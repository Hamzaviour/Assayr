"""Install, upgrade, roll back and uninstall Assayr as Windows services."""

import os
import secrets
import shutil
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
    runner.run(["icacls.exe", cfg.data_dir, "/inheritance:r", "/grant:r", *grants, "/T", "/C", "/Q"])


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


def _initdb(cfg: InstallConfig, runner, db_password: str) -> None:
    if (cfg.db_dir / "PG_VERSION").exists():
        return
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


def _ensure_database(cfg: InstallConfig, runner, db_password: str) -> None:
    """Create the assayr database once PostgreSQL runs (does nothing if it exists)."""
    runner.run(
        [cfg.pg_bin / "createdb.exe", "-h", "127.0.0.1", "-p", str(cfg.pg_port), "-U", "assayr", "assayr"],
        env=_child_env(cfg, PGPASSWORD=db_password),
        check=False,
    )


def _start_db(cfg: InstallConfig, runner, db_password: str) -> None:
    runner.run(["sc.exe", "start", "AssayrDb"], check=False)
    services.wait_running(cfg, runner, "AssayrDb")
    _ensure_database(cfg, runner, db_password)


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
    new_data_dir = not cfg.data_dir.exists()
    try:
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
        _assayr(cfg, runner, "create-admin", "--email", admin_email, ASSAYR_ADMIN_PASSWORD=admin_password)
        _firewall(cfg, runner, add=True)
        services.start_all(cfg, runner)
        _schedule_backup(cfg, runner)
        wait(cfg.health_url, health_timeout, cfg.version)
    except (CommandError, HealthError, ProvisionError, OSError) as exc:
        services.unregister(cfg, runner)
        _firewall(cfg, runner, add=False)
        if new_data_dir:
            shutil.rmtree(cfg.data_dir, ignore_errors=True)
        raise ProvisionError(f"Installation failed: {exc} (see {cfg.install_log})") from exc


def finish_upgrade(cfg: InstallConfig, runner, *, health_timeout: float = 180.0, wait=wait_healthy) -> None:
    """Run by the new program after its files are in place: re-register, migrate, start, check health."""
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
        services.start_all(cfg, runner)
        _schedule_backup(cfg, runner)
        wait(cfg.health_url, health_timeout, cfg.version)
    except (CommandError, HealthError, OSError) as exc:
        raise ProvisionError(f"Upgrade failed: {exc}") from exc


def make_backup(cfg: InstallConfig, runner, now: datetime | None = None) -> Path:
    db = PgTools(cfg.pg_bin, database_url(cfg, _env_password(cfg) or ""))
    sources = BackupSources(cfg.blobs_dir, cfg.env_file, cfg.certs_dir, cfg.license_dir)
    return create_backup(cfg.backups_dir, cfg.version, sources, db.dump, now or datetime.now(UTC))


def rollback(cfg: InstallConfig, backup: Path, runner) -> None:
    """Run by the restored (old) program: put the pre-upgrade database and files back, then start."""
    password = _env_password(cfg) or ""
    services.stop_all(cfg, runner)
    services.unregister(cfg, runner)
    _write_files(cfg, password)
    services.register(cfg, runner)
    _start_db(cfg, runner, password)
    work = cfg.data_dir / ".restore"
    shutil.rmtree(work, ignore_errors=True)
    try:
        source = read_backup(backup, work)
        restore_data(source, cfg.blobs_dir, PgTools(cfg.pg_bin, database_url(cfg, password)))
    except PgError as exc:
        raise ProvisionError(f"Rollback could not restore the database: {exc}") from exc
    finally:
        shutil.rmtree(work, ignore_errors=True)
    services.start_all(cfg, runner)


def uninstall(cfg: InstallConfig, runner, *, delete_data: bool) -> None:
    services.unregister(cfg, runner)
    _firewall(cfg, runner, add=False)
    runner.run(["schtasks", "/Delete", "/F", "/TN", TASK_NAME], check=False)
    if delete_data:
        shutil.rmtree(cfg.data_dir, ignore_errors=True)
