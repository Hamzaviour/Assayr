"""`assayr` administration commands."""

import signal
import time
from datetime import timedelta
from pathlib import Path
from pathlib import Path

import typer
from sqlalchemy import select

from assayr.audit.service import SYSTEM, record, verify_chain
from assayr.catalogue.seed import ensure_default_scope, seed_iso27001
from assayr.certs import CertError, check_pair, generate_self_signed, pfx_to_pem
from assayr.config import get_settings
from assayr.db import Database, utcnow
from assayr.identity.models import RoleAssignment, User
from assayr.identity.rbac import Role
from assayr.identity.security import WeakPasswordError, hash_password, normalize_email
from assayr.jobs import JobEnv, run_one, run_pending
from assayr.migrate import upgrade
from assayr.risk.seed import ensure_methodology, ensure_risk_library
from assayr.storage import BlobStore

app = typer.Typer(help="Assayr administration commands.", no_args_is_help=True)


class StopFlag:
    """Set when the service manager asks the worker to stop (Ctrl+C, SIGTERM, Ctrl+Break on Windows)."""

    _SIGNALS = tuple(s for s in (getattr(signal, n, None) for n in ("SIGINT", "SIGTERM", "SIGBREAK")) if s)

    def __init__(self) -> None:
        self.requested = False
        self._previous: dict[int, object] = {}

    def _handle(self, signum, frame) -> None:
        self.requested = True

    def install(self) -> None:
        for sig in self._SIGNALS:
            self._previous[sig] = signal.signal(sig, self._handle)

    def restore(self) -> None:
        for sig, handler in self._previous.items():
            signal.signal(sig, handler)
        self._previous.clear()


def _enqueue_recompute(database: Database) -> None:
    from assayr.scoring.jobs import enqueue_recompute_all

    with database.sessionmaker() as session:
        enqueue_recompute_all(session, utcnow())
        session.commit()


def _worker_loop(database, env, settings, flag: StopFlag) -> None:
    next_recompute = utcnow()
    while not flag.requested:
        if utcnow() >= next_recompute:
            _enqueue_recompute(database)
            next_recompute = utcnow() + timedelta(minutes=settings.recompute_interval_minutes)
        if not run_one(database.sessionmaker if database else None, env):
            deadline = time.monotonic() + settings.worker_poll_seconds
            while not flag.requested and time.monotonic() < deadline:
                time.sleep(0.2)


def _database() -> Database:
    return Database(get_settings().database_url)


@app.command()
def migrate() -> None:
    """Apply database migrations."""
    upgrade(get_settings().database_url)
    typer.echo("Database is up to date.")


@app.command()
def seed() -> None:
    """Load the ISO/IEC 27001:2022 catalogue (safe to run repeatedly)."""
    with _database().sessionmaker() as session:
        scope = ensure_default_scope(session, get_settings().org_name)
        result = seed_iso27001(session, scope)
        ensure_methodology(session, utcnow())
        library = ensure_risk_library(session)
        session.commit()
    typer.echo(
        f"Seed complete: {result.requirements_created} requirements and {result.controls_created} controls created."
    )
    typer.echo(
        f"Risk library: {library.threats} threats, {library.vulnerabilities} vulnerabilities "
        f"and {library.templates} templates added."
    )


@app.command("create-admin")
def create_admin(
    email: str = typer.Option(..., help="Sign-in email for the administrator."),
    full_name: str = typer.Option("Administrator", help="Display name."),
    password: str = typer.Option(
        ...,
        prompt=True,
        hide_input=True,
        confirmation_prompt=True,
        envvar="ASSAYR_ADMIN_PASSWORD",
        help="At least 12 characters.",
    ),
) -> None:
    """Create the first administrator (platform admin + ISMS manager, all scopes)."""
    normalized = normalize_email(email)
    try:
        password_hash = hash_password(password)
    except WeakPasswordError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc
    with _database().sessionmaker() as session:
        if session.scalar(select(User.id).where(User.email == normalized)):
            typer.echo(f"A user with the email {normalized} already exists.", err=True)
            raise typer.Exit(1)
        user = User(
            email=normalized,
            full_name=full_name,
            password_hash=password_hash,
            role_assignments=[
                RoleAssignment(role=Role.PLATFORM_ADMIN.value),
                RoleAssignment(role=Role.ISMS_MANAGER.value),
            ],
        )
        session.add(user)
        session.flush()
        record(
            session,
            SYSTEM,
            "user.create",
            "user",
            str(user.id),
            diff={"email": [None, normalized], "roles": [None, ["isms_manager", "platform_admin"]]},
        )
        session.commit()
    typer.echo(f"Administrator {normalized} created.")


@app.command("audit-verify")
def audit_verify() -> None:
    """Check the audit trail's hash chain. Exits with code 2 if it is broken."""
    with _database().sessionmaker() as session:
        result = verify_chain(session)
    if result.ok:
        typer.echo(f"Audit chain intact: {result.checked} entries verified.")
        return
    typer.echo(
        f"Audit chain broken at entry {result.first_bad_seq} ({result.checked} entries verified before it).",
        err=True,
    )
    raise typer.Exit(2)


@app.command()
def worker(once: bool = typer.Option(False, "--once", help="Process the queued jobs, then exit.")) -> None:
    """Run background jobs: evidence verification and scheduled status checks."""
    import assayr.job_handlers  # noqa: F401

    settings = get_settings()
    database = _database()
    env = JobEnv(settings=settings, store=BlobStore(settings.storage_dir), now=utcnow)
    if once:
        processed = run_pending(database.sessionmaker, env)
        typer.echo(f"Processed {processed} job{'s' if processed != 1 else ''}.")
        return
    typer.echo("Worker started.")
    flag = StopFlag()
    flag.install()
    try:
        _worker_loop(database, env, settings, flag)
    finally:
        flag.restore()
    typer.echo("Worker stopped.")


@app.command("gen-cert")
def gen_cert(hostname: str = typer.Option(...), out: Path = typer.Option(...)) -> None:
    """Create a self-signed certificate (tls.crt, tls.key) valid for two years."""
    generate_self_signed(hostname, out / "tls.crt", out / "tls.key")
    typer.echo(f"Self-signed certificate for {hostname} written to {out}.")


@app.command("import-pfx")
def import_pfx(
    pfx: Path,
    out: Path = typer.Option(...),
    password: str = typer.Option("", envvar="ASSAYR_PFX_PASSWORD", hidden=True),
) -> None:
    """Convert a .pfx/.p12 file to tls.crt and tls.key (password from ASSAYR_PFX_PASSWORD)."""
    try:
        pfx_to_pem(pfx.read_bytes(), password or None, out / "tls.crt", out / "tls.key")
    except (CertError, OSError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc
    typer.echo(f"Certificate written to {out}.")


@app.command("check-cert")
def check_cert(cert: Path = typer.Option(...), key: Path = typer.Option(...)) -> None:
    """Check that a PEM certificate and key can be read and belong together."""
    try:
        check_pair(cert, key)
    except CertError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc
    typer.echo("Certificate and key match.")
