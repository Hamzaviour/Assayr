"""Install, upgrade, roll back and uninstall Assayr as Windows services."""

import os
import secrets
import shutil
import socket
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from dotenv import dotenv_values

from assayr.backup import BackupSources, create_backup, read_backup, restore_data
from assayr.certs import CertError, check_pair, generate_self_signed, pfx_to_pem
from assayr.healthcheck import HealthError, wait_healthy
from assayr.pgtools import PgError, PgTools
from assayr.windows import services
from assayr.windows.layout import SERVICES, InstallConfig
from assayr.windows.render import database_url, render_caddyfile, render_clamd_conf, render_env
from assayr.windows.runner import CommandError

__all__ = ["CertChoice", "CommandError", "HealthError", "InstallConfig", "ProvisionError"]

TASK_NAME = "Assayr nightly backup"
_sleep = time.sleep  # replaced in tests


class ProvisionError(Exception):
    pass


@dataclass
class CertChoice:
    mode: str  # self-signed | pem | pfx
    cert: Path | None = None
    key: Path | None = None


def _env_password(cfg: InstallConfig) -> str | None:
    if not cfg.env_file.exists():
        return None
    return dotenv_values(cfg.env_file).get("POSTGRES_PASSWORD") or None


def _child_env(cfg: InstallConfig, **extra: str) -> dict[str, str]:
    return {**os.environ, "ASSAYR_ENV_FILE": str(cfg.env_file), "PYTHONUTF8": "1", **extra}


def _assayr(cfg: InstallConfig, runner, *args: str, **extra_env: str) -> None:
    runner.run([cfg.python_exe, "-m", "assayr", *args], env=_child_env(cfg, **extra_env))


def _secure_data_dir(cfg: InstallConfig, runner) -> None:
    """Only Administrators, SYSTEM and the Assayr service accounts may use the data folder."""
    grants = ["*S-1-5-32-544:(OI)(CI)F", "*S-1-5-18:(OI)(CI)F"]
    grants += [
        f"{services.account(s)}:(OI)(CI)M" for s in SERVICES if s != "AssayrClamAV" or cfg.malware_scan
    ]
    # Set the folder's own ACL only: with /T, /inheritance:r also strips every existing file, leaving
    # files (install.log first) with an empty ACL nobody can open. Then make everything below inherit it.
    runner.run(["icacls.exe", cfg.data_dir, "/inheritance:r", "/grant:r", *grants, "/C", "/Q"])
    runner.run(["icacls.exe", cfg.data_dir / "*", "/reset", "/T", "/C", "/Q"])


def _check_folders(cfg: InstallConfig) -> None:
    program, data = cfg.install_dir.resolve(), cfg.data_dir.resolve()
    if program == data or program.is_relative_to(data) or data.is_relative_to(program):
        raise ProvisionError(
            f"The data folder ({data}) and the program folder ({program}) must be separate folders, "
            "neither inside the other: upgrades replace the program folder."
        )


def _write_files(cfg: InstallConfig, db_password: str) -> None:
    cfg.env_file.write_text(render_env(cfg, db_password), encoding="utf-8")
    cfg.caddyfile.write_text(render_caddyfile(cfg), encoding="utf-8")
    cfg.clamd_conf.write_text(render_clamd_conf(cfg), encoding="utf-8")
    cfg.save()


def _certs(cfg: InstallConfig, cert: CertChoice, pfx_password: str | None) -> None:
    if cfg.web_mode == "http":
        return
    crt, key = cfg.certs_dir / "tls.crt", cfg.certs_dir / "tls.key"
    try:
        if cert.mode == "pem":
            cfg.certs_dir.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(cert.cert, crt)
            shutil.copyfile(cert.key, key)
            check_pair(crt, key)
        elif cert.mode == "pfx":
            pfx_to_pem(Path(cert.cert).read_bytes(), pfx_password, crt, key)
        elif not crt.exists():
            generate_self_signed(cfg.hostname, crt, key)
    except (CertError, OSError, TypeError) as exc:
        raise ProvisionError(f"Certificate: {exc}") from exc


def _grant_installer(cfg: InstallConfig, runner) -> None:
    """initdb drops its admin rights, so grant the installing account the db folder explicitly."""
    out = runner.run(["whoami", "/user", "/fo", "csv", "/nh"], check=False).stdout or ""
    sid = out.strip().rsplit(",", 1)[-1].strip().strip('"')
    cfg.db_dir.mkdir(parents=True, exist_ok=True)
    if sid.startswith("S-1-"):
        runner.run(["icacls.exe", cfg.db_dir, "/grant", f"*{sid}:(OI)(CI)F", "/Q"])


def _initdb(cfg: InstallConfig, runner, db_password: str) -> None:
    if (cfg.db_dir / "PG_VERSION").exists():
        return
    _grant_installer(cfg, runner)
    pwfile = cfg.data_dir / ".initdb.pw"
    pwfile.write_text(db_password, encoding="utf-8")
    try:
        runner.run(
            [
                cfg.pg_bin / "initdb.exe",
                "-D",
                cfg.db_dir,
                "-U",
                "assayr",
                "--pwfile",
                pwfile,
                "-E",
                "UTF8",
                "--locale=C",
                "--auth=scram-sha-256",
            ]
        )
    finally:
        pwfile.unlink(missing_ok=True)


def _wait_db_ready(cfg: InstallConfig, runner, timeout_s: int = 90) -> None:
    """A RUNNING service is not yet a PostgreSQL that accepts connections; ask pg_isready."""
    for _ in range(timeout_s):
        ready = runner.run(
            [cfg.pg_bin / "pg_isready.exe", "-h", "127.0.0.1", "-p", str(cfg.pg_port)], check=False
        )
        if ready.returncode == 0:
            return
        _sleep(1)
    raise CommandError(f"PostgreSQL did not accept connections on port {cfg.pg_port}; see {cfg.logs_dir}")


def _ensure_database(cfg: InstallConfig, runner, db_password: str) -> None:
    """Create the assayr database (an existing one is fine)."""
    result = runner.run(
        [cfg.pg_bin / "createdb.exe", "-h", "127.0.0.1", "-p", str(cfg.pg_port), "-U", "assayr", "assayr"],
        env=_child_env(cfg, PGPASSWORD=db_password),
        check=False,
    )
    output = f"{result.stdout or ''}{result.stderr or ''}"
    if result.returncode != 0 and "already exists" not in output:
        raise CommandError(f"createdb failed: {output.strip()}")


def _start_db(cfg: InstallConfig, runner, db_password: str) -> None:
    runner.run(["sc.exe", "start", "AssayrDb"], check=False)
    services.wait_running(cfg, runner, "AssayrDb")
    _wait_db_ready(cfg, runner)
    _ensure_database(cfg, runner, db_password)


def _port_free(port: int) -> bool:
    with socket.socket() as probe:
        try:
            probe.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def _choose_internal_ports(cfg: InstallConfig) -> None:
    """Move PostgreSQL, the API and ClamAV to free local ports when their defaults are taken."""
    taken = {cfg.https_port, cfg.http_port}
    for name in ("pg_port", "api_port", "clamav_port"):
        port = getattr(cfg, name)
        while port in taken or not _port_free(port):
            port += 1
        setattr(cfg, name, port)
        taken.add(port)


def _failed_log(cfg: InstallConfig) -> Path:
    return cfg.data_dir.with_name(f"{cfg.data_dir.name}-install-failed.log")


def _firewall(cfg: InstallConfig, runner, add: bool) -> None:
    ports = [cfg.http_port] if cfg.web_mode == "http" else [cfg.https_port, cfg.http_port]
    for port in ports:
        name = f"name=Assayr ({port})"
        runner.run(["netsh", "advfirewall", "firewall", "delete", "rule", name], check=False)
        if add:
            runner.run(
                ["netsh", "advfirewall", "firewall", "add", "rule", name, "dir=in", "action=allow", "protocol=TCP",
                 f"localport={port}"]
            )  # fmt: skip


def _schedule_backup(cfg: InstallConfig, runner) -> None:
    admin = cfg.install_dir / "assayr-admin.cmd"
    runner.run(
        ["schtasks", "/Create", "/F", "/TN", TASK_NAME, "/SC", "DAILY", "/ST", "02:00", "/RU", "SYSTEM",
         "/TR", f'"{admin}" backup --scheduled']
    )  # fmt: skip


def _copy_signatures(cfg: InstallConfig) -> None:
    """First install: start ClamAV with the signatures bundled in the installer."""
    if not cfg.malware_scan or not cfg.bundled_signatures.is_dir() or any(cfg.clamav_db_dir.glob("*.c?d")):
        return
    cfg.clamav_db_dir.mkdir(parents=True, exist_ok=True)
    for f in cfg.bundled_signatures.iterdir():
        shutil.copyfile(f, cfg.clamav_db_dir / f.name)


def install(
    cfg: InstallConfig,
    admin_email: str,
    admin_password: str,
    cert: CertChoice,
    runner,
    *,
    pfx_password: str | None = None,
    health_timeout: float = 180.0,
    wait=wait_healthy,
    token=secrets.token_urlsafe,
) -> None:
    """First installation. On failure removes what it registered, and the data folder if it created it."""
    _check_folders(cfg)
    new_data_dir = not cfg.data_dir.exists()
    try:
        services.unregister(cfg, runner, sleep=_sleep)  # left over from an interrupted attempt
        if not (cfg.db_dir / "PG_VERSION").exists():
            _choose_internal_ports(cfg)
        for d in (
            cfg.data_dir,
            cfg.blobs_dir,
            cfg.backups_dir,
            cfg.logs_dir,
            cfg.certs_dir,
            cfg.clamav_db_dir,
        ):
            d.mkdir(parents=True, exist_ok=True)
        db_password = _env_password(cfg) or token(32)
        _certs(cfg, cert, pfx_password)
        _copy_signatures(cfg)
        _write_files(cfg, db_password)
        _initdb(cfg, runner, db_password)
        services.register(cfg, runner)
        _secure_data_dir(cfg, runner)
        _start_db(cfg, runner, db_password)
        _assayr(cfg, runner, "migrate")
        _assayr(cfg, runner, "seed")
        _assayr(
            cfg,
            runner,
            "create-admin",
            "--email",
            admin_email,
            "--if-no-admin",
            ASSAYR_ADMIN_PASSWORD=admin_password,
        )
        _firewall(cfg, runner, add=True)
        services.start_all(cfg, runner)
        _schedule_backup(cfg, runner)
        wait(cfg.health_url, health_timeout, cfg.version)
    except (CommandError, HealthError, ProvisionError, OSError) as exc:
        message = f"Installation failed: {exc}"
        services.unregister(cfg, runner, sleep=_sleep)
        _firewall(cfg, runner, add=False)
        log = cfg.install_log
        try:
            with log.open("a", encoding="utf-8") as handle:
                handle.write(f"{message}\n")
            if new_data_dir:
                log = _failed_log(cfg)
                shutil.copyfile(cfg.install_log, log)
        except OSError:
            pass
        if new_data_dir:
            shutil.rmtree(cfg.data_dir, ignore_errors=True)
        raise ProvisionError(f"{message} (see {log})") from exc


def finish_upgrade(cfg: InstallConfig, runner, *, health_timeout: float = 180.0, wait=wait_healthy) -> None:
    """Run by the new program after its files are in place: re-register, migrate, seed, start, check health."""
    try:
        password = _env_password(cfg)
        if not password:
            raise ProvisionError(f"{cfg.env_file} has no database password.")
        _copy_signatures(cfg)
        _write_files(cfg, password)
        services.unregister(cfg, runner)
        services.register(cfg, runner)
        _start_db(cfg, runner, password)
        _assayr(cfg, runner, "migrate")
        _assayr(cfg, runner, "seed")  # idempotent: adds catalogues new in this version (e.g. NIA)
        services.start_all(cfg, runner)
        _schedule_backup(cfg, runner)
        wait(cfg.health_url, health_timeout, cfg.version)
    except (CommandError, HealthError, OSError) as exc:
        services.unregister(cfg, runner, sleep=_sleep)  # so the setup can put the old program folder back
        raise ProvisionError(f"Upgrade failed: {exc}") from exc


def make_backup(cfg: InstallConfig, runner, now: datetime | None = None) -> Path:
    db = PgTools(cfg.pg_bin, database_url(cfg, _env_password(cfg) or ""))
    sources = BackupSources(cfg.blobs_dir, cfg.env_file, cfg.certs_dir, cfg.license_dir)
    return create_backup(cfg.backups_dir, cfg.version, sources, db.dump, now or datetime.now(UTC))


def rollback(cfg: InstallConfig, backup: Path, runner) -> None:
    """Run by the restored (old) program: put the pre-upgrade database and files back, then start."""
    password = _env_password(cfg) or ""
    services.unregister(cfg, runner, sleep=_sleep)
    _write_files(cfg, password)
    services.register(cfg, runner)
    _start_db(cfg, runner, password)
    work = cfg.data_dir / ".restore"
    shutil.rmtree(work, ignore_errors=True)
    try:
        source = read_backup(backup, work)
        restore_data(source, cfg.blobs_dir, PgTools(cfg.pg_bin, database_url(cfg, password)))
    except (PgError, CommandError) as exc:
        raise ProvisionError(f"Rollback could not restore the database: {exc}") from exc
    finally:
        shutil.rmtree(work, ignore_errors=True)
    services.start_all(cfg, runner)


def uninstall(cfg: InstallConfig, runner, *, delete_data: bool) -> None:
    services.unregister(cfg, runner, sleep=_sleep)
    _firewall(cfg, runner, add=False)
    runner.run(["schtasks", "/Delete", "/F", "/TN", TASK_NAME], check=False)
    if delete_data:
        shutil.rmtree(cfg.data_dir, ignore_errors=True)
