"""`assayr win …`: commands the Windows installer and the Assayr Admin console use."""

import json
import os
import shutil
from pathlib import Path

import typer

from assayr.backup import BackupError, read_backup, restore_data, version_tuple
from assayr.healthcheck import HealthError, wait_healthy
from assayr.pgtools import PgError, PgTools
from assayr.signatures import SignatureError, update_signatures
from assayr.windows import provision, services
from assayr.windows.layout import InstallConfig
from assayr.windows.render import database_url
from assayr.windows.runner import SubprocessRunner

win_app = typer.Typer(help="Manage Assayr installed as Windows services.", no_args_is_help=True)

DEFAULT_DATA = Path(os.environ.get("ASSAYR_DATA_DIR", r"C:\ProgramData\Assayr"))
DATA_DIR = typer.Option(DEFAULT_DATA, "--data-dir", help="Assayr data folder.")
LOG_NAMES = {
    "api": "AssayrApi",
    "worker": "AssayrWorker",
    "web": "AssayrWeb",
    "db": "AssayrDb",
    "clamav": "AssayrClamAV",
}
ANSWER_KEYS = (
    "install_dir",
    "data_dir",
    "hostname",
    "org_name",
    "https_port",
    "http_port",
    "web_mode",
    "behind_tls_proxy",
    "malware_scan",
    "version",
)
SCHEDULED_KEEP = 14


def _fail(message: str) -> None:
    typer.echo(message, err=True)
    raise typer.Exit(1)


def _load(data_dir: Path) -> InstallConfig:
    try:
        return InstallConfig.load(data_dir)
    except PermissionError:
        _fail("Run Assayr Admin as administrator: only administrators can read the Assayr data folder.")
    except OSError:
        _fail(f"No Assayr installation found in {data_dir}.")


def _runner(cfg: InstallConfig) -> SubprocessRunner:
    return SubprocessRunner(cfg.install_log)


def _address(cfg: InstallConfig) -> str:
    return cfg.health_url.rsplit("/api/", 1)[0]


@win_app.command()
def install(answers: Path = typer.Option(..., help="JSON file written by the setup wizard.")) -> None:
    """First installation (admin password from ASSAYR_ADMIN_PASSWORD)."""
    password = os.environ.get("ASSAYR_ADMIN_PASSWORD", "")
    if not password:
        _fail("Set ASSAYR_ADMIN_PASSWORD to the first administrator's password.")
    a = json.loads(answers.read_text(encoding="utf-8"))
    cfg = InstallConfig(**{k: a[k] for k in ANSWER_KEYS})
    cert = provision.CertChoice(
        a.get("cert_mode", "self-signed"),
        Path(a["cert_file"]) if a.get("cert_file") else None,
        Path(a["key_file"]) if a.get("key_file") else None,
    )
    try:
        provision.install(
            cfg,
            a["admin_email"],
            password,
            cert,
            SubprocessRunner(cfg.install_log),
            pfx_password=os.environ.get("ASSAYR_PFX_PASSWORD") or None,
        )
    except provision.ProvisionError as exc:
        _fail(str(exc))
    typer.echo(f"Assayr {cfg.version} is running at {_address(cfg)}")


@win_app.command("prepare-upgrade")
def prepare_upgrade(data_dir: Path = DATA_DIR, backup_out: Path = typer.Option(...)) -> None:
    """Back up, then stop the services, before the setup replaces the program files."""
    cfg = _load(data_dir)
    r = _runner(cfg)
    try:
        path = provision.make_backup(cfg, r)
    except BackupError as exc:
        _fail(f"The backup before the upgrade failed, so nothing was changed: {exc}")
    services.stop_all(cfg, r)
    backup_out.write_text(str(path), encoding="utf-8")
    typer.echo(f"Backup: {path}")


@win_app.command("finish-upgrade")
def finish_upgrade(
    data_dir: Path = DATA_DIR, version: str = typer.Option(...), install_dir: Path = typer.Option(...)
) -> None:
    """Configure and start the newly installed version."""
    cfg = _load(data_dir)
    cfg.version, cfg.install_dir = version, install_dir
    try:
        provision.finish_upgrade(cfg, _runner(cfg))
    except provision.ProvisionError as exc:
        _fail(str(exc))
    typer.echo(f"Upgraded to Assayr {version}.")


@win_app.command()
def rollback(
    data_dir: Path = DATA_DIR,
    backup: Path = typer.Option(...),
    version: str = typer.Option(...),
    install_dir: Path = typer.Option(...),
) -> None:
    """Put the previous version's data back after a failed upgrade."""
    cfg = _load(data_dir)
    cfg.version, cfg.install_dir = version, install_dir
    try:
        provision.rollback(cfg, backup, _runner(cfg))
    except (provision.ProvisionError, BackupError) as exc:
        _fail(str(exc))
    typer.echo(f"Assayr {version} and its data have been put back.")


@win_app.command()
def uninstall(data_dir: Path = DATA_DIR, delete_data: bool = typer.Option(False, "--delete-data")) -> None:
    """Remove the services, firewall rules and scheduled backup (data is kept unless --delete-data)."""
    cfg = _load(data_dir)
    provision.uninstall(cfg, _runner(cfg), delete_data=delete_data)


@win_app.command()
def status(data_dir: Path = DATA_DIR) -> None:
    """Version, address, services and free disk."""
    cfg = _load(data_dir)
    typer.echo(f"Assayr {cfg.version} - {_address(cfg)}")
    for name, state in services.status(cfg, _runner(cfg)).items():
        typer.echo(f"  {name:<14} {state}")
    free = shutil.disk_usage(cfg.data_dir).free // 2**30
    typer.echo(f"  Free disk on the data drive: {free} GB")


@win_app.command()
def start(data_dir: Path = DATA_DIR) -> None:
    """Start Assayr."""
    cfg = _load(data_dir)
    services.start_all(cfg, _runner(cfg))


@win_app.command()
def stop(data_dir: Path = DATA_DIR) -> None:
    """Stop Assayr."""
    cfg = _load(data_dir)
    services.stop_all(cfg, _runner(cfg))


@win_app.command()
def restart(data_dir: Path = DATA_DIR) -> None:
    """Restart Assayr (after changing assayr.env or the certificate)."""
    cfg = _load(data_dir)
    r = _runner(cfg)
    services.stop_all(cfg, r)
    services.start_all(cfg, r)


@win_app.command()
def logs(which: str = typer.Argument("api"), lines: int = 200, data_dir: Path = DATA_DIR) -> None:
    """Show the end of a service's log: api, worker, web, db or clamav."""
    cfg = _load(data_dir)
    service = LOG_NAMES.get(which)
    if not service:
        _fail(f"Choose one of: {', '.join(LOG_NAMES)}")
    for suffix in ("out", "err"):
        path = cfg.logs_dir / f"{service}.{suffix}.log"
        if path.exists():
            typer.echo(f"== {path}")
            typer.echo("\n".join(path.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:]))


@win_app.command()
def backup(data_dir: Path = DATA_DIR, scheduled: bool = typer.Option(False, "--scheduled")) -> None:
    """Back up the database, evidence files and settings to the backups folder."""
    cfg = _load(data_dir)
    try:
        path = provision.make_backup(cfg, _runner(cfg))
    except BackupError as exc:
        _fail(str(exc))
    if scheduled:
        renamed = path.with_name(path.name.removesuffix(".tar.gz") + "-scheduled.tar.gz")
        path.rename(renamed)
        path = renamed
        for old in sorted(cfg.backups_dir.glob("assayr-*-scheduled.tar.gz"))[:-SCHEDULED_KEEP]:
            old.unlink()
    typer.echo(f"Backup written to {path}")


@win_app.command()
def restore(file: Path, data_dir: Path = DATA_DIR, yes: bool = typer.Option(False, "--yes")) -> None:
    """Replace all data with a backup (a safety backup is taken first)."""
    cfg = _load(data_dir)
    work = cfg.data_dir / ".restore"
    shutil.rmtree(work, ignore_errors=True)
    try:
        source = read_backup(file, work)
        if version_tuple(source.version) > version_tuple(cfg.version):
            _fail(
                f"This backup was made by Assayr {source.version}, which is newer than the installed "
                f"{cfg.version}. Upgrade to {source.version} or later first."
            )
        prompt = (
            f"Restoring replaces all current Assayr data with the backup taken at {source.created}. Continue?"
        )
        if not yes and not typer.confirm(prompt):
            raise typer.Exit(1)
    except BackupError as exc:
        shutil.rmtree(work, ignore_errors=True)
        _fail(f"This backup can't be used: {exc}")
    r = _runner(cfg)
    safety = None
    try:
        safety = provision.make_backup(cfg, r)
        typer.echo(f"Safety backup: {safety}")
        for s in ("AssayrWeb", "AssayrWorker", "AssayrApi"):
            services.stop(cfg, r, s)
        db = PgTools(cfg.pg_bin, database_url(cfg, provision._env_password(cfg) or ""))
        restore_data(source, cfg.blobs_dir, db)
        provision._assayr(cfg, r, "migrate")
    except (BackupError, PgError, services.CommandError, OSError) as exc:
        services.start_all(cfg, r)
        hint = f"\nThe data from just before it is in {safety}. To put it back: assayr-admin restore {safety}"
        _fail(f"The restore failed: {exc}{hint if safety else ''}")
    finally:
        shutil.rmtree(work, ignore_errors=True)
    services.start_all(cfg, r)
    try:
        wait_healthy(cfg.health_url, 180, cfg.version)
    except HealthError as exc:
        _fail(f"The data was restored, but Assayr did not start: {exc}. See {cfg.logs_dir}")
    typer.echo("Restore complete.")


@win_app.command("update-signatures")
def update_sigs(path: Path, data_dir: Path = DATA_DIR) -> None:
    """Copy ClamAV signature files (.cvd, .cld) from a file or folder, then restart ClamAV."""
    cfg = _load(data_dir)
    try:
        copied = update_signatures(path, cfg.clamav_db_dir)
    except SignatureError as exc:
        _fail(str(exc))
    r = _runner(cfg)
    r.run(["sc.exe", "stop", "AssayrClamAV"], check=False)
    r.run(["sc.exe", "start", "AssayrClamAV"], check=False)
    typer.echo(f"Updated: {', '.join(copied)}")


@win_app.command("create-admin")
def create_admin(email: str = typer.Option(...), data_dir: Path = DATA_DIR) -> None:
    """Create another administrator."""
    cfg = _load(data_dir)
    password = typer.prompt("Password (at least 12 characters)", hide_input=True, confirmation_prompt=True)
    provision._assayr(cfg, _runner(cfg), "create-admin", "--email", email, ASSAYR_ADMIN_PASSWORD=password)
