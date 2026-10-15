# Windows Installer (v0.3.0) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship `Assayr-Setup-0.3.0.exe`, a single offline Windows installer that installs Assayr as native Windows services on Windows Server, published on the GitHub Release next to the Linux bundles.

**Architecture:** Nearly all installer logic lives in a new, unit-tested Python package `assayr.windows` (render config files, provision, upgrade, rollback, uninstall, service control) plus shared `assayr.backup` (Linux-compatible backup format). Inno Setup only shows the wizard, copies files and calls `python -m assayr win …`. A PowerShell build script assembles pinned, hash-checked runtimes (Python, PostgreSQL, Caddy, ClamAV, WinSW); a `windows-2022` GitHub Actions job builds, end-to-end tests and publishes the exe.

**Tech Stack:** Python 3.12 (typer, cryptography), PowerShell 5.1, Inno Setup 6, WinSW 2.12, PostgreSQL 16 Windows binaries, Caddy 2, ClamAV 1.4 win64, python-build-standalone 3.12, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-10-15-windows-installer-design.md`

## Global Constraints

- Version `0.3.0` in `backend/pyproject.toml` and `frontend/package.json`; tag `v0.3.0` only after every task passes.
- Supported: Windows Server 2019/2022/2025 and Windows 10/11, x64 only (build ≥ 17763).
- No network access at install or run time; every runtime is inside the exe.
- Data dir default `C:\ProgramData\Assayr`, program dir `C:\Program Files\Assayr`, registry `HKLM\SOFTWARE\Assayr` (`InstallDir`, `DataDir`, `Version`).
- Services: `AssayrDb`, `AssayrClamAV`, `AssayrApi`, `AssayrWorker`, `AssayrWeb`; each runs as `NT SERVICE\<name>`; only the web ports are reachable from the network.
- Passwords never on a command line, in `answers.ini` or in `install.log`; admin password via `ASSAYR_ADMIN_PASSWORD`, PFX password via `ASSAYR_PFX_PASSWORD`.
- Backup archive format identical to Linux: `assayr-<version>-<YYYYMMDDTHHMMSSZ>.tar.gz` → folder `assayr-<version>-<stamp>/` with `manifest.txt`, `db.dump` (`pg_dump -Fc`), `blobs.tar`, `assayr.env`, `certs/`, `license/` (optional), `SHA256SUMS` (`<sha256>  ./<path>` lines, sorted, excluding `SHA256SUMS*`).
- Admin password minimum 12 characters (existing `hash_password` rule).
- Health endpoint: `https://localhost:<https_port>/api/v1/healthz` returns `{"status":"ok","version":"<version>"}`.
- Linux installer (`deploy/installer/`) behaviour must not change.
- Commits have no `Co-Authored-By` trailer (the user is the sole contributor).
- Dev machine: source `scripts/dev-env.sh` first (C: drive is full); run backend commands from `backend/` with `uv run`.

## Review Focus

1. **Paths with spaces** (`C:\Program Files\Assayr`, a data dir like `D:\Assayr Data`) — every generated command line, WinSW XML, Caddyfile and clamd.conf must quote/escape them; tests in Tasks 6 and 7 use a path with spaces.
2. **Re-running the installer on a machine where a previous install failed half-way** (services registered, data dir partly created) — provision must clean up what it created when the data dir was new, and a retry must succeed; test in Task 7.
3. **A restore archive made on Linux** (forward slashes, `./` prefixes, `certs/` without `license/`) restored on Windows — must verify and restore; test in Task 4.
4. **Passwords containing quotes, spaces, `%`, `&`, `^`** — must survive env-file rendering and the database URL; tests in Tasks 6 and 7.
5. **Service stop while the worker is processing a job** — the worker must finish the current job and exit, not leave a half-done job; test in Task 1.

---

## File Structure

```
backend/src/assayr/
  __init__.py              (modify) version from package metadata
  config.py                (modify) ASSAYR_ENV_FILE support
  cli.py                   (modify) worker stop flag; register backup/restore/cert/health/win commands
  certs.py                 (create) self-signed generation, PFX → PEM
  backup.py                (create) Linux-compatible backup create/verify/restore
  pgtools.py               (create) pg_dump / pg_restore / createdb / dropdb wrappers
  healthcheck.py           (create) wait-for-health over HTTPS (self-signed OK)
  signatures.py            (create) ClamAV offline signature update
  windows/
    __init__.py
    layout.py              (create) InstallConfig, install.json, paths
    render.py              (create) assayr.env, Caddyfile, clamd.conf, WinSW XML
    runner.py              (create) Runner protocol, SubprocessRunner (logs, redacts)
    services.py            (create) register/start/stop/status/logs
    provision.py           (create) install, finish_upgrade, rollback, uninstall
    cli.py                 (create) `assayr win …` typer sub-app
backend/tests/
  test_version_config.py, test_worker_stop.py, test_certs.py, test_backup.py,
  test_restore.py, test_healthcheck.py, test_signatures.py,
  windows/test_layout.py, windows/test_render.py, windows/test_services.py,
  windows/test_provision.py, windows/test_win_cli.py
deploy/windows/
  components.json          pinned downloads + sha256
  build.ps1                assemble staging dir
  assayr-admin.cmd         admin entry point
  assayr.iss               Inno Setup script
  answers.example.ini
  tests/e2e.ps1            end-to-end test on a clean Windows Server
  README-INSTALL-WINDOWS.md
  MANUAL-CHECKS.md
.github/workflows/release.yml   (modify) clamav-signatures + windows jobs, publish exe
.github/workflows/ci.yml        (modify) backend tests on windows-2022
```

---

### Task 1: Version, env file and clean worker stop

**Files:**
- Modify: `backend/src/assayr/__init__.py`
- Modify: `backend/src/assayr/config.py`
- Modify: `backend/src/assayr/cli.py` (worker command)
- Test: `backend/tests/test_version_config.py`, `backend/tests/test_worker_stop.py`

**Interfaces:**
- Produces: `assayr.__version__: str` equal to the installed package version; `get_settings()` reads the file named by `ASSAYR_ENV_FILE` (default `.env`); `assayr.cli.StopFlag` with `.requested: bool` and `install()`; `worker` loop exits after the current job when stop is requested.

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_version_config.py`:
```python
from importlib.metadata import version

import assayr
from assayr.config import get_settings


def test_version_matches_package_metadata():
    assert assayr.__version__ == version("assayr")


def test_env_file_named_by_variable(tmp_path, monkeypatch):
    env_file = tmp_path / "my settings.env"
    env_file.write_text('ASSAYR_ORG_NAME="Org from file"\nASSAYR_MAX_UPLOAD_MB=7\n', encoding="utf-8")
    monkeypatch.setenv("ASSAYR_ENV_FILE", str(env_file))
    monkeypatch.delenv("ASSAYR_ORG_NAME", raising=False)
    get_settings.cache_clear()
    try:
        settings = get_settings()
        assert settings.org_name == "Org from file"
        assert settings.max_upload_mb == 7
    finally:
        get_settings.cache_clear()
```

`backend/tests/test_worker_stop.py`:
```python
import signal

from assayr import cli


def test_stop_flag_set_by_signal_handler():
    flag = cli.StopFlag()
    flag.install()
    try:
        handler = signal.getsignal(signal.SIGINT)
        handler(signal.SIGINT, None)
        assert flag.requested
    finally:
        flag.restore()


def test_worker_finishes_current_job_then_exits(monkeypatch):
    calls = []
    flag = cli.StopFlag()

    def fake_run_one(make_session, env):
        calls.append("job")
        flag.requested = True  # stop arrives while a job runs
        return True

    monkeypatch.setattr(cli, "run_one", fake_run_one)
    monkeypatch.setattr(cli, "_enqueue_recompute", lambda database: None)
    cli._worker_loop(database=None, env=None, settings=cli.get_settings(), flag=flag)
    assert calls == ["job"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_version_config.py tests/test_worker_stop.py -v`
Expected: FAIL — version is `0.1.0`, env file ignored, `StopFlag` not defined.

- [ ] **Step 3: Implement**

`backend/src/assayr/__init__.py`:
```python
"""Assayr - on-premise GRC for ISO/IEC 27001."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("assayr")
except PackageNotFoundError:  # running from a source tree without installation
    __version__ = "0.0.0"
```

`backend/src/assayr/config.py` — replace `get_settings`:
```python
import os
...
@lru_cache
def get_settings() -> Settings:
    return Settings(_env_file=os.environ.get("ASSAYR_ENV_FILE", ".env"), _env_file_encoding="utf-8")
```

`backend/src/assayr/cli.py` — add near the top (after imports, `import signal` added):
```python
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
```
and replace the `while True:` tail of `worker()` with:
```python
    typer.echo("Worker started.")
    flag = StopFlag()
    flag.install()
    try:
        _worker_loop(database, env, settings, flag)
    finally:
        flag.restore()
    typer.echo("Worker stopped.")
```
(remove the now-unused `enqueue_recompute_all` import inside `worker`).

- [ ] **Step 4: Run the tests and the full suite**

Run: `uv run pytest -q && uv run ruff check . && uv run ruff format --check .`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add backend/src/assayr/__init__.py backend/src/assayr/config.py backend/src/assayr/cli.py backend/tests/test_version_config.py backend/tests/test_worker_stop.py
git commit -m "feat(backend): package version, ASSAYR_ENV_FILE and graceful worker stop"
```

---

### Task 2: Certificates — self-signed and PFX import

**Files:**
- Create: `backend/src/assayr/certs.py`
- Modify: `backend/pyproject.toml` (add `cryptography>=43`), `backend/uv.lock` (`uv lock`)
- Modify: `backend/src/assayr/cli.py` (commands `gen-cert`, `import-pfx`)
- Test: `backend/tests/test_certs.py`

**Interfaces:**
- Produces: `generate_self_signed(hostname: str, cert_path: Path, key_path: Path, days: int = 730) -> None`; `pfx_to_pem(pfx: bytes, password: str | None, cert_path: Path, key_path: Path) -> None` (raises `CertError` with a user-readable message); `check_pair(cert_path, key_path) -> None` (raises `CertError`). CLI: `assayr gen-cert --hostname H --out DIR`, `assayr import-pfx FILE --out DIR` (password from `ASSAYR_PFX_PASSWORD`), `assayr check-cert --cert C --key K`. Files written: `DIR/tls.crt`, `DIR/tls.key`.

- [ ] **Step 1: Add dependency**

Run: `uv add "cryptography>=43"`
Expected: `pyproject.toml` and `uv.lock` updated.

- [ ] **Step 2: Write the failing tests** — `backend/tests/test_certs.py`:
```python
import datetime as dt

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import pkcs12
from typer.testing import CliRunner

from assayr.certs import CertError, check_pair, generate_self_signed, pfx_to_pem
from assayr.cli import app


def test_self_signed_has_hostname_and_localhost(tmp_path):
    crt, key = tmp_path / "tls.crt", tmp_path / "tls.key"
    generate_self_signed("grc.example.local", crt, key)
    cert = x509.load_pem_x509_certificate(crt.read_bytes())
    names = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    assert set(names.get_values_for_type(x509.DNSName)) == {"grc.example.local", "localhost"}
    assert (cert.not_valid_after_utc - cert.not_valid_before_utc).days >= 729
    check_pair(crt, key)


def _pfx(password: bytes | None) -> bytes:
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(x509.oid.NameOID.COMMON_NAME, "grc")])
    now = dt.datetime.now(dt.UTC)
    cert = (
        x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
        .serial_number(1).not_valid_before(now).not_valid_after(now + dt.timedelta(days=1))
        .sign(key, hashes.SHA256())
    )
    enc = serialization.BestAvailableEncryption(password) if password else serialization.NoEncryption()
    return pkcs12.serialize_key_and_certificates(b"grc", key, cert, None, enc)


def test_pfx_with_password_converts(tmp_path):
    crt, key = tmp_path / "tls.crt", tmp_path / "tls.key"
    pfx_to_pem(_pfx(b"p&ss %word^"), "p&ss %word^", crt, key)
    check_pair(crt, key)


def test_pfx_wrong_password_is_readable_error(tmp_path):
    with pytest.raises(CertError, match="password"):
        pfx_to_pem(_pfx(b"right"), "wrong", tmp_path / "c", tmp_path / "k")


def test_mismatched_pair_rejected(tmp_path):
    generate_self_signed("a", tmp_path / "a.crt", tmp_path / "a.key")
    generate_self_signed("b", tmp_path / "b.crt", tmp_path / "b.key")
    with pytest.raises(CertError, match="does not match"):
        check_pair(tmp_path / "a.crt", tmp_path / "b.key")


def test_cli_import_pfx_reads_password_from_environment(tmp_path):
    pfx = tmp_path / "server.pfx"
    pfx.write_bytes(_pfx(b"secret"))
    result = CliRunner().invoke(
        app, ["import-pfx", str(pfx), "--out", str(tmp_path / "certs")], env={"ASSAYR_PFX_PASSWORD": "secret"}
    )
    assert result.exit_code == 0, result.output
    assert (tmp_path / "certs" / "tls.crt").exists() and (tmp_path / "certs" / "tls.key").exists()
```

- [ ] **Step 3: Run to verify failure**

Run: `uv run pytest tests/test_certs.py -v` — Expected: FAIL, `assayr.certs` missing.

- [ ] **Step 4: Implement** `backend/src/assayr/certs.py`:
```python
"""TLS certificate helpers for installers: self-signed generation, PFX import, key/cert check."""

import datetime as dt
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID


class CertError(Exception):
    pass


def _write_pair(cert_pem: bytes, key_pem: bytes, cert_path: Path, key_path: Path) -> None:
    cert_path.parent.mkdir(parents=True, exist_ok=True)
    key_path.parent.mkdir(parents=True, exist_ok=True)
    cert_path.write_bytes(cert_pem)
    key_path.write_bytes(key_pem)


def _key_pem(key) -> bytes:
    return key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    )


def generate_self_signed(hostname: str, cert_path: Path, key_path: Path, days: int = 730) -> None:
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, hostname)])
    now = dt.datetime.now(dt.UTC)
    names = [x509.DNSName(hostname)] + ([x509.DNSName("localhost")] if hostname != "localhost" else [])
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - dt.timedelta(minutes=5))
        .not_valid_after(now + dt.timedelta(days=days))
        .add_extension(x509.SubjectAlternativeName(names), critical=False)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )
    _write_pair(cert.public_bytes(serialization.Encoding.PEM), _key_pem(key), cert_path, key_path)


def pfx_to_pem(pfx: bytes, password: str | None, cert_path: Path, key_path: Path) -> None:
    try:
        key, cert, extra = pkcs12.load_key_and_certificates(pfx, password.encode() if password else None)
    except ValueError as exc:
        raise CertError("The .pfx file could not be opened: check the password.") from exc
    if key is None or cert is None:
        raise CertError("The .pfx file must contain both the certificate and its private key.")
    chain = b"".join(c.public_bytes(serialization.Encoding.PEM) for c in [cert, *(extra or [])])
    _write_pair(chain, _key_pem(key), cert_path, key_path)


def check_pair(cert_path: Path, key_path: Path) -> None:
    try:
        cert = x509.load_pem_x509_certificate(Path(cert_path).read_bytes())
        key = serialization.load_pem_private_key(Path(key_path).read_bytes(), password=None)
    except (OSError, ValueError) as exc:
        raise CertError(f"The certificate or key can't be read: {exc}") from exc
    if cert.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    ) != key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo):
        raise CertError("The private key does not match the certificate.")
```

Add to `backend/src/assayr/cli.py`:
```python
from pathlib import Path

from assayr.certs import CertError, check_pair, generate_self_signed, pfx_to_pem


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
```

- [ ] **Step 5: Run tests** — `uv run pytest tests/test_certs.py -v && uv run ruff check . && uv run ruff format --check .` → PASS.

- [ ] **Step 6: Commit**
```bash
git add backend/pyproject.toml backend/uv.lock backend/src/assayr/certs.py backend/src/assayr/cli.py backend/tests/test_certs.py
git commit -m "feat(backend): certificate commands for the Windows installer"
```

---

### Task 3: Linux-compatible backup (create)

**Files:**
- Create: `backend/src/assayr/pgtools.py`, `backend/src/assayr/backup.py`
- Test: `backend/tests/test_backup.py`

**Interfaces:**
- Produces:
  - `pgtools.PgTools(bin_dir: Path | None, url: str, run=subprocess.run)` with `dump(path: Path) -> None`, `recreate_database() -> None`, `restore(path: Path) -> None`. Builds `-h -p -U -d` from `url` (`postgresql+pg8000://user:pw@host:port/db`) and passes the password via `PGPASSWORD` in the child env only.
  - `backup.BackupSources(blobs_dir: Path, env_file: Path, certs_dir: Path, license_dir: Path | None)`
  - `backup.create_backup(dest: Path, version: str, sources: BackupSources, dump: Callable[[Path], None], now: datetime) -> Path`
  - `backup.write_sums(folder: Path) -> None`, `backup.verify_sums(folder: Path) -> str | None` (problem text or None)
  - `backup.BackupError(Exception)`

- [ ] **Step 1: Write the failing tests** — `backend/tests/test_backup.py`:
```python
import datetime as dt
import hashlib
import tarfile

import pytest

from assayr.backup import BackupError, BackupSources, create_backup, verify_sums, write_sums

NOW = dt.datetime(2026, 10, 15, 9, 30, 5, tzinfo=dt.UTC)


@pytest.fixture
def sources(tmp_path):
    blobs = tmp_path / "data dir" / "blobs"
    (blobs / "ab" / "cd").mkdir(parents=True)
    (blobs / "ab" / "cd" / ("ab" + "cd" + "0" * 60)).write_bytes(b"evidence")
    env = tmp_path / "data dir" / "assayr.env"
    env.write_text("ASSAYR_ORG_NAME=Acme\n", encoding="utf-8")
    certs = tmp_path / "data dir" / "certs"
    certs.mkdir()
    (certs / "tls.crt").write_text("CERT")
    (certs / "tls.key").write_text("KEY")
    return BackupSources(blobs_dir=blobs, env_file=env, certs_dir=certs, license_dir=None)


def fake_dump(path):
    path.write_bytes(b"PGDMP fake")


def test_archive_layout_matches_linux(tmp_path, sources):
    archive = create_backup(tmp_path / "backups", "0.3.0", sources, fake_dump, NOW)
    assert archive.name == "assayr-0.3.0-20261015T093005Z.tar.gz"
    with tarfile.open(archive) as tar:
        names = sorted(tar.getnames())
    top = "assayr-0.3.0-20261015T093005Z"
    assert names == sorted([
        top, f"{top}/manifest.txt", f"{top}/db.dump", f"{top}/blobs.tar", f"{top}/assayr.env",
        f"{top}/certs", f"{top}/certs/tls.crt", f"{top}/certs/tls.key", f"{top}/SHA256SUMS",
    ])


def test_manifest_and_sums_format(tmp_path, sources):
    archive = create_backup(tmp_path / "b", "0.3.0", sources, fake_dump, NOW)
    with tarfile.open(archive) as tar:
        tar.extractall(tmp_path / "x", filter="data")
    folder = tmp_path / "x" / "assayr-0.3.0-20261015T093005Z"
    assert (folder / "manifest.txt").read_text() == "version=0.3.0\ncreated=20261015T093005Z\n"
    lines = (folder / "SHA256SUMS").read_text().splitlines()
    assert lines == sorted(lines)
    digest = hashlib.sha256(b"PGDMP fake").hexdigest()
    assert f"{digest}  ./db.dump" in lines
    assert all("  ./" in line for line in lines)
    assert verify_sums(folder) is None


def test_blobs_tar_paths_are_relative(tmp_path, sources):
    archive = create_backup(tmp_path / "b", "0.3.0", sources, fake_dump, NOW)
    with tarfile.open(archive) as tar:
        tar.extractall(tmp_path / "x", filter="data")
    with tarfile.open(tmp_path / "x" / "assayr-0.3.0-20261015T093005Z" / "blobs.tar") as blobs:
        assert any(n.endswith("ab/cd/abcd" + "0" * 60) and not n.startswith("/") for n in blobs.getnames())


def test_failed_dump_leaves_nothing(tmp_path, sources):
    def broken(path):
        raise BackupError("pg_dump failed")

    with pytest.raises(BackupError):
        create_backup(tmp_path / "b", "0.3.0", sources, broken, NOW)
    assert list((tmp_path / "b").iterdir()) == []


def test_same_second_gets_suffix(tmp_path, sources):
    first = create_backup(tmp_path / "b", "0.3.0", sources, fake_dump, NOW)
    second = create_backup(tmp_path / "b", "0.3.0", sources, fake_dump, NOW)
    assert first != second and second.name.endswith("-2.tar.gz")


def test_verify_detects_tampering(tmp_path):
    (tmp_path / "a.txt").write_text("one")
    write_sums(tmp_path)
    (tmp_path / "a.txt").write_text("two")
    assert verify_sums(tmp_path) == "a.txt does not match its checksum."
```

- [ ] **Step 2: Run to verify failure** — `uv run pytest tests/test_backup.py -v` → FAIL (module missing).

- [ ] **Step 3: Implement** `backend/src/assayr/pgtools.py`:
```python
"""Run PostgreSQL client tools against the Assayr database without putting the password on a command line."""

import os
import subprocess
from pathlib import Path
from urllib.parse import unquote, urlsplit


class PgError(Exception):
    pass


class PgTools:
    def __init__(self, bin_dir: Path | None, url: str, run=subprocess.run) -> None:
        parts = urlsplit(url.replace("postgresql+pg8000://", "postgresql://", 1))
        self.host = parts.hostname or "127.0.0.1"
        self.port = str(parts.port or 5432)
        self.user = unquote(parts.username or "assayr")
        self.password = unquote(parts.password or "")
        self.db = parts.path.lstrip("/") or "assayr"
        self.bin_dir = bin_dir
        self._run = run

    def _tool(self, name: str) -> str:
        if self.bin_dir is None:
            return name
        exe = self.bin_dir / (name + (".exe" if os.name == "nt" else ""))
        return str(exe)

    def _call(self, args: list[str], stdin=None, stdout=None) -> None:
        env = {**os.environ, "PGPASSWORD": self.password}
        result = self._run(args, env=env, stdin=stdin, stdout=stdout, stderr=subprocess.PIPE, check=False)
        if result.returncode != 0:
            err = (result.stderr or b"").decode(errors="replace").strip()
            raise PgError(f"{Path(args[0]).name} failed: {err}")

    def _conn(self) -> list[str]:
        return ["-h", self.host, "-p", self.port, "-U", self.user]

    def dump(self, path: Path) -> None:
        self._call([self._tool("pg_dump"), *self._conn(), "-d", self.db, "-Fc", "-f", str(path)])

    def recreate_database(self) -> None:
        self._call([self._tool("dropdb"), *self._conn(), "--if-exists", "--force", self.db])
        self._call([self._tool("createdb"), *self._conn(), "-O", self.user, self.db])

    def restore(self, path: Path) -> None:
        self._call(
            [self._tool("pg_restore"), *self._conn(), "-d", self.db, "--no-owner", "--exit-on-error", str(path)]
        )
```

`backend/src/assayr/backup.py`:
```python
"""Backups in the same format as the Linux installer (deploy/installer/lib/backup.sh)."""

import hashlib
import os
import shutil
import tarfile
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

REQUIRED = ("manifest.txt", "db.dump", "blobs.tar")


class BackupError(Exception):
    pass


@dataclass(frozen=True)
class BackupSources:
    blobs_dir: Path
    env_file: Path
    certs_dir: Path
    license_dir: Path | None


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def write_sums(folder: Path) -> None:
    files = sorted(
        "./" + p.relative_to(folder).as_posix()
        for p in folder.rglob("*")
        if p.is_file() and not p.name.startswith("SHA256SUMS")
    )
    lines = "".join(f"{_sha256(folder / f[2:])}  {f}\n" for f in files)
    (folder / "SHA256SUMS.tmp").write_text(lines, encoding="utf-8", newline="\n")
    os.replace(folder / "SHA256SUMS.tmp", folder / "SHA256SUMS")


def verify_sums(folder: Path) -> str | None:
    sums = folder / "SHA256SUMS"
    if not sums.is_file():
        return "SHA256SUMS is missing."
    for line in sums.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        digest, _, path = line.partition("  ")
        rel = path.lstrip("*").removeprefix("./")
        target = folder / rel
        if not target.is_file():
            return f"{rel} is missing."
        if _sha256(target) != digest.strip():
            return f"{rel} does not match its checksum."
    return None


def _tar_dir(source: Path, target: Path) -> None:
    with tarfile.open(target, "w", format=tarfile.PAX_FORMAT) as tar:
        for path in sorted(source.rglob("*")):
            tar.add(path, arcname="./" + path.relative_to(source).as_posix(), recursive=False)


def create_backup(
    dest: Path, version: str, sources: BackupSources, dump: Callable[[Path], None], now: datetime
) -> Path:
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    name = f"assayr-{version}-{stamp}"
    dest.mkdir(parents=True, exist_ok=True)
    if (dest / f"{name}.tar.gz").exists():
        name += "-2"
    work = Path(tempfile.mkdtemp(prefix=".backup.", dir=dest))
    try:
        folder = work / name
        folder.mkdir()
        dump(folder / "db.dump")
        _tar_dir(sources.blobs_dir, folder / "blobs.tar")
        shutil.copy2(sources.env_file, folder / "assayr.env")
        shutil.copytree(sources.certs_dir, folder / "certs")
        if sources.license_dir and sources.license_dir.is_dir():
            shutil.copytree(sources.license_dir, folder / "license")
        (folder / "manifest.txt").write_text(f"version={version}\ncreated={stamp}\n", encoding="utf-8", newline="\n")
        write_sums(folder)
        partial = work / f"{name}.tar.gz"
        with tarfile.open(partial, "w:gz", format=tarfile.PAX_FORMAT) as tar:
            tar.add(folder, arcname=name)
        final = dest / f"{name}.tar.gz"
        os.replace(partial, final)
        return final
    except BackupError:
        raise
    except Exception as exc:
        raise BackupError(f"The backup failed: {exc}") from exc
    finally:
        shutil.rmtree(work, ignore_errors=True)
```

- [ ] **Step 4: Run tests** — `uv run pytest tests/test_backup.py -v && uv run ruff check . && uv run ruff format --check .` → PASS.

- [ ] **Step 5: Cross-check with the Linux reader (manual, Git Bash):**
```bash
cd /tmp && python -c "
import datetime as dt, pathlib, sys; sys.path.insert(0, r'E:/Work/GRC Tool/assayr/backend/src')
from assayr.backup import *
p=pathlib.Path('xb'); (p/'blobs').mkdir(parents=True, exist_ok=True); (p/'certs').mkdir(exist_ok=True); (p/'assayr.env').write_text('A=1\n')
print(create_backup(p/'out','0.3.0',BackupSources(p/'blobs',p/'assayr.env',p/'certs',None),lambda f:f.write_bytes(b'x'),dt.datetime.now(dt.UTC)))"
mkdir -p xr && tar -C xr -xzf xb/out/assayr-*.tar.gz && (cd xr/assayr-* && sha256sum -c SHA256SUMS)
```
Expected: every line `OK`.

- [ ] **Step 6: Commit**
```bash
git add backend/src/assayr/pgtools.py backend/src/assayr/backup.py backend/tests/test_backup.py
git commit -m "feat(backend): Linux-compatible backup archives in Python"
```

---

### Task 4: Restore (verify, version check, replace data)

**Files:**
- Modify: `backend/src/assayr/backup.py`
- Test: `backend/tests/test_restore.py`

**Interfaces:**
- Consumes: `verify_sums`, `REQUIRED`, `BackupError`, `PgTools` (Task 3).
- Produces:
  - `read_backup(archive: Path, work: Path) -> RestoreSource` where `RestoreSource(folder: Path, version: str, created: str)`; raises `BackupError` with the Linux wording (`"it can't be unpacked."`, `"it has no manifest."`, `"<part> is missing."`, `"<part> is not in its checksum list."`, checksum problems).
  - `version_tuple(v: str) -> tuple[int, int, int]`
  - `restore_data(source: RestoreSource, blobs_dir: Path, db: PgTools) -> None` — recreate DB, `pg_restore`, replace blobs. Does **not** touch `assayr.env` or certs (same as Linux).

- [ ] **Step 1: Write the failing tests** — `backend/tests/test_restore.py`:
```python
import io
import tarfile

import pytest

from assayr.backup import BackupError, read_backup, restore_data, version_tuple, write_sums


def linux_style_archive(tmp_path, version="0.2.0", drop=None, tamper=False):
    """Build an archive the way deploy/installer/lib/backup.sh does (GNU tar, ./ paths, no license dir)."""
    name = f"assayr-{version}-20261011T190000Z"
    folder = tmp_path / "src" / name
    (folder / "certs").mkdir(parents=True)
    (folder / "certs" / "tls.crt").write_text("CERT")
    (folder / "assayr.env").write_text("POSTGRES_PASSWORD=x\n")
    (folder / "db.dump").write_bytes(b"PGDMP")
    with tarfile.open(folder / "blobs.tar", "w") as blobs:
        data = b"evidence"
        info = tarfile.TarInfo("./ab/cd/abcd" + "0" * 60)
        info.size = len(data)
        blobs.addfile(info, io.BytesIO(data))
    (folder / "manifest.txt").write_text(f"version={version}\ncreated=20261011T190000Z\n")
    write_sums(folder)
    if drop:
        (folder / drop).unlink()
    if tamper:
        (folder / "db.dump").write_bytes(b"changed")
    archive = tmp_path / f"{name}.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        tar.add(folder, arcname=name)
    return archive


class FakeDb:
    def __init__(self):
        self.calls = []

    def recreate_database(self):
        self.calls.append("recreate")

    def restore(self, path):
        self.calls.append(("restore", path.read_bytes()))


def test_reads_linux_archive(tmp_path):
    src = read_backup(linux_style_archive(tmp_path), tmp_path / "work")
    assert (src.version, src.created) == ("0.2.0", "20261011T190000Z")


@pytest.mark.parametrize("drop", ["db.dump", "blobs.tar"])
def test_missing_part(tmp_path, drop):
    with pytest.raises(BackupError, match="is missing"):
        read_backup(linux_style_archive(tmp_path, drop=drop), tmp_path / "w")


def test_tampered_part(tmp_path):
    with pytest.raises(BackupError, match="does not match"):
        read_backup(linux_style_archive(tmp_path, tamper=True), tmp_path / "w")


def test_not_an_archive(tmp_path):
    bad = tmp_path / "x.tar.gz"
    bad.write_bytes(b"nope")
    with pytest.raises(BackupError, match="can't be unpacked"):
        read_backup(bad, tmp_path / "w")


def test_version_tuple():
    assert version_tuple("0.10.0") > version_tuple("0.9.9")


def test_restore_replaces_db_and_blobs(tmp_path):
    src = read_backup(linux_style_archive(tmp_path), tmp_path / "work")
    blobs = tmp_path / "blobs"
    (blobs / "old").mkdir(parents=True)
    (blobs / "old" / "file").write_text("old")
    db = FakeDb()
    restore_data(src, blobs, db)
    assert db.calls == ["recreate", ("restore", b"PGDMP")]
    assert not (blobs / "old").exists()
    assert (blobs / "ab" / "cd" / ("abcd" + "0" * 60)).read_bytes() == b"evidence"
```

- [ ] **Step 2: Run to verify failure** — `uv run pytest tests/test_restore.py -v` → FAIL (names missing).

- [ ] **Step 3: Implement** — append to `backend/src/assayr/backup.py`:
```python
@dataclass(frozen=True)
class RestoreSource:
    folder: Path
    version: str
    created: str


def version_tuple(v: str) -> tuple[int, int, int]:
    major, minor, patch = (int(x) for x in v.split("."))
    return major, minor, patch


def _manifest(path: Path) -> dict[str, str]:
    pairs = (line.partition("=") for line in path.read_text(encoding="utf-8").splitlines())
    return {k.strip(): v.strip() for k, _, v in pairs if k.strip()}


def read_backup(archive: Path, work: Path) -> RestoreSource:
    work.mkdir(parents=True, exist_ok=True)
    try:
        with tarfile.open(archive, "r:gz") as tar:
            tar.extractall(work, filter="data")
    except (tarfile.TarError, OSError, EOFError) as exc:
        raise BackupError("it can't be unpacked.") from exc
    folders = sorted(p for p in work.iterdir() if p.is_dir() and p.name.startswith("assayr-"))
    if not folders or not (folders[0] / "manifest.txt").is_file():
        raise BackupError("it has no manifest.")
    folder = folders[0]
    if problem := verify_sums(folder):
        raise BackupError(problem)
    listed = (folder / "SHA256SUMS").read_text(encoding="utf-8")
    for part in REQUIRED:
        if not (folder / part).is_file():
            raise BackupError(f"{part} is missing.")
        if f"  ./{part}\n" not in listed and f"  {part}\n" not in listed:
            raise BackupError(f"{part} is not in its checksum list.")
    manifest = _manifest(folder / "manifest.txt")
    return RestoreSource(folder=folder, version=manifest.get("version", ""), created=manifest.get("created", ""))


def restore_data(source: RestoreSource, blobs_dir: Path, db) -> None:
    db.recreate_database()
    db.restore(source.folder / "db.dump")
    if blobs_dir.exists():
        for child in blobs_dir.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
    blobs_dir.mkdir(parents=True, exist_ok=True)
    with tarfile.open(source.folder / "blobs.tar") as tar:
        tar.extractall(blobs_dir, filter="data")
```

- [ ] **Step 4: Run tests** — `uv run pytest tests/test_restore.py tests/test_backup.py -v && uv run ruff check . && uv run ruff format --check .` → PASS.

- [ ] **Step 5: Commit**
```bash
git add backend/src/assayr/backup.py backend/tests/test_restore.py
git commit -m "feat(backend): restore Linux and Windows backups"
```

---

### Task 5: Health wait and offline ClamAV signatures

**Files:**
- Create: `backend/src/assayr/healthcheck.py`, `backend/src/assayr/signatures.py`
- Modify: `backend/src/assayr/cli.py` (commands `healthcheck`)
- Test: `backend/tests/test_healthcheck.py`, `backend/tests/test_signatures.py`

**Interfaces:**
- Produces:
  - `healthcheck.wait_healthy(url: str, timeout_s: float, expect_version: str | None = None, fetch=_fetch, sleep=time.sleep, clock=time.monotonic) -> str` — returns the version; raises `HealthError` with the last problem. `_fetch(url) -> dict` uses an SSL context that skips verification **only** for hosts `localhost`/`127.0.0.1`.
  - `signatures.update_signatures(source: Path, db_dir: Path) -> list[str]` — copies `*.cvd`, `*.cld`, `*.cdiff`, `*.cud` (from a file or a folder) atomically; raises `SignatureError` if none found. Returns copied file names.
  - CLI: `assayr healthcheck --url URL [--timeout 180] [--expect-version V]`.

- [ ] **Step 1: Failing tests**

`backend/tests/test_healthcheck.py`:
```python
import pytest

from assayr.healthcheck import HealthError, wait_healthy


class Clock:
    def __init__(self):
        self.t = 0.0

    def now(self):
        return self.t

    def sleep(self, s):
        self.t += s


def test_returns_when_healthy_after_retries():
    replies = iter([OSError("refused"), {"status": "starting"}, {"status": "ok", "version": "0.3.0"}])

    def fetch(url):
        reply = next(replies)
        if isinstance(reply, Exception):
            raise reply
        return reply

    clock = Clock()
    assert wait_healthy("https://localhost/api/v1/healthz", 60, "0.3.0", fetch, clock.sleep, clock.now) == "0.3.0"


def test_wrong_version_times_out_with_reason():
    clock = Clock()
    with pytest.raises(HealthError, match="0.2.0"):
        wait_healthy("u", 10, "0.3.0", lambda u: {"status": "ok", "version": "0.2.0"}, clock.sleep, clock.now)
```

`backend/tests/test_signatures.py`:
```python
import pytest

from assayr.signatures import SignatureError, update_signatures


def test_copies_signature_files_from_folder(tmp_path):
    src = tmp_path / "usb"
    src.mkdir()
    for name in ("main.cvd", "daily.cld", "bytecode.cvd", "readme.txt"):
        (src / name).write_bytes(b"x")
    db = tmp_path / "db"
    assert sorted(update_signatures(src, db)) == ["bytecode.cvd", "daily.cld", "main.cvd"]
    assert not (db / "readme.txt").exists()


def test_single_file(tmp_path):
    f = tmp_path / "daily.cvd"
    f.write_bytes(b"x")
    assert update_signatures(f, tmp_path / "db") == ["daily.cvd"]


def test_nothing_to_copy(tmp_path):
    with pytest.raises(SignatureError):
        update_signatures(tmp_path, tmp_path / "db")
```

- [ ] **Step 2: Run to verify failure** — `uv run pytest tests/test_healthcheck.py tests/test_signatures.py -v` → FAIL.

- [ ] **Step 3: Implement**

`backend/src/assayr/healthcheck.py`:
```python
"""Wait until Assayr answers its health endpoint."""

import json
import ssl
import time
import urllib.request
from urllib.parse import urlsplit


class HealthError(Exception):
    pass


def _fetch(url: str) -> dict:
    context = ssl.create_default_context()
    if urlsplit(url).hostname in ("localhost", "127.0.0.1"):
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE  # local self-signed certificate
    with urllib.request.urlopen(url, timeout=5, context=context) as response:  # noqa: S310
        return json.loads(response.read().decode())


def wait_healthy(url, timeout_s, expect_version=None, fetch=_fetch, sleep=time.sleep, clock=time.monotonic) -> str:
    deadline = clock() + timeout_s
    problem = "no answer"
    while True:
        try:
            body = fetch(url)
            if body.get("status") == "ok" and (expect_version is None or body.get("version") == expect_version):
                return body.get("version", "")
            problem = f"answered {body}"
        except (OSError, ValueError) as exc:
            problem = str(exc)
        if clock() >= deadline:
            raise HealthError(f"Assayr did not become healthy at {url} within {int(timeout_s)} s: {problem}")
        sleep(2)
```

`backend/src/assayr/signatures.py`:
```python
"""Offline ClamAV signature updates: copy .cvd/.cld/.cdiff/.cud files into the database folder."""

import os
import shutil
from pathlib import Path

SUFFIXES = {".cvd", ".cld", ".cdiff", ".cud"}


class SignatureError(Exception):
    pass


def update_signatures(source: Path, db_dir: Path) -> list[str]:
    files = [source] if source.is_file() else sorted(p for p in source.iterdir() if p.is_file())
    files = [p for p in files if p.suffix.lower() in SUFFIXES]
    if not files:
        raise SignatureError(f"No ClamAV signature files (.cvd, .cld, .cdiff, .cud) found in {source}.")
    db_dir.mkdir(parents=True, exist_ok=True)
    for f in files:
        tmp = db_dir / f".{f.name}.tmp"
        shutil.copyfile(f, tmp)
        os.replace(tmp, db_dir / f.name)
    return [f.name for f in files]
```

CLI in `cli.py`:
```python
from assayr.healthcheck import HealthError, wait_healthy


@app.command()
def healthcheck(
    url: str = typer.Option(...),
    timeout: float = typer.Option(180.0),
    expect_version: str | None = typer.Option(None),
) -> None:
    """Wait until Assayr answers its health endpoint (exit 1 on timeout)."""
    try:
        found = wait_healthy(url, timeout, expect_version)
    except HealthError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc
    typer.echo(f"Assayr {found} is healthy.")
```

- [ ] **Step 4: Run tests** — `uv run pytest -q && uv run ruff check . && uv run ruff format --check .` → PASS.

- [ ] **Step 5: Commit**
```bash
git add backend/src/assayr/healthcheck.py backend/src/assayr/signatures.py backend/src/assayr/cli.py backend/tests/test_healthcheck.py backend/tests/test_signatures.py
git commit -m "feat(backend): health wait and offline signature update"
```

---

### Task 6: Windows layout and config rendering

**Files:**
- Create: `backend/src/assayr/windows/__init__.py` (empty docstring), `layout.py`, `render.py`
- Test: `backend/tests/windows/__init__.py`, `backend/tests/windows/test_layout.py`, `backend/tests/windows/test_render.py`

**Interfaces:**
- Produces:
```python
# layout.py
@dataclass
class InstallConfig:
    install_dir: Path
    data_dir: Path
    hostname: str
    org_name: str
    https_port: int = 443
    http_port: int = 80
    web_mode: str = "https"          # "https" | "http"
    behind_tls_proxy: bool = False
    malware_scan: bool = True
    pg_port: int = 5432
    api_port: int = 8000
    version: str = ""
    # derived paths (properties): python_exe, pg_bin, caddy_exe, clamd_exe, web_root, services_dir,
    # db_dir, blobs_dir, certs_dir, clamav_db_dir, backups_dir, logs_dir, env_file, caddyfile,
    # clamd_conf, install_json, install_log, health_url
    def save(self) -> None            # writes data_dir/install.json
    @classmethod
    def load(cls, data_dir: Path) -> "InstallConfig"

SERVICES: tuple[str, ...] = ("AssayrDb", "AssayrClamAV", "AssayrApi", "AssayrWorker", "AssayrWeb")
def active_services(cfg) -> list[str]   # omits AssayrClamAV when malware_scan is False

# render.py
def render_env(cfg: InstallConfig, db_password: str) -> str
def render_caddyfile(cfg: InstallConfig) -> str
def render_clamd_conf(cfg: InstallConfig) -> str
def render_service_xml(cfg: InstallConfig, service: str) -> str
def database_url(cfg: InstallConfig, db_password: str) -> str
```

- [ ] **Step 1: Failing tests**

`backend/tests/windows/test_layout.py`:
```python
from pathlib import PureWindowsPath  # noqa: F401  (documentation of intent)

from assayr.windows.layout import InstallConfig, active_services


def cfg(tmp_path, **kw):
    return InstallConfig(install_dir=tmp_path / "Program Files" / "Assayr", data_dir=tmp_path / "Assayr Data",
                         hostname="grc.example.local", org_name="Acme & Sons", **kw)


def test_round_trip(tmp_path):
    c = cfg(tmp_path, https_port=8443, version="0.3.0")
    c.data_dir.mkdir(parents=True)
    c.save()
    assert InstallConfig.load(c.data_dir) == c


def test_paths(tmp_path):
    c = cfg(tmp_path)
    assert c.python_exe == c.install_dir / "python" / "python.exe"
    assert c.pg_bin == c.install_dir / "pgsql" / "bin"
    assert c.env_file == c.data_dir / "assayr.env"
    assert c.health_url == "https://localhost:443/api/v1/healthz"
    assert cfg(tmp_path, web_mode="http", http_port=8080).health_url == "http://localhost:8080/api/v1/healthz"


def test_services_without_scan(tmp_path):
    assert "AssayrClamAV" not in active_services(cfg(tmp_path, malware_scan=False))
    assert active_services(cfg(tmp_path))[0] == "AssayrDb"
```

`backend/tests/windows/test_render.py`:
```python
import xml.etree.ElementTree as ET
from urllib.parse import unquote, urlsplit

from assayr.windows.layout import InstallConfig
from assayr.windows.render import (
    database_url, render_caddyfile, render_clamd_conf, render_env, render_service_xml,
)

PW = 'a "quoted" p%ss & ^word'


def cfg(tmp_path, **kw):
    return InstallConfig(install_dir=tmp_path / "Program Files" / "Assayr", data_dir=tmp_path / "Assayr Data",
                         hostname="grc.example.local", org_name='Acme "Bank" & Co', version="0.3.0", **kw)


def parse_env(text):
    from dotenv import dotenv_values  # pydantic-settings dependency
    import io
    return dotenv_values(stream=io.StringIO(text))


def test_env_round_trips_awkward_values(tmp_path):
    c = cfg(tmp_path)
    values = parse_env(render_env(c, PW))
    assert values["ASSAYR_ORG_NAME"] == 'Acme "Bank" & Co'
    assert values["POSTGRES_PASSWORD"] == PW
    url = urlsplit(values["ASSAYR_DATABASE_URL"].replace("postgresql+pg8000", "postgresql"))
    assert unquote(url.password) == PW and url.port == 5432
    assert values["ASSAYR_STORAGE_DIR"] == str(c.blobs_dir)
    assert values["ASSAYR_CLAMAV_HOST"] == "127.0.0.1"
    assert values["ASSAYR_SECURE_COOKIES"] == "true"


def test_env_without_scan_has_no_clamav(tmp_path):
    assert parse_env(render_env(cfg(tmp_path, malware_scan=False), "x"))["ASSAYR_CLAMAV_HOST"] == ""


def test_http_mode_cookies(tmp_path):
    assert parse_env(render_env(cfg(tmp_path, web_mode="http"), "x"))["ASSAYR_SECURE_COOKIES"] == "false"
    behind = cfg(tmp_path, web_mode="http", behind_tls_proxy=True)
    assert parse_env(render_env(behind, "x"))["ASSAYR_SECURE_COOKIES"] == "true"


def test_caddyfile_https(tmp_path):
    c = cfg(tmp_path, https_port=8443, http_port=8080)
    text = render_caddyfile(c)
    assert ":8443 {" in text and ":8080 {" in text
    assert f'tls "{(c.certs_dir / "tls.crt").as_posix()}" "{(c.certs_dir / "tls.key").as_posix()}"' in text
    assert "redir https://{host}:8443{uri} permanent" in text
    assert "reverse_proxy 127.0.0.1:8000" in text
    assert f'root * "{c.web_root.as_posix()}"' in text
    assert "Content-Security-Policy" in text and "admin off" in text


def test_caddyfile_http_only(tmp_path):
    text = render_caddyfile(cfg(tmp_path, web_mode="http", http_port=8080))
    assert ":8080 {" in text and "tls " not in text and "redir" not in text


def test_clamd_conf(tmp_path):
    c = cfg(tmp_path)
    text = render_clamd_conf(c)
    assert "TCPSocket 3310" in text and "TCPAddr 127.0.0.1" in text
    assert f'DatabaseDirectory "{c.clamav_db_dir}"' in text


def test_service_xml_quotes_paths_and_sets_env_file(tmp_path):
    c = cfg(tmp_path)
    root = ET.fromstring(render_service_xml(c, "AssayrApi"))
    assert root.findtext("id") == "AssayrApi"
    assert root.findtext("executable") == str(c.python_exe)
    args = root.findtext("arguments")
    assert "-m uvicorn assayr.main:create_app --factory --host 127.0.0.1 --port 8000" in args
    envs = {e.get("name"): e.get("value") for e in root.findall("env")}
    assert envs["ASSAYR_ENV_FILE"] == str(c.env_file)
    assert [d.text for d in root.findall("depend")] == ["AssayrDb"]
    assert root.findtext("startmode") == "Automatic"
    assert root.find("onfailure") is not None
    assert root.findtext("logpath") == str(c.logs_dir)


def test_db_service(tmp_path):
    c = cfg(tmp_path)
    root = ET.fromstring(render_service_xml(c, "AssayrDb"))
    assert root.findtext("executable") == str(c.pg_bin / "postgres.exe")
    assert f'-D "{c.db_dir}"' in root.findtext("arguments")
    assert "-p 5432" in root.findtext("arguments")


def test_worker_depends_on_clamav_only_when_scanning(tmp_path):
    with_scan = ET.fromstring(render_service_xml(cfg(tmp_path), "AssayrWorker"))
    without = ET.fromstring(render_service_xml(cfg(tmp_path, malware_scan=False), "AssayrWorker"))
    assert [d.text for d in with_scan.findall("depend")] == ["AssayrDb", "AssayrClamAV"]
    assert [d.text for d in without.findall("depend")] == ["AssayrDb"]
```

- [ ] **Step 2: Run to verify failure** — `uv run pytest tests/windows -v` → FAIL.

- [ ] **Step 3: Implement**

`backend/src/assayr/windows/__init__.py`:
```python
"""Native Windows installation: layout, rendered configuration, services and provisioning."""
```

`backend/src/assayr/windows/layout.py`:
```python
import json
from dataclasses import asdict, dataclass, fields
from pathlib import Path

SERVICES: tuple[str, ...] = ("AssayrDb", "AssayrClamAV", "AssayrApi", "AssayrWorker", "AssayrWeb")


@dataclass
class InstallConfig:
    install_dir: Path
    data_dir: Path
    hostname: str
    org_name: str
    https_port: int = 443
    http_port: int = 80
    web_mode: str = "https"
    behind_tls_proxy: bool = False
    malware_scan: bool = True
    pg_port: int = 5432
    api_port: int = 8000
    version: str = ""

    def __post_init__(self) -> None:
        self.install_dir = Path(self.install_dir)
        self.data_dir = Path(self.data_dir)

    python_exe = property(lambda self: self.install_dir / "python" / "python.exe")
    pg_bin = property(lambda self: self.install_dir / "pgsql" / "bin")
    caddy_exe = property(lambda self: self.install_dir / "caddy" / "caddy.exe")
    clamd_exe = property(lambda self: self.install_dir / "clamav" / "clamd.exe")
    bundled_signatures = property(lambda self: self.install_dir / "clamav" / "database")
    web_root = property(lambda self: self.install_dir / "web")
    services_dir = property(lambda self: self.install_dir / "services")
    db_dir = property(lambda self: self.data_dir / "db")
    blobs_dir = property(lambda self: self.data_dir / "blobs")
    certs_dir = property(lambda self: self.data_dir / "certs")
    clamav_db_dir = property(lambda self: self.data_dir / "clamav")
    backups_dir = property(lambda self: self.data_dir / "backups")
    logs_dir = property(lambda self: self.data_dir / "logs")
    license_dir = property(lambda self: self.data_dir / "license")
    env_file = property(lambda self: self.data_dir / "assayr.env")
    caddyfile = property(lambda self: self.data_dir / "Caddyfile")
    clamd_conf = property(lambda self: self.data_dir / "clamd.conf")
    install_json = property(lambda self: self.data_dir / "install.json")
    install_log = property(lambda self: self.data_dir / "install.log")

    @property
    def health_url(self) -> str:
        if self.web_mode == "http":
            return f"http://localhost:{self.http_port}/api/v1/healthz"
        return f"https://localhost:{self.https_port}/api/v1/healthz"

    def save(self) -> None:
        data = {k: str(v) if isinstance(v, Path) else v for k, v in asdict(self).items()}
        self.install_json.write_text(json.dumps(data, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, data_dir: Path) -> "InstallConfig":
        raw = json.loads((Path(data_dir) / "install.json").read_text(encoding="utf-8"))
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in raw.items() if k in known})


def active_services(cfg: InstallConfig) -> list[str]:
    return [s for s in SERVICES if cfg.malware_scan or s != "AssayrClamAV"]
```

`backend/src/assayr/windows/render.py`:
```python
"""Text of the files a Windows installation needs. Pure functions: easy to test on any OS."""

from urllib.parse import quote
from xml.sax.saxutils import escape, quoteattr

from assayr.windows.layout import InstallConfig

_SITE = """\
encode zstd gzip
header {{
	X-Content-Type-Options nosniff
	X-Frame-Options DENY
	Referrer-Policy no-referrer
	Permissions-Policy "camera=(), microphone=(), geolocation=()"
	Content-Security-Policy "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; font-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
	-Server
}}
handle /healthz {{
	respond "ok" 200
}}
handle /api/* {{
	request_body {{
		max_size 110MB
	}}
	reverse_proxy 127.0.0.1:{api_port}
}}
handle {{
	root * "{web_root}"
	try_files {{path}} /index.html
	file_server
}}
"""


def _env_value(value: str) -> str:
    """Double-quoted dotenv value: python-dotenv unescapes \\\\ and \\" inside double quotes."""
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def database_url(cfg: InstallConfig, db_password: str) -> str:
    return f"postgresql+pg8000://assayr:{quote(db_password, safe='')}@127.0.0.1:{cfg.pg_port}/assayr"


def render_env(cfg: InstallConfig, db_password: str) -> str:
    secure = cfg.web_mode == "https" or cfg.behind_tls_proxy
    values = {
        "ASSAYR_VERSION": cfg.version,
        "POSTGRES_PASSWORD": db_password,
        "ASSAYR_DATABASE_URL": database_url(cfg, db_password),
        "ASSAYR_HOSTNAME": cfg.hostname,
        "ASSAYR_ORG_NAME": cfg.org_name,
        "ASSAYR_WEB_MODE": cfg.web_mode,
        "ASSAYR_HTTPS_PORT": str(cfg.https_port),
        "ASSAYR_HTTP_PORT": str(cfg.http_port),
        "ASSAYR_SECURE_COOKIES": "true" if secure else "false",
        "ASSAYR_MALWARE_SCAN": "true" if cfg.malware_scan else "false",
        "ASSAYR_CLAMAV_HOST": "127.0.0.1" if cfg.malware_scan else "",
        "ASSAYR_CLAMAV_PORT": "3310",
        "ASSAYR_STORAGE_DIR": str(cfg.blobs_dir),
    }
    lines = ["# Assayr settings. Restart Assayr after changing this file."]
    lines += [f"{k}={_env_value(v)}" for k, v in values.items()]
    return "\n".join(lines) + "\n"


def render_caddyfile(cfg: InstallConfig) -> str:
    site = _SITE.format(api_port=cfg.api_port, web_root=cfg.web_root.as_posix())
    head = "{\n\tadmin off\n\tauto_https off\n" + (
        f"\tdefault_sni {cfg.hostname}\n" if cfg.web_mode == "https" else ""
    ) + "}\n\n"
    if cfg.web_mode == "http":
        return head + f":{cfg.http_port} {{\n{_indent(site)}}}\n"
    crt, key = (cfg.certs_dir / "tls.crt").as_posix(), (cfg.certs_dir / "tls.key").as_posix()
    return (
        head
        + f':{cfg.https_port} {{\n\ttls "{crt}" "{key}"\n{_indent(site)}}}\n\n'
        + f":{cfg.http_port} {{\n\thandle /healthz {{\n\t\trespond \"ok\" 200\n\t}}\n"
        + f"\thandle {{\n\t\tredir https://{{host}}:{cfg.https_port}{{uri}} permanent\n\t}}\n}}\n"
    )


def _indent(text: str) -> str:
    return "".join(f"\t{line}\n" if line else "\n" for line in text.splitlines())


def render_clamd_conf(cfg: InstallConfig) -> str:
    return (
        "TCPSocket 3310\nTCPAddr 127.0.0.1\n"
        f'DatabaseDirectory "{cfg.clamav_db_dir}"\n'
        f'LogFile "{cfg.logs_dir / "clamd.log"}"\nLogFileMaxSize 10M\nLogRotate yes\n'
        "StreamMaxLength 110M\nMaxFileSize 110M\nMaxScanSize 400M\n"
    )


def _service(cfg: InstallConfig, service: str) -> tuple[str, str, str, list[str], str]:
    """(display name, executable, arguments, dependencies, description)."""
    py = cfg.python_exe
    if service == "AssayrDb":
        return ("Assayr Database", str(cfg.pg_bin / "postgres.exe"),
                f'-D "{cfg.db_dir}" -p {cfg.pg_port} -c listen_addresses=127.0.0.1', [], "PostgreSQL for Assayr")
    if service == "AssayrClamAV":
        return ("Assayr ClamAV", str(cfg.clamd_exe), f'--foreground --config-file="{cfg.clamd_conf}"', [],
                "Malware scanning for uploaded evidence")
    if service == "AssayrApi":
        return ("Assayr API", str(py),
                f"-m uvicorn assayr.main:create_app --factory --host 127.0.0.1 --port {cfg.api_port} "
                "--proxy-headers --forwarded-allow-ips 127.0.0.1", ["AssayrDb"], "Assayr web API")
    if service == "AssayrWorker":
        deps = ["AssayrDb"] + (["AssayrClamAV"] if cfg.malware_scan else [])
        return ("Assayr Worker", str(py), "-m assayr worker", deps, "Assayr evidence verification")
    if service == "AssayrWeb":
        return ("Assayr Web", str(cfg.caddy_exe), f'run --config "{cfg.caddyfile}" --adapter caddyfile',
                ["AssayrApi"], "Assayr HTTPS front end")
    raise ValueError(service)


def render_service_xml(cfg: InstallConfig, service: str) -> str:
    name, exe, args, deps, description = _service(cfg, service)
    depends = "".join(f"  <depend>{d}</depend>\n" for d in deps)
    delayed = "" if service in ("AssayrDb", "AssayrClamAV") else "  <delayedAutoStart>true</delayedAutoStart>\n"
    return (
        "<service>\n"
        f"  <id>{service}</id>\n  <name>{escape(name)}</name>\n  <description>{escape(description)}</description>\n"
        f"  <executable>{escape(exe)}</executable>\n  <arguments>{escape(args)}</arguments>\n"
        f"  <workingdirectory>{escape(str(cfg.data_dir))}</workingdirectory>\n"
        f"  <env name=\"ASSAYR_ENV_FILE\" value={quoteattr(str(cfg.env_file))}/>\n"
        "  <env name=\"PYTHONUTF8\" value=\"1\"/>\n"
        f"{depends}  <startmode>Automatic</startmode>\n{delayed}"
        "  <stoptimeout>60 sec</stoptimeout>\n"
        "  <onfailure action=\"restart\" delay=\"10 sec\"/>\n  <onfailure action=\"restart\" delay=\"10 sec\"/>\n"
        "  <onfailure action=\"restart\" delay=\"10 sec\"/>\n  <resetfailure>1 hour</resetfailure>\n"
        f"  <logpath>{escape(str(cfg.logs_dir))}</logpath>\n"
        "  <log mode=\"roll-by-size\"><sizeThreshold>10240</sizeThreshold><keepFiles>5</keepFiles></log>\n"
        "</service>\n"
    )
```

Note: `python-dotenv` is already a dependency of `pydantic-settings`; the env test imports it.

- [ ] **Step 4: Run tests** — `uv run pytest tests/windows -v && uv run ruff check . && uv run ruff format --check .` → PASS. Also run `uv run pytest tests/test_version_config.py -v` to confirm the rendered env file loads through `get_settings` (add this test to `test_render.py`):
```python
def test_rendered_env_loads_into_settings(tmp_path, monkeypatch):
    from assayr.config import get_settings
    c = cfg(tmp_path)
    c.data_dir.mkdir(parents=True)
    c.env_file.write_text(render_env(c, PW), encoding="utf-8")
    monkeypatch.setenv("ASSAYR_ENV_FILE", str(c.env_file))
    for k in ("ASSAYR_DATABASE_URL", "ASSAYR_ORG_NAME", "ASSAYR_STORAGE_DIR"):
        monkeypatch.delenv(k, raising=False)
    get_settings.cache_clear()
    try:
        s = get_settings()
        assert s.org_name == 'Acme "Bank" & Co' and s.storage_dir == str(c.blobs_dir)
    finally:
        get_settings.cache_clear()
```

- [ ] **Step 5: Commit**
```bash
git add backend/src/assayr/windows backend/tests/windows
git commit -m "feat(windows): install layout and rendered configuration"
```

---

### Task 7: Runner, services and provisioning (install, upgrade finish, rollback, uninstall)

**Files:**
- Create: `backend/src/assayr/windows/runner.py`, `services.py`, `provision.py`
- Test: `backend/tests/windows/test_services.py`, `backend/tests/windows/test_provision.py`

**Interfaces:**
- Consumes: `InstallConfig`, `active_services`, render functions (Task 6); `generate_self_signed`, `check_pair` (Task 2); `wait_healthy` (Task 5); `create_backup`, `read_backup`, `restore_data`, `BackupSources` (Tasks 3–4); `PgTools`.
- Produces:
```python
# runner.py
class CommandError(Exception): ...
class Runner(Protocol):
    def run(self, args: list[str], *, env: dict[str, str] | None = None, input: str | None = None,
            check: bool = True) -> subprocess.CompletedProcess: ...
class SubprocessRunner:  # logs "RUN <args>" and exit code to a log file; values of SECRET_ENV keys never logged
    def __init__(self, log_path: Path): ...
SECRET_ENV = ("ASSAYR_ADMIN_PASSWORD", "ASSAYR_PFX_PASSWORD", "PGPASSWORD")

# services.py
def register(cfg, runner) -> None        # writes <services_dir>/<id>.xml + <id>.exe copy of WinSW, `<id>.exe install`,
                                         # `sc.exe config <id> obj= "NT SERVICE\<id>"`
def unregister(cfg, runner) -> None      # stop + `<id>.exe uninstall`, ignores "not installed"
def start_all(cfg, runner) / stop_all(cfg, runner)   # dependency order / reverse order via sc.exe
def status(cfg, runner) -> dict[str, str]            # "RUNNING" | "STOPPED" | "NOT INSTALLED" | ...
def account(service: str) -> str                    # 'NT SERVICE\\<service>'

# provision.py
@dataclass
class CertChoice:
    mode: str                 # "self-signed" | "pem" | "pfx"
    cert: Path | None = None  # pem certificate or pfx file
    key: Path | None = None   # pem key
class ProvisionError(Exception): ...
def install(cfg, admin_email: str, admin_password: str, cert: CertChoice, runner, *, pfx_password: str | None = None,
            health_timeout: float = 180.0, wait=wait_healthy, token=secrets.token_urlsafe) -> None
def finish_upgrade(cfg, runner, *, health_timeout=180.0, wait=wait_healthy) -> None
def rollback(cfg, backup: Path, runner) -> None   # run by the OLD program: restore db+blobs, re-register, start
def uninstall(cfg, runner, *, delete_data: bool) -> None
def make_backup(cfg, runner, now) -> Path
```

- [ ] **Step 1: Failing tests**

`backend/tests/windows/test_services.py`:
```python
import subprocess

from assayr.windows import services
from assayr.windows.layout import InstallConfig


class FakeRunner:
    def __init__(self, replies=None):
        self.calls = []
        self.replies = replies or {}

    def run(self, args, *, env=None, input=None, check=True):
        self.calls.append([str(a) for a in args])
        out = self.replies.get(tuple(str(a) for a in args[:3]), "")
        return subprocess.CompletedProcess(args, 0, out, "")


def cfg(tmp_path, **kw):
    c = InstallConfig(tmp_path / "Program Files" / "Assayr", tmp_path / "data", "h", "o", version="0.3.0", **kw)
    (c.services_dir).mkdir(parents=True)
    (c.services_dir / "WinSW-x64.exe").write_bytes(b"MZ")
    return c


def test_register_writes_xml_and_sets_virtual_account(tmp_path):
    c, r = cfg(tmp_path), FakeRunner()
    services.register(c, r)
    assert (c.services_dir / "AssayrApi.xml").exists() and (c.services_dir / "AssayrApi.exe").exists()
    assert [str(c.services_dir / "AssayrApi.exe"), "install"] in r.calls
    assert ["sc.exe", "config", "AssayrApi", "obj=", "NT SERVICE\\AssayrApi"] in r.calls


def test_start_order_and_stop_reverse(tmp_path):
    c, r = cfg(tmp_path, malware_scan=False), FakeRunner()
    services.start_all(c, r)
    services.stop_all(c, r)
    started = [call[2] for call in r.calls if call[:2] == ["sc.exe", "start"]]
    stopped = [call[2] for call in r.calls if call[:2] == ["sc.exe", "stop"]]
    assert started == ["AssayrDb", "AssayrApi", "AssayrWorker", "AssayrWeb"]
    assert stopped == list(reversed(started))


def test_status_parses_sc_query(tmp_path):
    c = cfg(tmp_path)
    r = FakeRunner({("sc.exe", "query", "AssayrDb"): "SERVICE_NAME: AssayrDb\n        STATE              : 4  RUNNING\n"})
    result = services.status(c, r)
    assert result["AssayrDb"] == "RUNNING" and result["AssayrApi"] == "NOT INSTALLED"
```

`backend/tests/windows/test_provision.py`:
```python
import subprocess

import pytest

from assayr.windows import provision
from assayr.windows.layout import InstallConfig
from assayr.windows.provision import CertChoice, ProvisionError


class FakeRunner:
    def __init__(self, fail_on=None):
        self.calls, self.envs, self.inputs, self.fail_on = [], [], [], fail_on

    def run(self, args, *, env=None, input=None, check=True):
        args = [str(a) for a in args]
        self.calls.append(args)
        self.envs.append(env or {})
        self.inputs.append(input)
        if self.fail_on and any(self.fail_on in a for a in args):
            if check:
                raise provision.CommandError(f"{args[0]} failed")
            return subprocess.CompletedProcess(args, 1, "", "boom")
        if args[:2] == ["sc.exe", "query"]:
            return subprocess.CompletedProcess(args, 1060, "", "")
        return subprocess.CompletedProcess(args, 0, "", "")


def make_cfg(tmp_path, **kw):
    c = InstallConfig(tmp_path / "Program Files" / "Assayr", tmp_path / "Assayr Data", "grc.local", "Acme",
                      version="0.3.0", **kw)
    c.services_dir.mkdir(parents=True)
    (c.services_dir / "WinSW-x64.exe").write_bytes(b"MZ")
    c.bundled_signatures.mkdir(parents=True)
    (c.bundled_signatures / "main.cvd").write_bytes(b"sig")
    return c


def run_install(tmp_path, runner=None, **kw):
    c = make_cfg(tmp_path, **kw)
    r = runner or FakeRunner()
    provision.install(c, "admin@acme.com", "a-very-long-password", CertChoice("self-signed"), r,
                      wait=lambda *a, **k: "0.3.0", token=lambda n: 'pw"with%odd&chars')
    return c, r


def flat(r):
    return [" ".join(c) for c in r.calls]


def test_install_order(tmp_path):
    c, r = run_install(tmp_path)
    cmds = flat(r)

    def idx(fragment):
        return next(i for i, cmd in enumerate(cmds) if fragment in cmd)

    assert idx("initdb") < idx("AssayrDb.exe install") < idx("sc.exe start AssayrDb")
    assert idx("sc.exe start AssayrDb") < idx("-m assayr migrate") < idx("-m assayr seed")
    assert idx("-m assayr seed") < idx("-m assayr create-admin") < idx("advfirewall")
    assert idx("advfirewall") < idx("sc.exe start AssayrWeb") < idx("schtasks")
    assert (c.data_dir / "install.json").exists() and (c.certs_dir / "tls.crt").exists()
    assert (c.clamav_db_dir / "main.cvd").exists()


def test_passwords_never_in_arguments(tmp_path):
    c, r = run_install(tmp_path)
    joined = " ".join(flat(r))
    assert "a-very-long-password" not in joined and 'pw"with%odd&chars' not in joined
    admin = next(i for i, cmd in enumerate(r.calls) if "create-admin" in cmd)
    assert r.envs[admin]["ASSAYR_ADMIN_PASSWORD"] == "a-very-long-password"
    initdb = next(i for i, cmd in enumerate(r.calls) if cmd[0].endswith("initdb.exe"))
    assert any("--pwfile" in a for a in r.calls[initdb])


def test_initdb_pwfile_removed(tmp_path):
    c, _ = run_install(tmp_path)
    assert not list(c.data_dir.glob("*.pw"))


def test_firewall_opens_only_web_ports(tmp_path):
    _, r = run_install(tmp_path, https_port=8443, http_port=8080)
    rules = [c for c in r.calls if "advfirewall" in c and "add" in c]
    ports = sorted(next(a for a in c if a.startswith("localport=")) for c in rules)
    assert ports == ["localport=8080", "localport=8443"]


def test_data_dir_acl(tmp_path):
    _, r = run_install(tmp_path)
    icacls = [c for c in r.calls if c[0] == "icacls.exe"]
    assert any("/inheritance:r" in c for c in icacls)
    assert any(any(a.startswith("NT SERVICE\\AssayrDb:") for a in c) for c in icacls)


def test_failure_on_new_data_dir_cleans_up(tmp_path):
    r = FakeRunner(fail_on="create-admin")
    with pytest.raises(ProvisionError, match="create-admin"):
        run_install(tmp_path, runner=r)
    c = make_cfg(tmp_path / "again")
    assert not (tmp_path / "Assayr Data").exists()
    assert any("AssayrDb.exe" in cmd and "uninstall" in cmd for cmd in flat(r))
    # a retry on the same machine succeeds
    run_install(tmp_path)


def test_existing_data_dir_is_kept_on_failure(tmp_path):
    c = make_cfg(tmp_path)
    c.data_dir.mkdir(parents=True)
    (c.data_dir / "keep.txt").write_text("x")
    r = FakeRunner(fail_on="create-admin")
    with pytest.raises(ProvisionError):
        provision.install(c, "a@b.c", "a-very-long-password", CertChoice("self-signed"), r,
                          wait=lambda *a, **k: "0.3.0", token=lambda n: "pw")
    assert (c.data_dir / "keep.txt").exists()


def test_existing_cluster_is_not_reinitialised(tmp_path):
    c = make_cfg(tmp_path)
    (c.db_dir).mkdir(parents=True)
    (c.db_dir / "PG_VERSION").write_text("16")
    c.data_dir.joinpath("assayr.env").write_text('POSTGRES_PASSWORD="old"\n')
    r = FakeRunner()
    provision.install(c, "a@b.c", "a-very-long-password", CertChoice("self-signed"), r,
                      wait=lambda *a, **k: "0.3.0", token=lambda n: "new")
    assert not any(cmd[0].endswith("initdb.exe") for cmd in r.calls)
    assert 'POSTGRES_PASSWORD="old"' in c.env_file.read_text()


def test_uninstall_keeps_data_by_default(tmp_path):
    c, _ = run_install(tmp_path)
    r = FakeRunner()
    provision.uninstall(c, r, delete_data=False)
    assert c.data_dir.exists()
    assert any("advfirewall" in cmd and "delete" in cmd for cmd in flat(r))
    assert any("schtasks" in cmd and "/Delete" in cmd for cmd in flat(r))
    provision.uninstall(c, FakeRunner(), delete_data=True)
    assert not c.data_dir.exists()


def test_finish_upgrade_rerenders_and_migrates(tmp_path):
    c, _ = run_install(tmp_path)
    c.version = "0.4.0"
    r = FakeRunner()
    provision.finish_upgrade(c, r, wait=lambda *a, **k: "0.4.0")
    assert any("-m assayr migrate" in cmd for cmd in flat(r))
    assert "0.4.0" in c.env_file.read_text()
    assert provision.InstallConfig.load(c.data_dir).version == "0.4.0"


def test_finish_upgrade_health_failure_raises(tmp_path):
    c, _ = run_install(tmp_path)

    def unhealthy(*a, **k):
        raise provision.HealthError("down")

    with pytest.raises(ProvisionError, match="down"):
        provision.finish_upgrade(c, FakeRunner(), wait=unhealthy)
```

- [ ] **Step 2: Run to verify failure** — `uv run pytest tests/windows -v` → FAIL.

- [ ] **Step 3: Implement**

`backend/src/assayr/windows/runner.py`:
```python
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

SECRET_ENV = ("ASSAYR_ADMIN_PASSWORD", "ASSAYR_PFX_PASSWORD", "PGPASSWORD")


class CommandError(Exception):
    pass


class Runner(Protocol):
    def run(self, args, *, env=None, input=None, check=True) -> subprocess.CompletedProcess: ...


class SubprocessRunner:
    """Runs commands, appends `RUN <args>` and the exit code to the install log. Never logs env values or stdin."""

    def __init__(self, log_path: Path) -> None:
        self.log_path = log_path

    def _log(self, line: str) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a", encoding="utf-8") as log:
            log.write(f"{datetime.now(UTC):%Y-%m-%dT%H:%M:%SZ} {line}\n")

    def run(self, args, *, env=None, input=None, check=True):
        args = [str(a) for a in args]
        self._log("RUN " + subprocess.list2cmdline(args))
        result = subprocess.run(args, env=env, input=input, capture_output=True, text=True, check=False)  # noqa: S603
        self._log(f"EXIT {result.returncode}")
        if result.stdout.strip():
            self._log(result.stdout.strip()[-4000:])
        if result.stderr.strip():
            self._log(result.stderr.strip()[-4000:])
        if check and result.returncode != 0:
            raise CommandError(f"{Path(args[0]).name} {' '.join(args[1:3])} failed (exit {result.returncode}).")
        return result
```

`backend/src/assayr/windows/services.py`:
```python
import re
import shutil

from assayr.windows.layout import SERVICES, InstallConfig, active_services
from assayr.windows.render import render_service_xml
from assayr.windows.runner import Runner


def account(service: str) -> str:
    return f"NT SERVICE\\{service}"


def register(cfg: InstallConfig, runner: Runner) -> None:
    winsw = cfg.services_dir / "WinSW-x64.exe"
    for service in active_services(cfg):
        (cfg.services_dir / f"{service}.xml").write_text(render_service_xml(cfg, service), encoding="utf-8")
        exe = cfg.services_dir / f"{service}.exe"
        shutil.copyfile(winsw, exe)
        runner.run([exe, "install"])
        runner.run(["sc.exe", "config", service, "obj=", account(service)])


def unregister(cfg: InstallConfig, runner: Runner) -> None:
    for service in reversed(SERVICES):
        runner.run(["sc.exe", "stop", service], check=False)
        exe = cfg.services_dir / f"{service}.exe"
        if exe.exists():
            runner.run([exe, "uninstall"], check=False)
        else:
            runner.run(["sc.exe", "delete", service], check=False)


def start_all(cfg: InstallConfig, runner: Runner) -> None:
    for service in active_services(cfg):
        runner.run(["sc.exe", "start", service], check=False)


def stop_all(cfg: InstallConfig, runner: Runner) -> None:
    for service in reversed(active_services(cfg)):
        runner.run(["sc.exe", "stop", service], check=False)


_STATE = re.compile(r"STATE\s*:\s*\d+\s+(\w+)")


def status(cfg: InstallConfig, runner: Runner) -> dict[str, str]:
    result = {}
    for service in active_services(cfg):
        out = runner.run(["sc.exe", "query", service], check=False).stdout or ""
        match = _STATE.search(out)
        result[service] = match.group(1) if match else "NOT INSTALLED"
    return result
```

Add `wait_running(cfg, runner, service, timeout_s=60, sleep=time.sleep)` to `services.py` (polls `status` until `RUNNING`; raises `CommandError(f"{service} did not start; see {cfg.logs_dir}")`). Provision calls it after starting `AssayrDb` (FakeRunner returns empty query output, so tests pass `services.wait_running` through a module-level hook `provision.WAIT_RUNNING` they set to a no-op in a fixture):

```python
# services.py
import time

def wait_running(cfg, runner, service, timeout_s=60, sleep=time.sleep):
    for _ in range(int(timeout_s)):
        out = runner.run(["sc.exe", "query", service], check=False).stdout or ""
        match = _STATE.search(out)
        if match and match.group(1) == "RUNNING":
            return
        sleep(1)
    raise CommandError(f"{service} did not start; see {cfg.logs_dir}")
```
(import `CommandError` from `runner`). In `test_provision.py` add at the top:
```python
@pytest.fixture(autouse=True)
def no_wait(monkeypatch):
    monkeypatch.setattr(provision.services, "wait_running", lambda *a, **k: None)
```

`backend/src/assayr/windows/provision.py`:
```python
"""Install, upgrade, roll back and uninstall Assayr as Windows services."""

import os
import secrets
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from assayr.backup import BackupSources, create_backup, read_backup, restore_data
from assayr.certs import CertError, check_pair, generate_self_signed, pfx_to_pem
from assayr.healthcheck import HealthError, wait_healthy
from assayr.pgtools import PgTools
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
    mode: str
    cert: Path | None = None
    key: Path | None = None


def _env_password(cfg: InstallConfig) -> str | None:
    if not cfg.env_file.exists():
        return None
    from dotenv import dotenv_values

    return dotenv_values(cfg.env_file).get("POSTGRES_PASSWORD")


def _child_env(cfg: InstallConfig, **extra: str) -> dict[str, str]:
    return {**os.environ, "ASSAYR_ENV_FILE": str(cfg.env_file), "PYTHONUTF8": "1", **extra}


def _assayr(cfg, runner, *args, **extra_env):
    runner.run([cfg.python_exe, "-m", "assayr", *args], env=_child_env(cfg, **extra_env))


def _secure_data_dir(cfg: InstallConfig, runner) -> None:
    grants = ["*S-1-5-32-544:(OI)(CI)F", "*S-1-5-18:(OI)(CI)F"]  # Administrators, SYSTEM
    grants += [f"{services.account(s)}:(OI)(CI)M" for s in SERVICES]
    runner.run(["icacls.exe", cfg.data_dir, "/inheritance:r", "/grant:r", *grants, "/T", "/C", "/Q"])


def _write_files(cfg: InstallConfig, db_password: str) -> None:
    cfg.env_file.write_text(render_env(cfg, db_password), encoding="utf-8")
    cfg.caddyfile.write_text(render_caddyfile(cfg), encoding="utf-8")
    cfg.clamd_conf.write_text(render_clamd_conf(cfg), encoding="utf-8")
    cfg.save()


def _certs(cfg: InstallConfig, cert: CertChoice, pfx_password: str | None) -> None:
    crt, key = cfg.certs_dir / "tls.crt", cfg.certs_dir / "tls.key"
    if cfg.web_mode == "http":
        return
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
    except (CertError, OSError) as exc:
        raise ProvisionError(f"Certificate: {exc}") from exc


def _initdb(cfg: InstallConfig, runner, db_password: str) -> None:
    if (cfg.db_dir / "PG_VERSION").exists():
        return
    pwfile = cfg.data_dir / ".initdb.pw"
    pwfile.write_text(db_password, encoding="utf-8")
    try:
        runner.run([cfg.pg_bin / "initdb.exe", "-D", cfg.db_dir, "-U", "assayr", "--pwfile", pwfile,
                    "-E", "UTF8", "--locale=C", "--auth=scram-sha-256"])
    finally:
        pwfile.unlink(missing_ok=True)
    runner.run([cfg.pg_bin / "createdb.exe", "-h", "127.0.0.1", "-p", str(cfg.pg_port), "-U", "assayr", "assayr"],
               env=_child_env(cfg, PGPASSWORD=db_password), check=False)


def _firewall(cfg: InstallConfig, runner, add: bool) -> None:
    ports = [cfg.http_port] if cfg.web_mode == "http" else [cfg.https_port, cfg.http_port]
    for port in ports:
        name = f"Assayr ({port})"
        runner.run(["netsh", "advfirewall", "firewall", "delete", "rule", f"name={name}"], check=False)
        if add:
            runner.run(["netsh", "advfirewall", "firewall", "add", "rule", f"name={name}", "dir=in",
                        "action=allow", "protocol=TCP", f"localport={port}"])


def _schedule_backup(cfg: InstallConfig, runner) -> None:
    admin = cfg.install_dir / "assayr-admin.cmd"
    runner.run(["schtasks", "/Create", "/F", "/TN", TASK_NAME, "/SC", "DAILY", "/ST", "02:00", "/RU", "SYSTEM",
                "/TR", f'"{admin}" backup --scheduled'])


def _copy_signatures(cfg: InstallConfig) -> None:
    if cfg.malware_scan and cfg.bundled_signatures.is_dir() and not any(cfg.clamav_db_dir.glob("*.c?d")):
        cfg.clamav_db_dir.mkdir(parents=True, exist_ok=True)
        for f in cfg.bundled_signatures.iterdir():
            shutil.copyfile(f, cfg.clamav_db_dir / f.name)


def install(cfg, admin_email, admin_password, cert, runner, *, pfx_password=None, health_timeout=180.0,
            wait=wait_healthy, token=secrets.token_urlsafe) -> None:
    new_data_dir = not cfg.data_dir.exists()
    try:
        for d in (cfg.data_dir, cfg.blobs_dir, cfg.backups_dir, cfg.logs_dir, cfg.certs_dir, cfg.clamav_db_dir):
            d.mkdir(parents=True, exist_ok=True)
        db_password = _env_password(cfg) or token(32)
        _certs(cfg, cert, pfx_password)
        _copy_signatures(cfg)
        _write_files(cfg, db_password)
        _secure_data_dir(cfg, runner)
        _initdb(cfg, runner, db_password)
        services.register(cfg, runner)
        runner.run(["sc.exe", "start", "AssayrDb"], check=False)
        services.wait_running(cfg, runner, "AssayrDb")
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


def finish_upgrade(cfg, runner, *, health_timeout=180.0, wait=wait_healthy) -> None:
    try:
        password = _env_password(cfg)
        if not password:
            raise ProvisionError(f"{cfg.env_file} has no database password.")
        _copy_signatures(cfg)
        _write_files(cfg, password)
        services.unregister(cfg, runner)
        services.register(cfg, runner)
        runner.run(["sc.exe", "start", "AssayrDb"], check=False)
        services.wait_running(cfg, runner, "AssayrDb")
        _assayr(cfg, runner, "migrate")
        services.start_all(cfg, runner)
        _schedule_backup(cfg, runner)
        wait(cfg.health_url, health_timeout, cfg.version)
    except (CommandError, HealthError, OSError) as exc:
        raise ProvisionError(f"Upgrade failed: {exc}") from exc


def make_backup(cfg: InstallConfig, runner, now=None) -> Path:
    password = _env_password(cfg) or ""
    db = PgTools(cfg.pg_bin, database_url(cfg, password))
    sources = BackupSources(cfg.blobs_dir, cfg.env_file, cfg.certs_dir, cfg.license_dir)
    return create_backup(cfg.backups_dir, cfg.version, sources, db.dump, now or datetime.now(UTC))


def rollback(cfg: InstallConfig, backup: Path, runner) -> None:
    """Run by the restored (old) program: put the pre-upgrade database and files back, then start."""
    services.stop_all(cfg, runner)
    services.unregister(cfg, runner)
    services.register(cfg, runner)
    runner.run(["sc.exe", "start", "AssayrDb"], check=False)
    services.wait_running(cfg, runner, "AssayrDb")
    work = cfg.data_dir / ".restore"
    shutil.rmtree(work, ignore_errors=True)
    try:
        source = read_backup(backup, work)
        restore_data(source, cfg.blobs_dir, PgTools(cfg.pg_bin, database_url(cfg, _env_password(cfg) or "")))
    finally:
        shutil.rmtree(work, ignore_errors=True)
    _write_files(cfg, _env_password(cfg) or "")
    services.start_all(cfg, runner)


def uninstall(cfg: InstallConfig, runner, *, delete_data: bool) -> None:
    services.unregister(cfg, runner)
    _firewall(cfg, runner, add=False)
    runner.run(["schtasks", "/Delete", "/F", "/TN", TASK_NAME], check=False)
    if delete_data:
        shutil.rmtree(cfg.data_dir, ignore_errors=True)
```

Note for `test_existing_cluster_is_not_reinitialised`: `_env_password` reads the existing `POSTGRES_PASSWORD`, `_write_files` re-renders the env with the same value (`'POSTGRES_PASSWORD="old"'` is exactly what `render_env` produces).

- [ ] **Step 4: Run tests** — `uv run pytest tests/windows -v && uv run pytest -q && uv run ruff check . && uv run ruff format --check .` → PASS.

- [ ] **Step 5: Commit**
```bash
git add backend/src/assayr/windows backend/tests/windows
git commit -m "feat(windows): services and provisioning with cleanup, upgrade and rollback"
```

---

### Task 8: `assayr win` command line

**Files:**
- Create: `backend/src/assayr/windows/cli.py`
- Modify: `backend/src/assayr/cli.py` (`app.add_typer(win_app, name="win")`)
- Test: `backend/tests/windows/test_win_cli.py`

**Interfaces:**
- Consumes: everything in Task 7.
- Produces (all read `install.json` from `--data-dir`, default `C:\ProgramData\Assayr`, or `ASSAYR_DATA_DIR`):
  - `assayr win install --answers FILE.json` (keys: `install_dir, data_dir, hostname, org_name, https_port, http_port, web_mode, behind_tls_proxy, malware_scan, version, admin_email, cert_mode, cert_file, key_file`; passwords from `ASSAYR_ADMIN_PASSWORD`, `ASSAYR_PFX_PASSWORD`). Exit 0 / 1 with the reason on stderr.
  - `assayr win prepare-upgrade --data-dir D --backup-out FILE` — stops services after taking a backup; writes the backup path to `FILE` (used by Inno before replacing files).
  - `assayr win finish-upgrade --data-dir D --version V`
  - `assayr win rollback --data-dir D --backup FILE`
  - `assayr win uninstall --data-dir D [--delete-data]`
  - `assayr win status|start|stop|restart [--data-dir D]`, `assayr win logs [api|worker|web|db|clamav] [--lines 200]` (prints the tail of `<logs>/<Service>.out.log` and `.err.log`)
  - `assayr win backup [--scheduled]` (scheduled: prune to newest 14 files named `assayr-*-scheduled*`; scheduled backups are created then renamed with a `-scheduled` suffix before `.tar.gz`), `assayr win restore FILE [--yes]`, `assayr win update-signatures PATH`, `assayr win create-admin --email E`.

- [ ] **Step 1: Failing tests** — `backend/tests/windows/test_win_cli.py`:
```python
import json

from typer.testing import CliRunner

from assayr.cli import app
from assayr.windows import cli as wincli
from assayr.windows.layout import InstallConfig

runner = CliRunner()


class Recorder:
    def __init__(self):
        self.called = {}

    def __getattr__(self, name):
        def record(*args, **kwargs):
            self.called[name] = (args, kwargs)
            return getattr(self, "_ret", None)
        return record


def test_install_reads_answers_and_env_password(tmp_path, monkeypatch):
    rec = Recorder()
    monkeypatch.setattr(wincli, "provision", rec)
    monkeypatch.setattr(wincli, "SubprocessRunner", lambda path: "runner")
    answers = tmp_path / "answers.json"
    answers.write_text(json.dumps({
        "install_dir": str(tmp_path / "p"), "data_dir": str(tmp_path / "d"), "hostname": "h",
        "org_name": "Acme", "https_port": 443, "http_port": 80, "web_mode": "https",
        "behind_tls_proxy": False, "malware_scan": True, "version": "0.3.0",
        "admin_email": "a@b.c", "cert_mode": "self-signed", "cert_file": "", "key_file": "",
    }))
    result = runner.invoke(app, ["win", "install", "--answers", str(answers)],
                           env={"ASSAYR_ADMIN_PASSWORD": "a-very-long-password"})
    assert result.exit_code == 0, result.output
    args, kwargs = rec.called["install"]
    assert args[1] == "a@b.c" and args[2] == "a-very-long-password"


def test_install_without_password_fails(tmp_path, monkeypatch):
    answers = tmp_path / "a.json"
    answers.write_text("{}")
    result = runner.invoke(app, ["win", "install", "--answers", str(answers)], env={"ASSAYR_ADMIN_PASSWORD": ""})
    assert result.exit_code == 1 and "ASSAYR_ADMIN_PASSWORD" in result.output


def test_status_prints_each_service(tmp_path, monkeypatch):
    c = InstallConfig(tmp_path / "p", tmp_path / "d", "h", "o", version="0.3.0")
    c.data_dir.mkdir()
    c.save()
    monkeypatch.setattr(wincli.services, "status", lambda cfg, r: {"AssayrDb": "RUNNING", "AssayrApi": "STOPPED"})
    monkeypatch.setattr(wincli, "SubprocessRunner", lambda path: None)
    result = runner.invoke(app, ["win", "status", "--data-dir", str(c.data_dir)])
    assert "Assayr 0.3.0" in result.output and "AssayrDb" in result.output and "STOPPED" in result.output


def test_scheduled_backup_prunes_to_14(tmp_path, monkeypatch):
    c = InstallConfig(tmp_path / "p", tmp_path / "d", "h", "o", version="0.3.0")
    c.backups_dir.mkdir(parents=True)
    c.save()
    for i in range(16):
        (c.backups_dir / f"assayr-0.3.0-2026100{i:02d}T020000Z-scheduled.tar.gz").write_bytes(b"x")
    (c.backups_dir / "assayr-0.3.0-20260101T000000Z.tar.gz").write_bytes(b"manual")

    def fake_backup(cfg, r, now=None):
        p = cfg.backups_dir / "assayr-0.3.0-20261099T020000Z.tar.gz"
        p.write_bytes(b"new")
        return p

    monkeypatch.setattr(wincli.provision, "make_backup", fake_backup)
    monkeypatch.setattr(wincli, "SubprocessRunner", lambda path: None)
    result = runner.invoke(app, ["win", "backup", "--scheduled", "--data-dir", str(c.data_dir)])
    assert result.exit_code == 0, result.output
    assert len(list(c.backups_dir.glob("*-scheduled.tar.gz"))) == 14
    assert (c.backups_dir / "assayr-0.3.0-20260101T000000Z.tar.gz").exists()
```

- [ ] **Step 2: Run to verify failure** — `uv run pytest tests/windows/test_win_cli.py -v` → FAIL.

- [ ] **Step 3: Implement** `backend/src/assayr/windows/cli.py`:
```python
"""`assayr win …`: commands the Windows installer and the Assayr Admin console use."""

import json
import os
import shutil
from pathlib import Path

import typer

from assayr.backup import BackupError, read_backup, restore_data, version_tuple
from assayr.pgtools import PgTools
from assayr.signatures import SignatureError, update_signatures
from assayr.windows import provision, services
from assayr.windows.layout import InstallConfig
from assayr.windows.render import database_url
from assayr.windows.runner import SubprocessRunner

win_app = typer.Typer(help="Manage Assayr installed as Windows services.", no_args_is_help=True)
DEFAULT_DATA = Path(os.environ.get("ASSAYR_DATA_DIR", r"C:\ProgramData\Assayr"))
DataDir = typer.Option(DEFAULT_DATA, "--data-dir", help="Assayr data folder.")
LOG_NAMES = {"api": "AssayrApi", "worker": "AssayrWorker", "web": "AssayrWeb", "db": "AssayrDb",
             "clamav": "AssayrClamAV"}


def _fail(message: str) -> None:
    typer.echo(message, err=True)
    raise typer.Exit(1)


def _load(data_dir: Path) -> InstallConfig:
    try:
        return InstallConfig.load(data_dir)
    except OSError:
        _fail(f"No Assayr installation found in {data_dir}.")


def _runner(cfg: InstallConfig):
    return SubprocessRunner(cfg.install_log)


@win_app.command()
def install(answers: Path = typer.Option(...)) -> None:
    password = os.environ.get("ASSAYR_ADMIN_PASSWORD", "")
    if not password:
        _fail("Set ASSAYR_ADMIN_PASSWORD to the first administrator's password.")
    a = json.loads(answers.read_text(encoding="utf-8"))
    cfg = InstallConfig(**{k: a[k] for k in (
        "install_dir", "data_dir", "hostname", "org_name", "https_port", "http_port", "web_mode",
        "behind_tls_proxy", "malware_scan", "version")})
    cert = provision.CertChoice(a.get("cert_mode", "self-signed"), Path(a["cert_file"]) if a.get("cert_file") else None,
                                Path(a["key_file"]) if a.get("key_file") else None)
    try:
        provision.install(cfg, a["admin_email"], password, cert, SubprocessRunner(cfg.install_log),
                          pfx_password=os.environ.get("ASSAYR_PFX_PASSWORD") or None)
    except provision.ProvisionError as exc:
        _fail(str(exc))
    typer.echo(f"Assayr {cfg.version} is running at {cfg.health_url.rsplit('/api/', 1)[0]}")


@win_app.command("prepare-upgrade")
def prepare_upgrade(data_dir: Path = DataDir, backup_out: Path = typer.Option(...)) -> None:
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
def finish_upgrade(data_dir: Path = DataDir, version: str = typer.Option(...),
                   install_dir: Path = typer.Option(...)) -> None:
    cfg = _load(data_dir)
    cfg.version, cfg.install_dir = version, install_dir
    try:
        provision.finish_upgrade(cfg, _runner(cfg))
    except provision.ProvisionError as exc:
        _fail(str(exc))
    typer.echo(f"Upgraded to Assayr {version}.")


@win_app.command()
def rollback(data_dir: Path = DataDir, backup: Path = typer.Option(...), version: str = typer.Option(...),
             install_dir: Path = typer.Option(...)) -> None:
    cfg = _load(data_dir)
    cfg.version, cfg.install_dir = version, install_dir
    provision.rollback(cfg, backup, _runner(cfg))
    typer.echo(f"Assayr {version} and its data have been put back.")


@win_app.command()
def uninstall(data_dir: Path = DataDir, delete_data: bool = typer.Option(False, "--delete-data")) -> None:
    cfg = _load(data_dir)
    provision.uninstall(cfg, _runner(cfg), delete_data=delete_data)


@win_app.command()
def status(data_dir: Path = DataDir) -> None:
    cfg = _load(data_dir)
    typer.echo(f"Assayr {cfg.version} — {cfg.health_url.rsplit('/api/', 1)[0]}")
    for name, state in services.status(cfg, _runner(cfg)).items():
        typer.echo(f"  {name:<14} {state}")
    free = shutil.disk_usage(cfg.data_dir).free // 2**30
    typer.echo(f"  Free disk on the data drive: {free} GB")


@win_app.command()
def start(data_dir: Path = DataDir) -> None:
    cfg = _load(data_dir)
    services.start_all(cfg, _runner(cfg))


@win_app.command()
def stop(data_dir: Path = DataDir) -> None:
    cfg = _load(data_dir)
    services.stop_all(cfg, _runner(cfg))


@win_app.command()
def restart(data_dir: Path = DataDir) -> None:
    cfg = _load(data_dir)
    r = _runner(cfg)
    services.stop_all(cfg, r)
    services.start_all(cfg, r)


@win_app.command()
def logs(which: str = typer.Argument("api"), lines: int = 200, data_dir: Path = DataDir) -> None:
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
def backup(data_dir: Path = DataDir, scheduled: bool = False) -> None:
    cfg = _load(data_dir)
    try:
        path = provision.make_backup(cfg, _runner(cfg))
    except BackupError as exc:
        _fail(str(exc))
    if scheduled:
        renamed = path.with_name(path.name.replace(".tar.gz", "-scheduled.tar.gz"))
        path.rename(renamed)
        path = renamed
        for old in sorted(cfg.backups_dir.glob("assayr-*-scheduled.tar.gz"))[:-14]:
            old.unlink()
    typer.echo(f"Backup written to {path}")


@win_app.command()
def restore(file: Path, data_dir: Path = DataDir, yes: bool = typer.Option(False, "--yes")) -> None:
    cfg = _load(data_dir)
    work = cfg.data_dir / ".restore"
    shutil.rmtree(work, ignore_errors=True)
    try:
        source = read_backup(file, work)
        if version_tuple(source.version) > version_tuple(cfg.version):
            _fail(f"This backup was made by Assayr {source.version}, which is newer than the installed "
                  f"{cfg.version}. Upgrade to {source.version} or later first.")
        if not yes and not typer.confirm(
            f"Restoring replaces all current Assayr data with the backup taken at {source.created}. Continue?"
        ):
            raise typer.Exit(1)
        r = _runner(cfg)
        safety = provision.make_backup(cfg, r)
        typer.echo(f"Safety backup: {safety}")
        for s in ("AssayrWeb", "AssayrWorker", "AssayrApi"):
            r.run(["sc.exe", "stop", s], check=False)
        restore_data(source, cfg.blobs_dir, PgTools(cfg.pg_bin, database_url(cfg, provision._env_password(cfg) or "")))
        provision._assayr(cfg, r, "migrate")
        services.start_all(cfg, r)
    except BackupError as exc:
        _fail(f"This backup can't be used: {exc}")
    finally:
        shutil.rmtree(work, ignore_errors=True)
    typer.echo("Restore complete.")


@win_app.command("update-signatures")
def update_sigs(path: Path, data_dir: Path = DataDir) -> None:
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
def create_admin(email: str = typer.Option(...), data_dir: Path = DataDir) -> None:
    cfg = _load(data_dir)
    password = typer.prompt("Password (at least 12 characters)", hide_input=True, confirmation_prompt=True)
    provision._assayr(cfg, _runner(cfg), "create-admin", "--email", email, ASSAYR_ADMIN_PASSWORD=password)
```

`backend/src/assayr/cli.py` (bottom):
```python
from assayr.windows.cli import win_app  # noqa: E402

app.add_typer(win_app, name="win")
```
Also add `backend/src/assayr/__main__.py` so `python -m assayr` works:
```python
from assayr.cli import app

app()
```

- [ ] **Step 4: Run tests** — `uv run pytest -q && uv run ruff check . && uv run ruff format --check .` → PASS.

- [ ] **Step 5: Commit**
```bash
git add backend/src/assayr/windows/cli.py backend/src/assayr/cli.py backend/src/assayr/__main__.py backend/tests/windows/test_win_cli.py
git commit -m "feat(windows): assayr win commands for the installer and admin console"
```

---

### Task 9: Build script and pinned components

**Files:**
- Create: `deploy/windows/components.json`, `deploy/windows/build.ps1`, `deploy/windows/assayr-admin.cmd`

**Interfaces:**
- Produces: `deploy/windows/build.ps1 -Version 0.3.0 -Out <dir> [-Signatures <dir>]` creates `<dir>/stage/` with `python\`, `pgsql\`, `caddy\caddy.exe`, `clamav\` (+ `clamav\database\*.cvd` when `-Signatures` given), `web\`, `services\WinSW-x64.exe`, `assayr-admin.cmd`, `VERSION`. Fails on any SHA-256 mismatch.

- [ ] **Step 1: Pin components.** Download each URL once and record its hash:

`deploy/windows/components.json` (fill `sha256` with the values printed by the command below):
```json
{
  "python":   {"version": "3.12.12", "url": "https://github.com/astral-sh/python-build-standalone/releases/download/20251014/cpython-3.12.12+20251014-x86_64-pc-windows-msvc-install_only.tar.gz", "sha256": ""},
  "postgres": {"version": "16.10", "url": "https://get.enterprisedb.com/postgresql/postgresql-16.10-1-windows-x64-binaries.zip", "sha256": ""},
  "caddy":    {"version": "2.10.2", "url": "https://github.com/caddyserver/caddy/releases/download/v2.10.2/caddy_2.10.2_windows_amd64.zip", "sha256": ""},
  "clamav":   {"version": "1.4.3", "url": "https://www.clamav.net/downloads/production/clamav-1.4.3.win.x64.zip", "sha256": ""},
  "winsw":    {"version": "2.12.0", "url": "https://github.com/winsw/winsw/releases/download/v2.12.0/WinSW-x64.exe", "sha256": ""}
}
```
Run (PowerShell), pick the newest patch release of each that exists and update `version`/`url` if a URL 404s:
```powershell
$c = Get-Content deploy/windows/components.json | ConvertFrom-Json
foreach ($p in $c.PSObject.Properties) { $f = "$env:TEMP\$($p.Name)"; Invoke-WebRequest $p.Value.url -OutFile $f; "$($p.Name) $((Get-FileHash $f -Algorithm SHA256).Hash.ToLower())" }
```
Write each printed hash into `sha256`.

- [ ] **Step 2: Write** `deploy/windows/assayr-admin.cmd`:
```bat
@echo off
rem Assayr Admin: status, start, stop, restart, logs, backup, restore, create-admin, update-signatures
setlocal
set "ASSAYR_HOME=%~dp0"
for /f "usebackq tokens=2,*" %%A in (`reg query "HKLM\SOFTWARE\Assayr" /v DataDir 2^>nul ^| find "DataDir"`) do set "ASSAYR_DATA_DIR=%%B"
if not defined ASSAYR_DATA_DIR set "ASSAYR_DATA_DIR=%ProgramData%\Assayr"
set "ASSAYR_ENV_FILE=%ASSAYR_DATA_DIR%\assayr.env"
set "PYTHONUTF8=1"
if "%~1"=="" (
  "%ASSAYR_HOME%python\python.exe" -m assayr win --help
) else (
  "%ASSAYR_HOME%python\python.exe" -m assayr win %* --data-dir "%ASSAYR_DATA_DIR%"
)
exit /b %ERRORLEVEL%
```
Note: typer accepts options after positional arguments, so `assayr-admin restore FILE` becomes `win restore FILE --data-dir …`.

- [ ] **Step 3: Write** `deploy/windows/build.ps1`:
```powershell
<#
.SYNOPSIS
  Assemble the Windows installer staging folder from pinned, hash-checked components.
#>
param(
  [Parameter(Mandatory)] [ValidatePattern('^\d+\.\d+\.\d+$')] [string] $Version,
  [Parameter(Mandatory)] [string] $Out,
  [string] $Signatures = ""
)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$repo = Resolve-Path "$PSScriptRoot\..\.."
$components = Get-Content "$PSScriptRoot\components.json" -Raw | ConvertFrom-Json
$downloads = Join-Path $Out 'downloads'
$stage = Join-Path $Out 'stage'
New-Item -ItemType Directory -Force $downloads | Out-Null
if (Test-Path $stage) { Remove-Item -Recurse -Force $stage }
New-Item -ItemType Directory -Force $stage | Out-Null

function Get-Component([string] $name) {
  $c = $components.$name
  $file = Join-Path $downloads ([IO.Path]::GetFileName(([Uri]$c.url).AbsolutePath))
  if (-not (Test-Path $file)) { Invoke-WebRequest $c.url -OutFile $file }
  $hash = (Get-FileHash $file -Algorithm SHA256).Hash.ToLower()
  if ($hash -ne $c.sha256) { throw "$name download does not match its pinned SHA-256 ($hash)" }
  return $file
}

# Python (relocatable build) + backend
$py = Get-Component python
tar -xzf $py -C $stage
if (-not (Test-Path "$stage\python\python.exe")) { throw "python.exe missing after unpacking" }
Push-Location "$repo\backend"
uv build --wheel --out-dir "$Out\wheel" | Out-Host
uv export --frozen --no-dev --no-hashes --no-emit-project -o "$Out\requirements.txt" | Out-Host
Pop-Location
& "$stage\python\python.exe" -m pip install --no-warn-script-location --disable-pip-version-check `
    -r "$Out\requirements.txt" (Get-ChildItem "$Out\wheel\assayr-*.whl").FullName
if ($LASTEXITCODE) { throw "pip install failed" }
Remove-Item -Recurse -Force "$stage\python\Lib\test" -ErrorAction SilentlyContinue

# PostgreSQL: keep bin, lib, share only (drop pgAdmin, docs, headers, symbols)
$pg = Get-Component postgres
$tmp = Join-Path $Out 'pgsql-unpacked'
if (Test-Path $tmp) { Remove-Item -Recurse -Force $tmp }
Expand-Archive $pg $tmp
New-Item -ItemType Directory "$stage\pgsql" | Out-Null
foreach ($d in 'bin', 'lib', 'share') { Copy-Item -Recurse "$tmp\pgsql\$d" "$stage\pgsql\$d" }
Get-ChildItem "$stage\pgsql" -Recurse -Include *.pdb | Remove-Item -Force

# Caddy
$caddy = Get-Component caddy
Expand-Archive $caddy "$stage\caddy"
Get-ChildItem "$stage\caddy" -Exclude caddy.exe | Remove-Item -Recurse -Force

# ClamAV
$clam = Get-Component clamav
$tmp = Join-Path $Out 'clamav-unpacked'
if (Test-Path $tmp) { Remove-Item -Recurse -Force $tmp }
Expand-Archive $clam $tmp
$root = (Get-ChildItem $tmp -Directory | Select-Object -First 1).FullName
Copy-Item -Recurse $root "$stage\clamav"
New-Item -ItemType Directory -Force "$stage\clamav\database" | Out-Null
if ($Signatures) { Copy-Item "$Signatures\*.c?d" "$stage\clamav\database\" }

# WinSW
New-Item -ItemType Directory "$stage\services" | Out-Null
Copy-Item (Get-Component winsw) "$stage\services\WinSW-x64.exe"

# Frontend
Push-Location "$repo\frontend"
npm ci | Out-Host
npm run build | Out-Host
Pop-Location
Copy-Item -Recurse "$repo\frontend\dist" "$stage\web"

Copy-Item "$PSScriptRoot\assayr-admin.cmd" $stage
Set-Content "$stage\VERSION" $Version -NoNewline -Encoding ascii
& "$stage\python\python.exe" -c "import assayr, sys; assert assayr.__version__ == sys.argv[1], assayr.__version__" $Version
if ($LASTEXITCODE) { throw "Packaged backend version is not $Version" }
Write-Host "Staged Assayr $Version in $stage"
```

- [ ] **Step 4: Run it locally** (Windows dev machine; output on E:):
```powershell
. .\scripts\dev-env.ps1
powershell -ExecutionPolicy Bypass -File deploy\windows\build.ps1 -Version 0.2.0 -Out E:\assayr-win-build
& E:\assayr-win-build\stage\python\python.exe -m assayr win --help
& E:\assayr-win-build\stage\pgsql\bin\postgres.exe --version
& E:\assayr-win-build\stage\caddy\caddy.exe version
```
Expected: help text listing `install`, `status`, …; `postgres (PostgreSQL) 16.x`; a Caddy version. (Version 0.2.0 here because the bump happens in Task 13; the script's final check will pass because `pyproject.toml` is still 0.2.0.)

- [ ] **Step 5: Commit**
```bash
git add deploy/windows/components.json deploy/windows/build.ps1 deploy/windows/assayr-admin.cmd
git commit -m "build(windows): staging script with pinned, hash-checked runtimes"
```

---

### Task 10: Inno Setup installer

**Files:**
- Create: `deploy/windows/assayr.iss`, `deploy/windows/answers.example.ini`

**Interfaces:**
- Consumes: staging folder (Task 9); `assayr win install|prepare-upgrade|finish-upgrade|rollback|uninstall` (Task 8).
- Produces: `Assayr-Setup-<version>.exe` via `ISCC.exe /DVersion=<v> /DStage=<stage> /DOutDir=<dir> deploy\windows\assayr.iss`. Silent mode: `/VERYSILENT /SUPPRESSMSGBOXES /CONFIG=<ini>` (+ env `ASSAYR_ADMIN_PASSWORD`). Exit codes: 0 ok; 1 setup failed (Inno default for exceptions); log at `<data>\install.log`.

- [ ] **Step 1: Write** `deploy/windows/answers.example.ini`:
```ini
; Unattended install: Assayr-Setup-<version>.exe /VERYSILENT /SUPPRESSMSGBOXES /CONFIG=C:\path\answers.ini
; The administrator password comes from the ASSAYR_ADMIN_PASSWORD environment variable, never from this file.
[Assayr]
Hostname=grc.example.local
Organisation=Example Bank
AdminEmail=isms@example.com
HttpsPort=443
HttpPort=80
; https (default) or http (plain HTTP, e.g. behind your own TLS proxy)
WebMode=https
BehindTlsProxy=no
; self-signed (default), pem (CertFile + KeyFile) or pfx (CertFile; password from ASSAYR_PFX_PASSWORD)
CertMode=self-signed
CertFile=
KeyFile=
MalwareScan=yes
DataDir=C:\ProgramData\Assayr
```

- [ ] **Step 2: Write** `deploy/windows/assayr.iss`:
```pascal
; Assayr Windows installer. Build: ISCC /DVersion=0.3.0 /DStage=<stage dir> /DOutDir=<out dir> assayr.iss
#ifndef Version
  #error Pass /DVersion=x.y.z
#endif

[Setup]
AppId={{03AE51D2-794C-46E2-9883-A074E1623697}
AppName=Assayr
AppVersion={#Version}
AppPublisher=Assayr
DefaultDirName={autopf}\Assayr
DisableDirPage=yes
DisableProgramGroupPage=yes
OutputDir={#OutDir}
OutputBaseFilename=Assayr-Setup-{#Version}
Compression=lzma2/ultra64
SolidCompression=yes
LZMAUseSeparateProcess=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.17763
PrivilegesRequired=admin
WizardStyle=modern
SetupLogging=yes
UninstallDisplayName=Assayr
UninstallDisplayIcon={app}\caddy\caddy.exe
CloseApplications=no
#ifdef SignTool
SignTool={#SignTool}
SignedUninstaller=yes
#endif

[Files]
Source: "{#Stage}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{autoprograms}\Assayr\Open Assayr"; Filename: "{code:SiteUrl}"
Name: "{autoprograms}\Assayr\Assayr Admin"; Filename: "{cmd}"; Parameters: "/k ""{app}\assayr-admin.cmd"" status"; WorkingDir: "{app}"
Name: "{autoprograms}\Assayr\Back up now"; Filename: "{app}\assayr-admin.cmd"; Parameters: "backup"; WorkingDir: "{app}"

[Registry]
Root: HKLM; Subkey: "SOFTWARE\Assayr"; ValueType: string; ValueName: "InstallDir"; ValueData: "{app}"; Flags: uninsdeletekey
Root: HKLM; Subkey: "SOFTWARE\Assayr"; ValueType: string; ValueName: "DataDir"; ValueData: "{code:DataDir}"
Root: HKLM; Subkey: "SOFTWARE\Assayr"; ValueType: string; ValueName: "Version"; ValueData: "{#Version}"

[Code]
const
  RegKey = 'SOFTWARE\Assayr';

var
  ServerPage, AdminPage: TInputQueryWizardPage;
  CertPage: TInputOptionWizardPage;
  CertFilesPage: TInputFileWizardPage;
  OptionsPage: TInputOptionWizardPage;
  DataPage: TInputDirWizardPage;
  Upgrading: Boolean;
  OldVersion, OldDataDir, BackupFile: string;
  Silent: Boolean;

function SetEnvironmentVariable(lpName, lpValue: string): BOOL;
  external 'SetEnvironmentVariableW@kernel32.dll stdcall';

{ ---------- helpers ---------- }

function Ini(Key, Default: string): string;
begin
  Result := GetIniString('Assayr', Key, Default, ExpandConstant('{param:CONFIG|}'));
end;

function VersionValue(V: string): Int64;
var Major, Minor, Patch: Integer; P: Integer;
begin
  P := Pos('.', V); Major := StrToIntDef(Copy(V, 1, P - 1), 0); Delete(V, 1, P);
  P := Pos('.', V); Minor := StrToIntDef(Copy(V, 1, P - 1), 0); Delete(V, 1, P);
  Patch := StrToIntDef(V, 0);
  Result := Int64(Major) * 1000000 + Minor * 1000 + Patch;
end;

function DataDir(Param: string): string;
begin
  if Upgrading then Result := OldDataDir
  else if Silent then Result := Ini('DataDir', ExpandConstant('{commonappdata}\Assayr'))
  else Result := DataPage.Values[0];
end;

function HttpsPort: string;
begin
  if Silent then Result := Ini('HttpsPort', '443') else Result := ServerPage.Values[2];
end;

function HttpPort: string;
begin
  if Silent then Result := Ini('HttpPort', '80') else Result := ServerPage.Values[3];
end;

function SiteUrl(Param: string): string;
begin
  if Upgrading then Result := 'https://localhost'
  else Result := 'https://localhost:' + HttpsPort;
end;

function PortOwner(Port: string): string;
var Code: Integer; Tmp: string; Lines: TArrayOfString;
begin
  Result := '';
  Tmp := ExpandConstant('{tmp}\port.txt');
  Exec('powershell.exe', '-NoProfile -Command "$c = Get-NetTCPConnection -State Listen -LocalPort ' + Port +
       ' -ErrorAction SilentlyContinue | Select-Object -First 1; if ($c) { (Get-Process -Id $c.OwningProcess).ProcessName }" > "' + Tmp + '"',
       '', SW_HIDE, ewWaitUntilTerminated, Code);
  if LoadStringsFromFile(Tmp, Lines) and (GetArrayLength(Lines) > 0) then Result := Trim(Lines[0]);
end;

function Python(Args: string): Integer;
var Code: Integer;
begin
  Exec(ExpandConstant('{app}\python\python.exe'), '-m assayr win ' + Args, ExpandConstant('{app}'),
       SW_HIDE, ewWaitUntilTerminated, Code);
  Result := Code;
end;

function OldPython(Args: string): Integer;
var Code: Integer;
begin
  Exec(ExpandConstant('{app}.previous\python\python.exe'), '-m assayr win ' + Args, ExpandConstant('{app}.previous'),
       SW_HIDE, ewWaitUntilTerminated, Code);
  Result := Code;
end;

{ ---------- wizard ---------- }

procedure InitializeWizard;
begin
  Silent := WizardSilent;
  Upgrading := RegQueryStringValue(HKLM, RegKey, 'Version', OldVersion) and
               RegQueryStringValue(HKLM, RegKey, 'DataDir', OldDataDir);

  ServerPage := CreateInputQueryPage(wpWelcome, 'Server', 'How users reach Assayr',
    'Enter the name users will type in the browser, your organisation and the ports.');
  ServerPage.Add('Hostname:', False);
  ServerPage.Add('Organisation name:', False);
  ServerPage.Add('HTTPS port:', False);
  ServerPage.Add('HTTP port (redirects to HTTPS):', False);
  ServerPage.Values[0] := Lowercase(GetComputerNameString);
  ServerPage.Values[2] := '443';
  ServerPage.Values[3] := '80';

  CertPage := CreateInputOptionPage(ServerPage.ID, 'HTTPS certificate', 'Which certificate should Assayr use?',
    'A self-signed certificate works immediately but browsers warn until you replace it.', True, False);
  CertPage.Add('Create a self-signed certificate');
  CertPage.Add('Use a certificate (.crt) and key (.key) from my certificate authority');
  CertPage.Add('Use a .pfx / .p12 file');
  CertPage.SelectedValueIndex := 0;

  CertFilesPage := CreateInputFilePage(CertPage.ID, 'Certificate files', 'Choose the files',
    'For a .pfx file leave the key empty; you will be asked for its password next.');
  CertFilesPage.Add('Certificate (.crt, .pem, .pfx, .p12):', 'Certificates|*.crt;*.pem;*.cer;*.pfx;*.p12|All files|*.*', '.crt');
  CertFilesPage.Add('Private key (.key):', 'Keys|*.key;*.pem|All files|*.*', '.key');

  AdminPage := CreateInputQueryPage(CertFilesPage.ID, 'First administrator', 'Sign-in for the first administrator',
    'The password must be at least 12 characters.');
  AdminPage.Add('Email:', False);
  AdminPage.Add('Password:', True);
  AdminPage.Add('Repeat password:', True);
  AdminPage.Add('PFX password (only for a .pfx file):', True);

  OptionsPage := CreateInputOptionPage(AdminPage.ID, 'Options', 'Malware scanning',
    'Scanning every upload with ClamAV needs about 2 GB of memory.', False, False);
  OptionsPage.Add('Scan uploaded evidence for malware (recommended)');
  OptionsPage.Values[0] := True;

  DataPage := CreateInputDirPage(OptionsPage.ID, 'Data folder', 'Where Assayr keeps its data',
    'The database, evidence files, certificates and backups go here. It is kept when Assayr is upgraded or uninstalled.',
    False, '');
  DataPage.Add('');
  DataPage.Values[0] := ExpandConstant('{commonappdata}\Assayr');
end;

function ShouldSkipPage(PageID: Integer): Boolean;
begin
  Result := Upgrading and ((PageID = ServerPage.ID) or (PageID = CertPage.ID) or (PageID = CertFilesPage.ID) or
            (PageID = AdminPage.ID) or (PageID = OptionsPage.ID) or (PageID = DataPage.ID));
  if (PageID = CertFilesPage.ID) and (CertPage.SelectedValueIndex = 0) then Result := True;
end;

function CheckPorts(Https, Http: string): string;
var Owner: string;
begin
  Result := '';
  Owner := PortOwner(Https);
  if Owner <> '' then Result := 'Port ' + Https + ' is used by ' + Owner + '. Choose another HTTPS port.';
  Owner := PortOwner(Http);
  if (Result = '') and (Owner <> '') then Result := 'Port ' + Http + ' is used by ' + Owner + '. Choose another HTTP port.';
end;

function NextButtonClick(CurPageID: Integer): Boolean;
var Problem: string;
begin
  Result := True;
  if CurPageID = ServerPage.ID then begin
    if (Trim(ServerPage.Values[0]) = '') or (Trim(ServerPage.Values[1]) = '') then begin
      MsgBox('Enter the hostname and the organisation name.', mbError, MB_OK); Result := False; Exit; end;
    Problem := CheckPorts(ServerPage.Values[2], ServerPage.Values[3]);
    if Problem <> '' then begin MsgBox(Problem, mbError, MB_OK); Result := False; end;
  end;
  if CurPageID = CertFilesPage.ID then begin
    if not FileExists(CertFilesPage.Values[0]) then begin
      MsgBox('Choose the certificate file.', mbError, MB_OK); Result := False; end
    else if (CertPage.SelectedValueIndex = 1) and not FileExists(CertFilesPage.Values[1]) then begin
      MsgBox('Choose the private key file.', mbError, MB_OK); Result := False; end;
  end;
  if CurPageID = AdminPage.ID then begin
    if Pos('@', AdminPage.Values[0]) = 0 then begin
      MsgBox('Enter a valid email address.', mbError, MB_OK); Result := False; end
    else if Length(AdminPage.Values[1]) < 12 then begin
      MsgBox('The password must be at least 12 characters.', mbError, MB_OK); Result := False; end
    else if AdminPage.Values[1] <> AdminPage.Values[2] then begin
      MsgBox('The passwords do not match.', mbError, MB_OK); Result := False; end;
  end;
end;

{ ---------- system checks ---------- }

type
  TMemoryStatusEx = record
    dwLength: DWORD; dwMemoryLoad: DWORD;
    ullTotalPhys, ullAvailPhys, ullTotalPageFile, ullAvailPageFile, ullTotalVirtual, ullAvailVirtual,
    ullAvailExtendedVirtual: Int64;
  end;

function GlobalMemoryStatusEx(var lpBuffer: TMemoryStatusEx): BOOL;
  external 'GlobalMemoryStatusEx@kernel32.dll stdcall';

function InitializeSetup: Boolean;
var Mem: TMemoryStatusEx; Warn, Problem: string; Installed: string;
begin
  Result := True;
  if RegQueryStringValue(HKLM, RegKey, 'Version', Installed) then begin
    if VersionValue(Installed) > VersionValue('{#Version}') then begin
      SuppressibleMsgBox('Assayr ' + Installed + ' is installed, which is newer than ' + '{#Version}' +
        '. Downgrading is not supported.', mbCriticalError, MB_OK, IDOK);
      Result := False; Exit;
    end;
    Exit;  { upgrade or repair: checks below are for first installs }
  end;
  Warn := '';
  Mem.dwLength := SizeOf(Mem);
  if GlobalMemoryStatusEx(Mem) and (Mem.ullTotalPhys < Int64(7800) * 1024 * 1024) then
    Warn := Warn + '- Less than 8 GB of memory.' + #13#10;
  if Warn <> '' then
    if SuppressibleMsgBox('This server is below the recommended size:' + #13#10 + Warn + 'Continue anyway?',
         mbConfirmation, MB_YESNO, IDYES) = IDNO then Result := False;
  if WizardSilent then begin
    Problem := CheckPorts(Ini('HttpsPort', '443'), Ini('HttpPort', '80'));
    if Problem <> '' then begin Log(Problem); Result := False; end;
  end;
end;

{ ---------- install / upgrade ---------- }

function BoolStr(B: Boolean): string;
begin if B then Result := 'true' else Result := 'false'; end;

function JsonStr(S: string): string;
begin
  StringChangeEx(S, '\', '\\', True);
  StringChangeEx(S, '"', '\"', True);
  Result := '"' + S + '"';
end;

function WriteAnswers: string;
var Mode, CertFile, KeyFile, Host, Org, Email, WebMode: string; Scan, Proxy: Boolean;
begin
  if Silent then begin
    Host := Ini('Hostname', Lowercase(GetComputerNameString)); Org := Ini('Organisation', 'My Organization');
    Email := Ini('AdminEmail', ''); Mode := Ini('CertMode', 'self-signed'); CertFile := Ini('CertFile', '');
    KeyFile := Ini('KeyFile', ''); Scan := CompareText(Ini('MalwareScan', 'yes'), 'yes') = 0;
    WebMode := Ini('WebMode', 'https'); Proxy := CompareText(Ini('BehindTlsProxy', 'no'), 'yes') = 0;
  end else begin
    Host := ServerPage.Values[0]; Org := ServerPage.Values[1]; Email := AdminPage.Values[0];
    case CertPage.SelectedValueIndex of 0: Mode := 'self-signed'; 1: Mode := 'pem'; else Mode := 'pfx'; end;
    CertFile := CertFilesPage.Values[0]; KeyFile := CertFilesPage.Values[1];
    Scan := OptionsPage.Values[0]; WebMode := 'https'; Proxy := False;
    SetEnvironmentVariable('ASSAYR_ADMIN_PASSWORD', AdminPage.Values[1]);
    SetEnvironmentVariable('ASSAYR_PFX_PASSWORD', AdminPage.Values[3]);
  end;
  Result := ExpandConstant('{tmp}\answers.json');
  SaveStringToFile(Result,
    '{"install_dir": ' + JsonStr(ExpandConstant('{app}')) + ', "data_dir": ' + JsonStr(DataDir('')) +
    ', "hostname": ' + JsonStr(Host) + ', "org_name": ' + JsonStr(Org) +
    ', "https_port": ' + HttpsPort + ', "http_port": ' + HttpPort + ', "web_mode": ' + JsonStr(WebMode) +
    ', "behind_tls_proxy": ' + BoolStr(Proxy) + ', "malware_scan": ' + BoolStr(Scan) +
    ', "version": "{#Version}", "admin_email": ' + JsonStr(Email) + ', "cert_mode": ' + JsonStr(Mode) +
    ', "cert_file": ' + JsonStr(CertFile) + ', "key_file": ' + JsonStr(KeyFile) + '}', False);
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var App, Out: string; Lines: TArrayOfString;
begin
  Result := '';
  if not Upgrading then Exit;
  App := ExpandConstant('{app}');
  Out := ExpandConstant('{tmp}\backup-path.txt');
  WizardForm.PreparingLabel.Caption := 'Backing up Assayr ' + OldVersion + ' before the upgrade...';
  if Python_Old_Prepare(App, Out) <> 0 then begin
    Result := 'The backup before the upgrade failed, so nothing was changed. See ' + OldDataDir + '\install.log';
    Exit;
  end;
  if LoadStringsFromFile(Out, Lines) and (GetArrayLength(Lines) > 0) then BackupFile := Trim(Lines[0]);
  DelTree(App + '.previous', True, True, True);
  if not RenameFile(App, App + '.previous') then
    Result := 'Could not move the old program folder aside. Close any window using ' + App + ' and try again.';
end;
```
The helper `Python_Old_Prepare` must be declared above `PrepareToInstall`:
```pascal
function Python_Old_Prepare(App, Out: string): Integer;
var Code: Integer;
begin
  Exec(App + '\python\python.exe', '-m assayr win prepare-upgrade --data-dir "' + OldDataDir +
       '" --backup-out "' + Out + '"', App, SW_HIDE, ewWaitUntilTerminated, Code);
  Result := Code;
end;
```
and the post-install step:
```pascal
procedure Fail(Msg: string);
begin
  SuppressibleMsgBox(Msg, mbCriticalError, MB_OK, IDOK);
  Abort;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var App, Answers: string;
begin
  if CurStep <> ssPostInstall then Exit;
  App := ExpandConstant('{app}');
  WizardForm.StatusLabel.Caption := 'Configuring Assayr. This takes a few minutes...';
  if Upgrading then begin
    if Python('finish-upgrade --data-dir "' + OldDataDir + '" --version {#Version} --install-dir "' + App + '"') <> 0 then begin
      WizardForm.StatusLabel.Caption := 'The upgrade failed. Putting Assayr ' + OldVersion + ' back...';
      DelTree(App, True, True, True);
      RenameFile(App + '.previous', App);
      RegWriteStringValue(HKLM, RegKey, 'Version', OldVersion);
      Python('rollback --data-dir "' + OldDataDir + '" --backup "' + BackupFile + '" --version ' + OldVersion +
             ' --install-dir "' + App + '"');
      Fail('The upgrade to {#Version} failed, so Assayr ' + OldVersion + ' and its data have been restored. ' +
           'See ' + OldDataDir + '\install.log');
    end;
    DelTree(App + '.previous', True, True, True);
  end else begin
    Answers := WriteAnswers;
    if Python('install --answers "' + Answers + '"') <> 0 then begin
      DeleteFile(Answers);
      SetEnvironmentVariable('ASSAYR_ADMIN_PASSWORD', '');
      Fail('Assayr could not be set up. See ' + DataDir('') + '\install.log for the step that failed.');
    end;
    DeleteFile(Answers);
    SetEnvironmentVariable('ASSAYR_ADMIN_PASSWORD', '');
    SetEnvironmentVariable('ASSAYR_PFX_PASSWORD', '');
  end;
end;

function UpdateReadyMemo(Space, NewLine, MemoUserInfoInfo, MemoDirInfo, MemoTypeInfo, MemoComponentsInfo,
  MemoGroupInfo, MemoTasksInfo: String): String;
begin
  if Upgrading then Result := 'Upgrade Assayr ' + OldVersion + ' to {#Version}.' + NewLine +
    'A backup is taken first; if the new version does not start, ' + OldVersion + ' is put back automatically.'
  else Result := 'Install Assayr {#Version}' + NewLine + 'Data folder: ' + DataDir('') + NewLine +
    'Address: https://' + ServerPage.Values[0] + ':' + HttpsPort;
end;

{ ---------- uninstall ---------- }

var DeleteData: Boolean;

function InitializeUninstall: Boolean;
begin
  Result := True;
  DeleteData := False;
  if not UninstallSilent then
    DeleteData := MsgBox('Also delete ALL Assayr data (database, evidence files, certificates and backups)?' + #13#10 +
      'Choose No to keep the data so Assayr can be reinstalled later. Take a backup first if unsure.',
      mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var Code: Integer; Data, Args: string;
begin
  if CurUninstallStep <> usUninstall then Exit;
  if not RegQueryStringValue(HKLM, RegKey, 'DataDir', Data) then Data := ExpandConstant('{commonappdata}\Assayr');
  Args := '-m assayr win uninstall --data-dir "' + Data + '"';
  if DeleteData then Args := Args + ' --delete-data';
  Exec(ExpandConstant('{app}\python\python.exe'), Args, ExpandConstant('{app}'), SW_HIDE, ewWaitUntilTerminated, Code);
  RegDeleteKeyIncludingSubkeys(HKLM, RegKey);
end;
```
Silent uninstall keeps data unless `/DELETEDATA` is passed: in `InitializeUninstall`, also set `DeleteData := True` when `ExpandConstant('{param:DELETEDATA|no}') = 'yes'`.

The `AppId` GUID must never change (upgrades depend on it). Remove the unused `OldPython` function if the compiler warns.

- [ ] **Step 3: Compile locally** (Inno Setup 6 installed: `winget install JRSoftware.InnoSetup`):
```powershell
& "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe" /DVersion=0.2.0 /DStage=E:\assayr-win-build\stage /DOutDir=E:\assayr-win-build\out deploy\windows\assayr.iss
```
Expected: `Successful compile`, `E:\assayr-win-build\out\Assayr-Setup-0.2.0.exe` exists.

- [ ] **Step 4: Commit**
```bash
git add deploy/windows/assayr.iss deploy/windows/answers.example.ini
git commit -m "build(windows): Inno Setup installer with upgrade rollback and uninstall"
```

---

### Task 11: Windows end-to-end test

**Files:**
- Create: `deploy/windows/tests/e2e.ps1`

**Interfaces:**
- Consumes: `Assayr-Setup-<v>.exe`, plus a newer working installer and a newer broken one (built in Task 12 with versions `99.0.0`, `99.1.0`).
- Produces: `e2e.ps1 -Setup <exe> -Newer <exe> -Broken <exe>`; exit 0 only if every step passes; prints `install.log` and service logs on failure.

- [ ] **Step 1: Write** `deploy/windows/tests/e2e.ps1`:
```powershell
param(
  [Parameter(Mandatory)] [string] $Setup,
  [Parameter(Mandatory)] [string] $Newer,
  [Parameter(Mandatory)] [string] $Broken
)
$ErrorActionPreference = 'Stop'
$Data = 'C:\ProgramData\Assayr'
$App = "$env:ProgramFiles\Assayr"
$Admin = "$App\assayr-admin.cmd"
$Base = 'https://localhost'
$Email = 'e2e@example.com'
$env:ASSAYR_ADMIN_PASSWORD = 'e2e-password-123'

function Step($name) { Write-Host "`n=== $name" }
function Fail($msg) {
  Write-Host "FAILED: $msg"
  if (Test-Path "$Data\install.log") { Get-Content "$Data\install.log" -Tail 200 }
  Get-ChildItem "$Data\logs" -Filter *.log -ErrorAction SilentlyContinue | ForEach-Object { "== $_"; Get-Content $_.FullName -Tail 50 }
  Get-Service Assayr* -ErrorAction SilentlyContinue | Format-Table -AutoSize | Out-String | Write-Host
  exit 1
}
function Run-Setup($exe, $extra) {
  $p = Start-Process $exe -ArgumentList (@('/VERYSILENT', '/SUPPRESSMSGBOXES', "/LOG=$env:TEMP\setup.log") + $extra) -Wait -PassThru
  return $p.ExitCode
}
function Health {
  curl.exe -sk "$Base/api/v1/healthz" | ConvertFrom-Json
}
function Login {
  $s = New-Object Microsoft.PowerShell.Commands.WebRequestSession
  $body = @{ email = $Email; password = $env:ASSAYR_ADMIN_PASSWORD } | ConvertTo-Json
  Invoke-RestMethod "$Base/api/v1/auth/login" -Method Post -Body $body -ContentType 'application/json' -WebSession $s -SkipCertificateCheck | Out-Null
  return $s
}
# Windows PowerShell 5.1 has no -SkipCertificateCheck: the job runs this script with pwsh 7.

$answers = "$env:TEMP\answers.ini"
@"
[Assayr]
Hostname=localhost
Organisation=E2E Org
AdminEmail=$Email
CertMode=self-signed
MalwareScan=yes
"@ | Set-Content $answers -Encoding ascii

Step 'Silent install'
if ((Run-Setup $Setup @("/CONFIG=$answers")) -ne 0) { Fail 'setup exit code' }
$h = Health
if ($h.status -ne 'ok') { Fail "health: $h" }
$installed = $h.version
foreach ($s in 'AssayrDb', 'AssayrClamAV', 'AssayrApi', 'AssayrWorker', 'AssayrWeb') {
  $svc = Get-Service $s
  if ($svc.Status -ne 'Running') { Fail "$s is $($svc.Status)" }
  $acct = (Get-CimInstance Win32_Service -Filter "Name='$s'").StartName
  if ($acct -ne "NT SERVICE\$s") { Fail "$s runs as $acct" }
}
if ((Get-NetTCPConnection -LocalPort 5432 -State Listen).LocalAddress -notcontains '127.0.0.1') { Fail 'postgres not on localhost only' }
if ((curl.exe -s -o NUL -w '%{http_code}' http://localhost/) -ne '301') { Fail 'HTTP does not redirect' }

Step 'Log in and upload evidence'
$session = Login
& $App\python\python.exe "$PSScriptRoot\e2e_evidence.py" $Base $Email $env:ASSAYR_ADMIN_PASSWORD
if ($LASTEXITCODE) { Fail 'evidence checks (clean document verified, EICAR rejected)' }

Step 'Backup and restore'
& $Admin backup | Out-Host
$backup = Get-ChildItem "$Data\backups\assayr-*.tar.gz" | Sort-Object LastWriteTime | Select-Object -Last 1
& $App\python\python.exe -m assayr win restore $backup.FullName --yes --data-dir $Data
if ($LASTEXITCODE) { Fail 'restore' }
if ((Health).status -ne 'ok') { Fail 'unhealthy after restore' }

Step 'Upgrade to a newer version'
if ((Run-Setup $Newer @()) -ne 0) { Fail 'upgrade exit code' }
if ((Health).version -ne '99.0.0') { Fail 'version after upgrade' }
$session = Login

Step 'Broken upgrade rolls back'
$code = Run-Setup $Broken @()
if ($code -eq 0) { Fail 'broken upgrade reported success' }
if ((Health).version -ne '99.0.0') { Fail 'rollback did not restore 99.0.0' }
$session = Login
if ((Get-ItemProperty HKLM:\SOFTWARE\Assayr).Version -ne '99.0.0') { Fail 'registry version after rollback' }

Step 'Uninstall keeps data'
$unins = Get-ChildItem "$App\unins*.exe" | Select-Object -First 1
Start-Process $unins.FullName -ArgumentList '/VERYSILENT', '/SUPPRESSMSGBOXES' -Wait
if (Get-Service Assayr* -ErrorAction SilentlyContinue) { Fail 'services still registered' }
if (-not (Test-Path "$Data\db\PG_VERSION")) { Fail 'data folder was removed' }

Step 'Reinstall over kept data'
if ((Run-Setup $Newer @("/CONFIG=$answers")) -ne 0) { Fail 'reinstall exit code' }
$session = Login

Write-Host "`nAll Windows end-to-end checks passed."
```

- [ ] **Step 2: Write** `deploy/windows/tests/e2e_evidence.py` (runs with the installed Python; uses only stdlib):
```python
"""Upload a clean document and the EICAR file; check the verdicts."""

import http.cookiejar
import json
import ssl
import sys
import time
import urllib.request
import uuid

base, email, password = sys.argv[1:4]
ctx = ssl._create_unverified_context()  # noqa: S323  local self-signed certificate
jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx), urllib.request.HTTPCookieProcessor(jar))


def call(method, path, body=None, headers=None):
    req = urllib.request.Request(base + path, data=body, method=method, headers=headers or {})
    csrf = next((c.value for c in jar if c.name == "assayr_csrf"), None)
    if csrf:
        req.add_header("X-CSRF-Token", csrf)
    with opener.open(req) as resp:
        raw = resp.read()
        return json.loads(raw) if raw else None


call("POST", "/api/v1/auth/login", json.dumps({"email": email, "password": password}).encode(),
     {"Content-Type": "application/json"})
```
Then extend with the evidence upload calls. **Before writing them, read `deploy/installer/tests/e2e.sh`** — the Linux end-to-end test already performs exactly this flow (CSRF cookie name, slot lookup, upload endpoint, polling the verdict, EICAR check). Port those `curl` calls one-for-one into `call(...)` invocations here, keeping its assertions: the clean document reaches a non-error verdict and the EICAR upload ends `rejected` with the malware rule. Exit `1` with a message on any mismatch.

- [ ] **Step 3: Local smoke** (optional on the dev machine if it has spare ports 80/443): run the 0.2.0-built exe from Task 10 with `/VERYSILENT /CONFIG=` and check `https://localhost/api/v1/healthz`; uninstall with `/DELETEDATA=yes` afterwards. The authoritative run is CI (Task 12).

- [ ] **Step 4: Commit**
```bash
git add deploy/windows/tests
git commit -m "test(windows): end-to-end install, evidence, restore, upgrade, rollback and uninstall"
```

---

### Task 12: CI — Windows build, test and publish

**Files:**
- Modify: `.github/workflows/release.yml`, `.github/workflows/ci.yml`

**Interfaces:**
- Consumes: Tasks 9–11.
- Produces: artifact `windows-installer` (`Assayr-Setup-<v>.exe`); the `publish` job attaches it and includes it in `SHA256SUMS.txt`.

- [ ] **Step 1: Add the `paths:` trigger entries** `deploy/windows/**` and `backend/src/**` to `release.yml`'s branch filter.

- [ ] **Step 2: Add a signatures job** (Linux, reuses the ClamAV image already pinned in compose):
```yaml
  clamav-signatures:
    runs-on: ubuntu-24.04
    steps:
      - name: Copy the bundled virus signatures out of the ClamAV image
        run: |
          mkdir sigs
          docker run --rm --entrypoint sh -v "$PWD/sigs:/out" clamav/clamav-debian:1.4 \
            -c 'freshclam --stdout || true; cp /var/lib/clamav/*.c?d /out/'
          ls -l sigs
          test -n "$(ls sigs/*.c?d)"
      - uses: actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02 # v4
        with: { name: clamav-signatures, path: sigs/, retention-days: 1, if-no-files-found: error }
```

- [ ] **Step 3: Add the Windows job:**
```yaml
  windows:
    needs: clamav-signatures
    runs-on: windows-2022
    env:
      INPUT_VERSION: ${{ inputs.version }}
    defaults:
      run:
        shell: pwsh
    steps:
      - uses: actions/checkout@11d5960a326750d5838078e36cf38b85af677262 # v4
        with: { persist-credentials: false }
      - uses: astral-sh/setup-uv@v6
      - uses: actions/setup-node@v4
        with: { node-version: 24 }
      - uses: actions/download-artifact@d3f86a106a0bac45b974a628896c90dbdf5c8093 # v4
        with: { name: clamav-signatures, path: sigs }
      - name: Work out the version
        run: |
          if ($env:GITHUB_REF_TYPE -eq 'tag') { $v = $env:GITHUB_REF_NAME.TrimStart('v') }
          elseif ($env:INPUT_VERSION) { $v = $env:INPUT_VERSION }
          else { $v = (Select-String -Path backend/pyproject.toml -Pattern '^version = "(.*)"$').Matches[0].Groups[1].Value }
          if ($v -notmatch '^\d+\.\d+\.\d+$') { throw "Not a version: $v" }
          "VERSION=$v" >> $env:GITHUB_ENV
      - name: Backend tests on Windows
        working-directory: backend
        run: |
          uv sync --python 3.12 --frozen
          uv run pytest -q -W error
      - name: Stage
        run: ./deploy/windows/build.ps1 -Version $env:VERSION -Out build -Signatures sigs
      - name: Build the installer and the test installers
        run: |
          $iscc = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
          & $iscc /Q "/DVersion=$env:VERSION" /DStage=build\stage /DOutDir=dist deploy\windows\assayr.iss
          # newer working build: same files, version 99.0.0 (package metadata patched for the health check)
          Copy-Item -Recurse build\stage build\stage99
          Get-ChildItem build\stage99\python\Lib\site-packages\assayr-*.dist-info\METADATA |
            ForEach-Object { (Get-Content $_) -replace '^Version: .*$', 'Version: 99.0.0' | Set-Content $_ }
          Rename-Item (Get-ChildItem build\stage99\python\Lib\site-packages\assayr-*.dist-info).FullName 'assayr-99.0.0.dist-info'
          & $iscc /Q /DVersion=99.0.0 /DStage=build\stage99 /DOutDir=dist\test deploy\windows\assayr.iss
          # newer broken build: the API exits at once
          Copy-Item -Recurse build\stage99 build\stage991
          Rename-Item (Get-ChildItem build\stage991\python\Lib\site-packages\assayr-*.dist-info).FullName 'assayr-99.1.0.dist-info'
          Get-ChildItem build\stage991\python\Lib\site-packages\assayr-*.dist-info\METADATA |
            ForEach-Object { (Get-Content $_) -replace '^Version: .*$', 'Version: 99.1.0' | Set-Content $_ }
          Add-Content build\stage991\python\Lib\site-packages\assayr\main.py "`nraise SystemExit('broken on purpose')"
          & $iscc /Q /DVersion=99.1.0 /DStage=build\stage991 /DOutDir=dist\test deploy\windows\assayr.iss
      - name: Sign
        if: env.WINDOWS_SIGNING_CERT != ''
        env:
          WINDOWS_SIGNING_CERT: ${{ secrets.WINDOWS_SIGNING_CERT }}
          WINDOWS_SIGNING_PASSWORD: ${{ secrets.WINDOWS_SIGNING_PASSWORD }}
        run: |
          [IO.File]::WriteAllBytes("$env:RUNNER_TEMP\sign.pfx", [Convert]::FromBase64String($env:WINDOWS_SIGNING_CERT))
          $signtool = (Get-ChildItem "${env:ProgramFiles(x86)}\Windows Kits\10\bin\*\x64\signtool.exe" | Select-Object -Last 1).FullName
          & $signtool sign /f "$env:RUNNER_TEMP\sign.pfx" /p $env:WINDOWS_SIGNING_PASSWORD /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 "dist\Assayr-Setup-$env:VERSION.exe"
          Remove-Item "$env:RUNNER_TEMP\sign.pfx"
      - name: End-to-end test
        run: ./deploy/windows/tests/e2e.ps1 -Setup "dist\Assayr-Setup-$env:VERSION.exe" -Newer dist\test\Assayr-Setup-99.0.0.exe -Broken dist\test\Assayr-Setup-99.1.0.exe
      - uses: actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02 # v4
        with:
          name: windows-installer
          path: dist/Assayr-Setup-*.exe
          retention-days: 7
          if-no-files-found: error
```
Note: signing happens before ISCC would sign the uninstaller; uninstaller signing (via `/DSignTool`) is enabled later together with the certificate — documented in `MANUAL-CHECKS.md`.

- [ ] **Step 4: Update `publish`:**
```yaml
  publish:
    if: github.ref_type == 'tag'
    needs: [bundle, windows]
    ...
      - uses: actions/download-artifact@d3f86a106a0bac45b974a628896c90dbdf5c8093 # v4
        with:
          pattern: "{bundle-*,windows-installer}"
          path: dist
          merge-multiple: true
```
and in the release script: `sha256sum assayr-*.tar.gz Assayr-Setup-*.exe >SHA256SUMS.txt`, add the line `echo "- Windows Server 2019/2022/2025: Assayr-Setup-${TAG#v}.exe (run it and follow the wizard; see README-INSTALL-WINDOWS.md)"` to the notes, change the `linux-amd64` notes line to drop "Windows (Docker Desktop with WSL2)", and upload `Assayr-Setup-*.exe` in `gh release create`.

- [ ] **Step 5: Windows backend tests in `ci.yml`:**
```yaml
  backend-windows:
    runs-on: windows-2022
    defaults:
      run:
        working-directory: backend
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v6
      - run: uv sync --python 3.12 --frozen
      - run: uv run pytest -q -W error
```

- [ ] **Step 6: Run on the branch** (needs the branch pushed — ask the user before pushing):
`gh workflow run release.yml --ref windows-installer -f version=0.3.0` then `gh run watch`. Expected: `clamav-signatures`, `windows`, `bundle (amd64)`, `bundle (arm64)` green; `publish` skipped (not a tag). Fix and repeat until green.

- [ ] **Step 7: Commit**
```bash
git add .github/workflows/release.yml .github/workflows/ci.yml
git commit -m "ci(release): build, test and publish the Windows installer"
```

---

### Task 13: Documentation, version 0.3.0, release

**Files:**
- Create: `deploy/windows/README-INSTALL-WINDOWS.md`, `deploy/windows/MANUAL-CHECKS.md`
- Modify: `README.md`, `deploy/installer/README-INSTALL.md` (Windows section points to the new installer), `backend/pyproject.toml`, `frontend/package.json`, `frontend/package-lock.json`, `backend/uv.lock`

- [ ] **Step 1: Write** `deploy/windows/README-INSTALL-WINDOWS.md` covering, in this order: requirements (Windows Server 2019/2022/2025 x64, 4 cores, 8 GB RAM, 100 GB disk, ports 443/80); download and checksum (`Get-FileHash Assayr-Setup-0.3.0.exe -Algorithm SHA256` vs `SHA256SUMS.txt`); SmartScreen ("More info → Run anyway" while unsigned); the wizard pages; opening `https://<hostname>`; Assayr Admin commands table (`status`, `start`, `stop`, `restart`, `logs`, `backup`, `restore FILE`, `create-admin --email`, `update-signatures PATH`); nightly backups at 02:00 (14 kept) and copying `backups\` elsewhere; replacing the certificate (`certs\tls.crt`/`tls.key` then `assayr-admin restart`); upgrading (run the newer Setup; automatic backup and rollback); unattended install (`answers.example.ini` + `ASSAYR_ADMIN_PASSWORD`); moving from Linux (restore a Linux backup with `assayr-admin restore`); antivirus exclusions for `C:\Program Files\Assayr` and the data folder; uninstall (data kept unless chosen); troubleshooting (`install.log`, `assayr-admin logs api`).

- [ ] **Step 2: Write** `deploy/windows/MANUAL-CHECKS.md`: checklist for each release — Windows Server 2019 VM: interactive install with self-signed cert; install with a `.pfx`; port 443 taken by IIS → wizard names `w3wp`/`System` and accepts 8443; SmartScreen behaviour; Start Menu shortcuts work; reboot → all services come back; nightly task present in Task Scheduler; uninstall with and without data. Plus: how to enable signing (add `WINDOWS_SIGNING_CERT` base64 PFX and `WINDOWS_SIGNING_PASSWORD` secrets).

- [ ] **Step 3: README links** — in `README.md` "Install for customers" add: "Windows Server: `Assayr-Setup-<version>.exe` on the same Release; see `deploy/windows/README-INSTALL-WINDOWS.md`." In `deploy/installer/README-INSTALL.md` change the Windows row/section to say production Windows installs use `Assayr-Setup-<version>.exe`; the WSL2 route stays for evaluation on desktops.

- [ ] **Step 4: Bump versions**
```bash
sed -i 's/^version = "0.2.0"/version = "0.3.0"/' backend/pyproject.toml
(cd backend && uv lock)
(cd frontend && npm version 0.3.0 --no-git-tag-version)
grep -n '^version' backend/pyproject.toml; grep -n '"version"' frontend/package.json
```
Expected: both `0.3.0`.

- [ ] **Step 5: Full gate**
```bash
cd backend && uv run pytest -q -W error && uv run ruff check . && uv run ruff format --check . && cd ..
cd frontend && npm test -- --run && cd ..
deploy/installer/tests/run.sh
```
Expected: all green (Linux installer tests unchanged).

- [ ] **Step 6: Commit**
```bash
git add deploy/windows/README-INSTALL-WINDOWS.md deploy/windows/MANUAL-CHECKS.md README.md deploy/installer/README-INSTALL.md backend/pyproject.toml backend/uv.lock frontend/package.json frontend/package-lock.json
git commit -m "docs: Windows install guide; version 0.3.0"
```

- [ ] **Step 7: Release (only with the user's go-ahead):** push the branch, open a PR, merge after the release workflow run on the branch is green, then:
```bash
git tag v0.3.0 && git push origin v0.3.0
gh run watch $(gh run list --workflow release.yml --limit 1 --json databaseId -q '.[0].databaseId')
gh release view v0.3.0 --repo Hamzaviour/Assayr
```
Expected: release `Assayr 0.3.0` with `Assayr-Setup-0.3.0.exe`, two Linux bundles and `SHA256SUMS.txt`; the exe downloads without authentication.
