# Assayr Phase 0 Foundations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the Assayr monorepo with a working, tested slice: FastAPI backend (local sign-in, scope-aware RBAC, hash-chained audit log, ISO 27001 catalogue seeded with all 93 Annex A controls and clauses 4–10), a React app (Strata design tokens, app shell, sign-in, dashboard, controls list and detail), a Docker Compose deployment and CI.

**Architecture:** Modular monolith. `backend/` is one Python package (`assayr`) split by bounded context (`identity`, `audit`, `catalogue`), served by FastAPI, persisted with SQLAlchemy 2 + Alembic on PostgreSQL in production (SQLite for fast local tests; CI runs the suite against both). `frontend/` is a static React SPA built by Vite and served by Caddy, which also reverse-proxies `/api` to the backend. Cookies carry an opaque session token; state-changing requests need a double-submit CSRF header.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, pydantic-settings, SQLAlchemy 2, Alembic, pg8000, argon2-cffi, Typer, pytest, ruff, uv · React 19, TypeScript 5.7, Vite 6, TanStack Router + Query, Tailwind CSS v4, Vitest 3, Testing Library · PostgreSQL 16, Caddy 2, Docker Compose · GitHub Actions.

**Spec:** Obsidian vault at `E:\Work\GRC Tool\Assayr-Vault` — chiefly `03-Product/PRD.md`, `03-Product/Non-Functional Requirements.md`, `03-Product/RBAC Matrix.md`, `03-Product/Requirements/FR-02 Frameworks and Controls.md`, `FR-18 Identity Roles and Access.md`, `FR-20 Audit Trail.md`, `05-Workflows/State Machines.md`, `06-Architecture/*` (Tech Stack, Data Model, API Design, Deployment On-Prem, Security of the Platform, ADR-001…009), `07-Design/Design System.md`, `07-Design/Information Architecture.md`, `08-Delivery/Roadmap.md` (Phase 0). Seed data: `_data/annex_a_controls.json`.

**Scope notes (deliberate deviations from the Roadmap's Phase 0 exit criteria — confirm with the user):**
- LDAP/AD and OIDC sign-in move to a follow-up plan (Phase 0b). This plan builds local accounts, which every later auth method falls back to.
- Storybook is replaced by an in-app `/styleguide` route (same purpose, no extra toolchain).
- TLS termination, Valkey and the verification worker arrive with Phase 1 (nothing in Phase 0 uses a queue). The compose stack serves HTTP on port 8080 for local evaluation only.

## Global Constraints

- Python `>=3.12`; container base `python:3.12-slim`. Node 24; Vite SPA, no Node server in production (ADR-002).
- In-process dependencies must be permissive (MIT, BSD, Apache-2.0, ISC, MPL-2.0); GPL/AGPL tools only as separate processes (ADR-009). Therefore the Postgres driver is **pg8000** (BSD), not psycopg (LGPL).
- Zero outbound network calls at runtime; fonts self-hosted via `@fontsource/*` packages, never Google Fonts (NFR-SEC-7, Typography).
- Passwords hashed with Argon2id; minimum 12 characters (FR-18.1).
- Session idle timeout 30 minutes, absolute 12 hours (NFR-SEC-10).
- Audit trail append-only and hash-chained; `assayr audit-verify` checks the chain (NFR-SEC-9, FR-20.3, FR-20.6, ADR-008).
- RBAC enforced server-side on every endpoint, deny by default, scope-aware (NFR-SEC-4, RBAC Matrix).
- Time stored in UTC (NFR-DATA-3); the API rejects naive datetimes at the persistence layer.
- Control status is derived, never edited directly (ADR-005). In Phase 0 every control is `not_started`; the column exists so Phase 1 can compute it.
- Status vocabulary (exact API values): `not_started`, `in_progress`, `in_review`, `at_risk`, `non_compliant`, `compliant`, `excluded` (State Machines). Implementation status: `not_started`, `planned`, `partial`, `implemented` (FR-02.5).
- ISO text: ship identifiers, titles and Assayr-authored guidance only, never normative text (ADR-007).
- UI copy: sentence case, buttons verb + noun, control IDs in mono and never wrapped (Voice and Tone, Typography).
- Brand tokens exactly as in `07-Design/Design System.md` (cobalt `#2F4BFF`, ink `#0A0F1F`, brass `#CFAE4E`, status colours); fonts Schibsted Grotesk / IBM Plex Sans / IBM Plex Mono.
- The dev machine's C: drive is full: every command runs after `source scripts/dev-env.sh` (repo root), which points uv, npm, Python installs and temp files at `.cache/` inside the repo.
- Git commit messages end with the line `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

- Email typed with different case or stray spaces at sign-in or user creation must resolve to the same account, never create a duplicate → tests in Task 3 (`normalize_email`), Task 6 (`test_login_is_case_insensitive`) and Task 7 (`test_duplicate_email_rejected_case_insensitively`).
- Repeated wrong passwords must lock the account temporarily without revealing whether the email exists (identical response for unknown user, wrong password and locked account) → Task 6 (`test_unknown_and_wrong_password_look_identical`, `test_lockout_after_five_failures`).
- The container runs `assayr seed` on every start: re-seeding must not duplicate controls or reset owner and implementation edits → Task 8 (`test_seed_is_idempotent_and_preserves_edits`).
- Search text containing `%` or `_` must match literally, not act as SQL wildcards → Task 9 (`test_search_treats_wildcards_literally`).
- A `next` link on the sign-in page pointing off-site (`//evil.com`, `https://…`, backslash tricks) must fall back to `/` → Task 12 (`safeNext` tests).

---

## File Structure

```
assayr/
├── README.md                         # dev quick start, layout, links to the vault
├── .gitignore  .editorconfig
├── scripts/dev-env.sh                # cache/temp redirection (Git Bash)
├── scripts/dev-env.ps1               # same for PowerShell
├── docs/superpowers/plans/…          # this plan
├── backend/
│   ├── pyproject.toml  uv.lock  .env.example  Dockerfile  .dockerignore  docker-entrypoint.sh
│   ├── src/assayr/
│   │   ├── __init__.py               # __version__
│   │   ├── config.py                 # Settings (env prefix ASSAYR_)
│   │   ├── main.py                   # create_app() factory, request-id middleware, routers
│   │   ├── health.py                 # /healthz, /readyz
│   │   ├── db.py                     # Base, mixins, UTCDateTime, Database, get_session
│   │   ├── models.py                 # imports every model module (for metadata/migrations)
│   │   ├── migrate.py                # programmatic Alembic upgrade/downgrade
│   │   ├── cli.py                    # `assayr` Typer CLI
│   │   ├── migrations/               # env.py, script.py.mako, versions/0001-0003
│   │   ├── identity/
│   │   │   ├── models.py             # Organization, Scope, User, RoleAssignment, UserSession
│   │   │   ├── security.py           # Argon2id hashing, tokens, email normalisation
│   │   │   ├── rbac.py               # Role, Perm, ROLE_PERMISSIONS, Grant, grant_for
│   │   │   ├── schemas.py            # Pydantic request/response models
│   │   │   ├── deps.py               # current_user, require(), actor_for(), get_clock()
│   │   │   ├── auth_router.py        # /auth/login, /auth/logout, /auth/me
│   │   │   └── users_router.py       # /users
│   │   ├── audit/
│   │   │   ├── models.py             # AuditLog
│   │   │   ├── service.py            # Actor, record(), verify_chain()
│   │   │   └── router.py             # /audit-log, /audit-log/verify
│   │   └── catalogue/
│   │       ├── models.py             # Framework, Requirement, Control, ControlRequirement, EvidenceSlot
│   │       ├── iso27001_clauses.py   # clause 4–10 identifiers and titles
│   │       ├── seed.py               # ensure_default_scope(), seed_iso27001()
│   │       ├── data/iso27001_2022_annex_a.json
│   │       ├── schemas.py
│   │       └── router.py             # /frameworks, /controls…
│   └── tests/                        # conftest.py + one test module per area
├── frontend/
│   ├── package.json  package-lock.json  tsconfig.json  vite.config.ts  index.html
│   ├── Dockerfile  .dockerignore  Caddyfile  public/favicon.svg
│   └── src/
│       ├── main.tsx  router.tsx
│       ├── styles/tokens.css  styles/global.css
│       ├── api/client.ts  api/types.ts  api/controls.ts
│       ├── auth/session.ts
│       ├── lib/theme.ts
│       ├── components/icons.tsx  Button.tsx  StatusPill.tsx  ControlId.tsx  AppShell.tsx
│       ├── layouts/AppLayout.tsx
│       ├── pages/Login.tsx  Dashboard.tsx  Controls.tsx  ControlDetail.tsx  Styleguide.tsx
│       └── test/setup.ts  test/render.tsx  + *.test.ts(x) beside the code
├── deploy/compose.yaml  assayr.env.example  smoke.sh
└── .github/workflows/ci.yml
```

---

### Task 1: Repository, dev environment and backend skeleton

**Files:**
- Create: `.gitignore`, `.editorconfig`, `scripts/dev-env.sh`, `scripts/dev-env.ps1`, `backend/pyproject.toml`, `backend/src/assayr/__init__.py`, `backend/src/assayr/config.py`, `backend/src/assayr/health.py`, `backend/src/assayr/main.py`, `backend/tests/conftest.py`
- Test: `backend/tests/test_health.py`

**Interfaces:**
- Produces: `assayr.config.Settings`, `assayr.config.get_settings() -> Settings`; `assayr.main.create_app(settings: Settings | None = None) -> FastAPI` (stores `app.state.settings`); request-id middleware sets `request.state.request_id`; test fixtures `settings`, `app`, `client`.

- [ ] **Step 1: Initialise git and the root files**

Working directory for every task: `E:/Work/GRC Tool/assayr`.

```bash
cd "E:/Work/GRC Tool/assayr" && git init -b main
```

`.gitignore`:
```gitignore
.cache/
**/__pycache__/
*.pyc
.pytest_cache/
.ruff_cache/
backend/.venv/
backend/*.db
backend/.env
frontend/node_modules/
frontend/dist/
deploy/assayr.env
*.log
```

`.editorconfig`:
```ini
root = true

[*]
charset = utf-8
end_of_line = lf
insert_final_newline = true
indent_style = space
indent_size = 2
trim_trailing_whitespace = true

[*.py]
indent_size = 4
```

`scripts/dev-env.sh`:
```bash
#!/usr/bin/env bash
# Source this before running uv, npm or python: keeps caches, Python installs and temp
# files inside the repo (the dev machine's C: drive has no free space).
_ASSAYR_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if command -v cygpath >/dev/null 2>&1; then _ASSAYR_ROOT="$(cygpath -m "$_ASSAYR_ROOT")"; fi
export UV_CACHE_DIR="$_ASSAYR_ROOT/.cache/uv"
export UV_PYTHON_INSTALL_DIR="$_ASSAYR_ROOT/.cache/python"
export npm_config_cache="$_ASSAYR_ROOT/.cache/npm"
export TMPDIR="$_ASSAYR_ROOT/.cache/tmp" TMP="$_ASSAYR_ROOT/.cache/tmp" TEMP="$_ASSAYR_ROOT/.cache/tmp"
mkdir -p "$UV_CACHE_DIR" "$UV_PYTHON_INSTALL_DIR" "$npm_config_cache" "$TMPDIR"
```

`scripts/dev-env.ps1`:
```powershell
# Dot-source this before running uv, npm or python: . .\scripts\dev-env.ps1
$root = (Resolve-Path "$PSScriptRoot\..").Path
$env:UV_CACHE_DIR = "$root\.cache\uv"
$env:UV_PYTHON_INSTALL_DIR = "$root\.cache\python"
$env:npm_config_cache = "$root\.cache\npm"
$env:TMP = "$root\.cache\tmp"; $env:TEMP = $env:TMP; $env:TMPDIR = $env:TMP
foreach ($d in @($env:UV_CACHE_DIR, $env:UV_PYTHON_INSTALL_DIR, $env:npm_config_cache, $env:TMP)) {
  New-Item -ItemType Directory -Force -Path $d | Out-Null
}
```

- [ ] **Step 2: Create the backend project**

`backend/pyproject.toml`:
```toml
[project]
name = "assayr"
version = "0.1.0"
description = "Assayr - on-premise GRC for ISO/IEC 27001"
requires-python = ">=3.12"
dependencies = [
  "fastapi>=0.115",
  "uvicorn>=0.30",
  "pydantic>=2.8",
  "pydantic-settings>=2.4",
  "sqlalchemy>=2.0.30",
  "alembic>=1.13",
  "pg8000>=1.31",
  "argon2-cffi>=23.1",
  "typer>=0.12",
]

[dependency-groups]
dev = ["pytest>=8.2", "httpx>=0.27", "ruff>=0.6"]

[project.scripts]
assayr = "assayr.cli:app"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/assayr"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-q"

[tool.ruff]
line-length = 110
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP"]
ignore = ["B008", "E501"]  # Depends() in defaults is idiomatic FastAPI; the formatter owns line length
```

`backend/src/assayr/__init__.py`:
```python
"""Assayr - on-premise GRC for ISO/IEC 27001."""

__version__ = "0.1.0"
```

`backend/src/assayr/config.py`:
```python
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration. Every field can be set with an ASSAYR_<NAME> environment variable."""

    model_config = SettingsConfigDict(env_prefix="ASSAYR_", env_file=".env", extra="ignore")

    database_url: str = "sqlite+pysqlite:///./assayr-dev.db"
    secure_cookies: bool = True
    session_idle_minutes: int = 30
    session_absolute_hours: int = 12
    login_max_failures: int = 5
    login_lockout_minutes: int = 15
    org_name: str = "My Organization"


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

`backend/src/assayr/health.py`:
```python
from fastapi import APIRouter

from assayr import __version__

router = APIRouter(tags=["health"])


@router.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok", "version": __version__}
```

`backend/src/assayr/main.py`:
```python
import re
import uuid

from fastapi import FastAPI, Request

from assayr import __version__
from assayr.config import Settings, get_settings
from assayr.health import router as health_router

_REQUEST_ID_UNSAFE = re.compile(r"[^A-Za-z0-9_-]")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(
        title="Assayr API",
        version=__version__,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        redoc_url=None,
    )
    app.state.settings = settings

    @app.middleware("http")
    async def request_id(request: Request, call_next):
        supplied = _REQUEST_ID_UNSAFE.sub("", request.headers.get("X-Request-Id", ""))[:64]
        request.state.request_id = supplied or uuid.uuid4().hex
        response = await call_next(request)
        response.headers["X-Request-Id"] = request.state.request_id
        return response

    app.include_router(health_router, prefix="/api/v1")
    return app
```

`backend/tests/conftest.py`:
```python
import pytest
from fastapi.testclient import TestClient

from assayr.config import Settings
from assayr.main import create_app


@pytest.fixture
def settings() -> Settings:
    return Settings(database_url="sqlite+pysqlite:///:memory:", secure_cookies=False)


@pytest.fixture
def app(settings):
    return create_app(settings)


@pytest.fixture
def client(app):
    with TestClient(app) as test_client:
        yield test_client
```

- [ ] **Step 3: Write the failing tests**

`backend/tests/test_health.py`:
```python
def test_healthz_reports_ok_and_version(client):
    response = client.get("/api/v1/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "0.1.0"}


def test_request_id_is_echoed_and_sanitised(client):
    response = client.get("/api/v1/healthz", headers={"X-Request-Id": "abc-123<script>"})
    assert response.headers["X-Request-Id"] == "abc-123script"


def test_request_id_generated_when_missing(client):
    response = client.get("/api/v1/healthz")
    assert len(response.headers["X-Request-Id"]) == 32
```

- [ ] **Step 4: Install Python 3.12, sync dependencies, run the tests**

```bash
cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && cd backend && uv python install 3.12 && uv sync --python 3.12 && uv run pytest
```
Expected: `3 passed`. (If you run the tests before Step 2's code exists you get `ModuleNotFoundError: assayr` — that is the failing state.)

- [ ] **Step 5: Lint and commit**

```bash
cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && (cd backend && uv run ruff format . && uv run ruff check --fix .) && git add -A && git commit -m "chore: scaffold repo and FastAPI backend skeleton" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
`ruff format` rewrites files in place and `ruff check --fix` sorts imports; review the diff before committing.

---

### Task 2: Database layer, identity models and migrations

**Files:**
- Create: `backend/src/assayr/db.py`, `backend/src/assayr/identity/__init__.py` (empty), `backend/src/assayr/identity/models.py`, `backend/src/assayr/models.py`, `backend/src/assayr/migrate.py`, `backend/src/assayr/migrations/env.py`, `backend/src/assayr/migrations/script.py.mako`, `backend/src/assayr/migrations/versions/0001_identity.py`
- Modify: `backend/src/assayr/main.py`, `backend/src/assayr/health.py`, `backend/tests/conftest.py`
- Test: `backend/tests/test_db.py`, `backend/tests/test_migrations.py`

**Interfaces:**
- Consumes: `Settings.database_url`, `create_app()` from Task 1.
- Produces: `assayr.db.Base`, `IdMixin`, `TimestampMixin`, `UTCDateTime`, `utcnow() -> datetime`, `Database(url)` with `.engine` and `.sessionmaker`, `get_session(request) -> Iterator[Session]`; models `Organization`, `Scope`, `User`, `RoleAssignment`, `UserSession` in `assayr.identity.models`; `assayr.migrate.upgrade(url, revision="head")`, `downgrade(url, revision)`, `alembic_config(url)`; `app.state.db`, `app.state.clock` (callable returning aware UTC datetime); fixtures `db` (Session) and `TEST_DB_URL` env support (`ASSAYR_TEST_DATABASE_URL`).

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_db.py`:
```python
from datetime import datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import StatementError

from assayr.identity.models import Organization, RoleAssignment, Scope, User


def test_datetimes_round_trip_as_aware_utc(db):
    db.add(Organization(name="Acme"))
    db.commit()
    db.expunge_all()
    loaded = db.scalar(select(Organization))
    assert loaded.created_at.utcoffset() == timedelta(0)


def test_naive_datetimes_are_rejected(db):
    db.add(Organization(name="Acme", created_at=datetime(2026, 1, 1)))
    with pytest.raises(StatementError, match="Naive datetimes"):
        db.commit()


def test_deleting_a_user_removes_their_role_assignments(db):
    org = Organization(name="Acme")
    db.add(org)
    db.flush()
    scope = Scope(organization_id=org.id, name="HQ", is_default=True)
    db.add(scope)
    db.flush()
    user = User(email="a@acme.com", full_name="A", role_assignments=[RoleAssignment(role="viewer", scope_id=scope.id)])
    db.add(user)
    db.commit()
    db.delete(user)
    db.commit()
    assert db.scalar(select(func.count()).select_from(RoleAssignment)) == 0


def test_readyz_ok(client):
    response = client.get("/api/v1/readyz")
    assert response.status_code == 200
    assert response.json() == {"status": "ready", "database": "ok"}


def test_readyz_reports_unreachable_database(settings):
    from fastapi.testclient import TestClient

    from assayr.main import create_app

    broken = create_app(settings.model_copy(update={"database_url": "sqlite+pysqlite:////no-such-dir/x.db"}))
    with TestClient(broken) as client:
        response = client.get("/api/v1/readyz")
    assert response.status_code == 503
    assert response.json() == {"status": "unavailable", "database": "unreachable"}
```

`backend/tests/test_migrations.py`:
```python
import os

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect

import assayr.models  # noqa: F401  (registers every table on Base.metadata)
from assayr.db import Base
from assayr.migrate import alembic_config, downgrade, upgrade

STRUCTURAL = {"add_table", "remove_table", "add_column", "remove_column"}


def migration_url(tmp_path) -> str:
    return os.environ.get("ASSAYR_TEST_DATABASE_URL") or f"sqlite+pysqlite:///{(tmp_path / 'm.db').as_posix()}"


def clean(engine) -> None:
    Base.metadata.drop_all(engine)
    with engine.begin() as conn:
        conn.exec_driver_sql("DROP TABLE IF EXISTS alembic_version")


def test_migrations_match_models_and_downgrade_cleanly(tmp_path):
    url = migration_url(tmp_path)
    engine = create_engine(url)
    clean(engine)
    upgrade(url)
    with engine.connect() as conn:
        diffs = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    structural = [d for d in diffs if isinstance(d, tuple) and d[0] in STRUCTURAL]
    assert structural == []
    downgrade(url, "base")
    assert set(inspect(engine).get_table_names()) <= {"alembic_version"}
    engine.dispose()


def test_alembic_config_keeps_percent_signs_in_passwords():
    url = "postgresql+pg8000://assayr:p%40ss@db/assayr"
    assert alembic_config(url).get_main_option("sqlalchemy.url") == url
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && cd backend && uv run pytest tests/test_db.py tests/test_migrations.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'assayr.identity'`.

- [ ] **Step 3: Implement the database layer**

`backend/src/assayr/db.py`:
```python
"""Database engine, session factory and shared column types."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime

from fastapi import Request
from sqlalchemy import DateTime, MetaData, Uuid, create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.types import TypeDecorator

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


def utcnow() -> datetime:
    return datetime.now(UTC)


class UTCDateTime(TypeDecorator[datetime]):
    """Timezone-aware UTC datetimes on every backend (SQLite drops tzinfo on storage)."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("Naive datetimes are not allowed; use timezone-aware UTC values.")
        return value.astimezone(UTC)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class IdMixin:
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)


class Database:
    def __init__(self, url: str) -> None:
        kwargs: dict = {}
        if url.startswith("sqlite"):
            kwargs["connect_args"] = {"check_same_thread": False}
            if ":memory:" in url:
                kwargs["poolclass"] = StaticPool
        self.engine: Engine = create_engine(url, **kwargs)
        if url.startswith("sqlite"):
            event.listen(self.engine, "connect", _sqlite_pragmas)
        self.sessionmaker = sessionmaker(self.engine, expire_on_commit=False)


def _sqlite_pragmas(dbapi_connection, _record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def get_session(request: Request) -> Iterator[Session]:
    with request.app.state.db.sessionmaker() as session:
        yield session
```

`backend/src/assayr/identity/models.py`:
```python
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from assayr.db import Base, IdMixin, TimestampMixin, UTCDateTime


class Organization(IdMixin, TimestampMixin, Base):
    __tablename__ = "organization"

    name: Mapped[str] = mapped_column(String(200))
    aliases: Mapped[list[str]] = mapped_column(JSON, default=list)


class Scope(IdMixin, TimestampMixin, Base):
    __tablename__ = "scope"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organization.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(200))
    is_default: Mapped[bool] = mapped_column(default=False)


class User(IdMixin, TimestampMixin, Base):
    __tablename__ = "user_account"

    email: Mapped[str] = mapped_column(String(320), unique=True)
    full_name: Mapped[str] = mapped_column(String(200))
    password_hash: Mapped[str | None] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(default=True)
    failed_logins: Mapped[int] = mapped_column(default=0)
    locked_until: Mapped[datetime | None] = mapped_column(UTCDateTime)
    last_login_at: Mapped[datetime | None] = mapped_column(UTCDateTime)

    role_assignments: Mapped[list[RoleAssignment]] = relationship(
        back_populates="user", cascade="all, delete-orphan", lazy="selectin"
    )


class RoleAssignment(IdMixin, Base):
    __tablename__ = "role_assignment"
    __table_args__ = (UniqueConstraint("user_id", "role", "scope_id", name="uq_role_assignment_user_role_scope"),)

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_account.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(String(40))
    scope_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("scope.id", ondelete="CASCADE"))

    user: Mapped[User] = relationship(back_populates="role_assignments")


class UserSession(Base):
    """A signed-in browser session. `id` is the SHA-256 of the cookie token, never the token itself."""

    __tablename__ = "user_session"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_account.id", ondelete="CASCADE"), index=True)
    csrf_token: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)
    last_seen_at: Mapped[datetime] = mapped_column(UTCDateTime)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime)
    ip: Mapped[str | None] = mapped_column(String(45))
```

`backend/src/assayr/models.py`:
```python
"""Import every model module so Base.metadata is complete (used by create_all and Alembic)."""

from assayr.identity.models import Organization, RoleAssignment, Scope, User, UserSession  # noqa: F401
```

`backend/src/assayr/migrate.py`:
```python
from pathlib import Path

from alembic import command
from alembic.config import Config

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


def alembic_config(url: str) -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", str(MIGRATIONS_DIR))
    # ConfigParser treats % as interpolation; URL-encoded passwords contain %.
    cfg.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    return cfg


def upgrade(url: str, revision: str = "head") -> None:
    command.upgrade(alembic_config(url), revision)


def downgrade(url: str, revision: str) -> None:
    command.downgrade(alembic_config(url), revision)
```

`backend/src/assayr/migrations/env.py`:
```python
from alembic import context
from sqlalchemy import engine_from_config, pool

import assayr.models  # noqa: F401
from assayr.db import Base

config = context.config
target_metadata = Base.metadata


def _run(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=connection.dialect.name == "sqlite",
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = engine_from_config(
        config.get_section(config.config_ini_section, {}), prefix="sqlalchemy.", poolclass=pool.NullPool
    )
    with engine.connect() as connection:
        _run(connection)


if context.is_offline_mode():
    context.configure(url=config.get_main_option("sqlalchemy.url"), target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    run_migrations_online()
```

`backend/src/assayr/migrations/script.py.mako`:
```mako
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}
"""
import sqlalchemy as sa
from alembic import op
${imports if imports else ""}
revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
```

`backend/src/assayr/migrations/versions/0001_identity.py`:
```python
"""identity tables

Revision ID: 0001
Revises:
Create Date: 2026-10-07
"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "organization",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("aliases", sa.JSON(), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_organization"),
    )
    op.create_table(
        "scope",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organization.id"], name="fk_scope_organization_id_organization", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_scope"),
    )
    op.create_table(
        "user_account",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("full_name", sa.String(length=200), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("failed_logins", sa.Integer(), nullable=False),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_user_account"),
        sa.UniqueConstraint("email", name="uq_user_account_email"),
    )
    op.create_table(
        "role_assignment",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=40), nullable=False),
        sa.Column("scope_id", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"], ["user_account.id"], name="fk_role_assignment_user_id_user_account", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["scope_id"], ["scope.id"], name="fk_role_assignment_scope_id_scope", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_role_assignment"),
        sa.UniqueConstraint("user_id", "role", "scope_id", name="uq_role_assignment_user_role_scope"),
    )
    op.create_table(
        "user_session",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("csrf_token", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ip", sa.String(length=45), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"], ["user_account.id"], name="fk_user_session_user_id_user_account", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_user_session"),
    )
    op.create_index("ix_user_session_user_id", "user_session", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_user_session_user_id", table_name="user_session")
    op.drop_table("user_session")
    op.drop_table("role_assignment")
    op.drop_table("user_account")
    op.drop_table("scope")
    op.drop_table("organization")
```

- [ ] **Step 4: Wire the database into the app**

Replace `backend/src/assayr/health.py`:
```python
from fastapi import APIRouter, Request, Response
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from assayr import __version__

router = APIRouter(tags=["health"])


@router.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@router.get("/readyz")
def readyz(request: Request, response: Response) -> dict[str, str]:
    try:
        with request.app.state.db.engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except SQLAlchemyError:
        response.status_code = 503
        return {"status": "unavailable", "database": "unreachable"}
    return {"status": "ready", "database": "ok"}
```

In `backend/src/assayr/main.py`, add imports and two lines after `app.state.settings = settings`:
```python
import assayr.models  # noqa: F401  (top of file, with the other imports)
from assayr.db import Database, utcnow
```
```python
    app.state.db = Database(settings.database_url)
    app.state.clock = utcnow
```

Replace `backend/tests/conftest.py`:
```python
import os
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from assayr.config import Settings
from assayr.db import Base, utcnow
from assayr.main import create_app

TEST_DB_URL = os.environ.get("ASSAYR_TEST_DATABASE_URL", "sqlite+pysqlite:///:memory:")


class FakeClock:
    """Controllable replacement for app.state.clock."""

    def __init__(self) -> None:
        self.now = utcnow()

    def __call__(self):
        return self.now

    def advance(self, **kwargs) -> None:
        self.now += timedelta(**kwargs)


@pytest.fixture
def settings() -> Settings:
    return Settings(database_url=TEST_DB_URL, secure_cookies=False, org_name="Acme Financial Services")


@pytest.fixture
def app(settings):
    application = create_app(settings)
    engine = application.state.db.engine
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield application
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def client(app):
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def db(app):
    with app.state.db.sessionmaker() as session:
        yield session


@pytest.fixture
def clock(app) -> FakeClock:
    fake = FakeClock()
    app.state.clock = fake
    return fake
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && cd backend && uv run pytest`
Expected: all tests pass (`10 passed`).

- [ ] **Step 6: Commit**

```bash
cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && (cd backend && uv run ruff format . && uv run ruff check --fix .) && git add -A && git commit -m "feat(backend): database layer, identity models and first migration" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Password hashing, tokens and email normalisation

**Files:**
- Create: `backend/src/assayr/identity/security.py`
- Test: `backend/tests/test_security.py`

**Interfaces:**
- Produces: `WeakPasswordError(ValueError)`, `MIN_PASSWORD_LENGTH = 12`, `MAX_PASSWORD_LENGTH = 256`, `validate_password(pw) -> None`, `hash_password(pw) -> str`, `verify_password(hash_, pw) -> bool`, `needs_rehash(hash_) -> bool`, `dummy_hash() -> str`, `new_token() -> str`, `token_digest(token) -> str` (64-char hex), `normalize_email(email) -> str`.

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_security.py`:
```python
import pytest

from assayr.identity.security import (
    WeakPasswordError,
    hash_password,
    needs_rehash,
    new_token,
    normalize_email,
    token_digest,
    verify_password,
)


def test_hash_and_verify_round_trip():
    hashed = hash_password("correct-horse-battery")
    assert hashed.startswith("$argon2id$")
    assert verify_password(hashed, "correct-horse-battery")
    assert not verify_password(hashed, "wrong-horse-battery")
    assert not needs_rehash(hashed)


def test_short_password_is_rejected_with_a_clear_message():
    with pytest.raises(WeakPasswordError, match="Use at least 12 characters"):
        hash_password("short")


def test_overlong_password_is_rejected():
    with pytest.raises(WeakPasswordError, match="256 characters or fewer"):
        hash_password("x" * 257)


def test_verify_returns_false_for_garbage_hash():
    assert verify_password("not-a-hash", "whatever-password") is False


def test_email_is_trimmed_and_lowercased():
    assert normalize_email("  Sana.Malik@ACME.com ") == "sana.malik@acme.com"


def test_tokens_are_unique_and_digests_stable():
    first, second = new_token(), new_token()
    assert first != second
    assert token_digest(first) == token_digest(first)
    assert len(token_digest(first)) == 64
```

- [ ] **Step 2: Run to verify failure**

Run: `cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && cd backend && uv run pytest tests/test_security.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'assayr.identity.security'`.

- [ ] **Step 3: Implement**

`backend/src/assayr/identity/security.py`:
```python
"""Password hashing (Argon2id), opaque tokens and identifier normalisation."""

import hashlib
import secrets
from functools import lru_cache

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

MIN_PASSWORD_LENGTH = 12
MAX_PASSWORD_LENGTH = 256

_hasher = PasswordHasher()  # argon2id with the library's current recommended parameters


class WeakPasswordError(ValueError):
    pass


def validate_password(password: str) -> None:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise WeakPasswordError(f"Use at least {MIN_PASSWORD_LENGTH} characters.")
    if len(password) > MAX_PASSWORD_LENGTH:
        raise WeakPasswordError(f"Use {MAX_PASSWORD_LENGTH} characters or fewer.")


def hash_password(password: str) -> str:
    validate_password(password)
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


@lru_cache
def dummy_hash() -> str:
    """A real hash to verify against when the user does not exist, so timing doesn't reveal it."""
    return _hasher.hash("timing-equaliser-not-a-real-password")


def new_token() -> str:
    return secrets.token_urlsafe(32)


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def normalize_email(email: str) -> str:
    return email.strip().lower()
```

- [ ] **Step 4: Run to verify pass**

Run: `cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && cd backend && uv run pytest tests/test_security.py`
Expected: `6 passed`.

- [ ] **Step 5: Commit**

```bash
cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && (cd backend && uv run ruff format . && uv run ruff check --fix .) && git add -A && git commit -m "feat(identity): argon2id password hashing and token helpers" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Hash-chained audit log

**Files:**
- Create: `backend/src/assayr/audit/__init__.py` (empty), `backend/src/assayr/audit/models.py`, `backend/src/assayr/audit/service.py`, `backend/src/assayr/migrations/versions/0002_audit_log.py`
- Modify: `backend/src/assayr/models.py`, `backend/tests/test_migrations.py`
- Test: `backend/tests/test_audit.py`

**Interfaces:**
- Consumes: `Base`, `UTCDateTime`, `utcnow` (Task 2).
- Produces: `AuditLog` model; `assayr.audit.service.GENESIS` (64 zeros); `Actor(id: UUID | None, email: str | None, ip: str | None = None, request_id: str | None = None)`; `SYSTEM = Actor(id=None, email="system")`; `record(session, actor, action, entity_type, entity_id=None, diff=None, reason=None, at=None) -> AuditLog` (flushes, does not commit); `verify_chain(session) -> ChainCheck(ok: bool, checked: int, first_bad_seq: int | None)`.

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_audit.py`:
```python
from sqlalchemy import delete, update

from assayr.audit.models import AuditLog
from assayr.audit.service import GENESIS, SYSTEM, record, verify_chain


def test_entries_chain_to_each_other(db):
    first = record(db, SYSTEM, "test.one", "thing", "1")
    second = record(db, SYSTEM, "test.two", "thing", "2", diff={"x": [1, 2]})
    db.commit()
    assert first.prev_hash == GENESIS
    assert second.prev_hash == first.hash
    assert verify_chain(db).ok


def test_empty_log_is_valid(db):
    result = verify_chain(db)
    assert result.ok and result.checked == 0 and result.first_bad_seq is None


def test_verify_detects_an_edited_row(db):
    for n in range(3):
        record(db, SYSTEM, "test.step", "thing", str(n))
    db.commit()
    db.execute(update(AuditLog).where(AuditLog.seq == 2).values(action="test.tampered"))
    db.commit()
    result = verify_chain(db)
    assert not result.ok
    assert result.first_bad_seq == 2


def test_verify_detects_a_deleted_row(db):
    for n in range(3):
        record(db, SYSTEM, "test.step", "thing", str(n))
    db.commit()
    db.execute(delete(AuditLog).where(AuditLog.seq == 2))
    db.commit()
    assert verify_chain(db).first_bad_seq == 3


def test_unicode_and_nested_diffs_survive_a_database_round_trip(db):
    record(db, SYSTEM, "test.unicode", "thing", diff={"title": ["Sécurité", "Security"], "n": {"a": [1, None]}})
    db.commit()
    db.expunge_all()
    assert verify_chain(db).ok
```

Append to `backend/tests/test_migrations.py`:
```python
import pytest
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from assayr.audit.service import SYSTEM, record


@pytest.mark.skipif(
    not os.environ.get("ASSAYR_TEST_DATABASE_URL", "").startswith("postgresql"), reason="PostgreSQL-only trigger"
)
def test_audit_log_is_append_only_on_postgres(tmp_path):
    url = migration_url(tmp_path)
    engine = create_engine(url)
    clean(engine)
    upgrade(url)
    with Session(engine) as session:
        record(session, SYSTEM, "test.write", "thing")
        session.commit()
    with pytest.raises(DBAPIError, match="append-only"):
        with engine.begin() as conn:
            conn.exec_driver_sql("UPDATE audit_log SET action = 'test.changed'")
    downgrade(url, "base")
    engine.dispose()
```
(Move the new imports to the top of the file with the existing ones.)

- [ ] **Step 2: Run to verify failure**

Run: `cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && cd backend && uv run pytest tests/test_audit.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'assayr.audit'`.

- [ ] **Step 3: Implement the model, service and migration**

`backend/src/assayr/audit/models.py`:
```python
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, BigInteger, Index, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from assayr.db import Base, UTCDateTime


class AuditLog(Base):
    """Append-only, hash-chained record of every state change (FR-20, ADR-008)."""

    __tablename__ = "audit_log"
    __table_args__ = (Index("ix_audit_log_entity", "entity_type", "entity_id"),)

    seq: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    at: Mapped[datetime] = mapped_column(UTCDateTime)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    actor_email: Mapped[str | None] = mapped_column(String(320))
    ip: Mapped[str | None] = mapped_column(String(45))
    action: Mapped[str] = mapped_column(String(80))
    entity_type: Mapped[str] = mapped_column(String(60))
    entity_id: Mapped[str | None] = mapped_column(String(80))
    diff: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    reason: Mapped[str | None] = mapped_column(Text)
    request_id: Mapped[str | None] = mapped_column(String(64))
    prev_hash: Mapped[str] = mapped_column(String(64))
    hash: Mapped[str] = mapped_column(String(64))
```

`backend/src/assayr/audit/service.py`:
```python
"""Writing and verifying the hash-chained audit trail."""

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from assayr.audit.models import AuditLog
from assayr.db import utcnow

GENESIS = "0" * 64
_ADVISORY_LOCK_KEY = 727274  # serialises chain appends on PostgreSQL


@dataclass(frozen=True)
class Actor:
    id: uuid.UUID | None
    email: str | None
    ip: str | None = None
    request_id: str | None = None


SYSTEM = Actor(id=None, email="system")


@dataclass(frozen=True)
class ChainCheck:
    ok: bool
    checked: int
    first_bad_seq: int | None


def _canonical(entry: AuditLog) -> str:
    payload = {
        "at": entry.at.astimezone(UTC).isoformat(timespec="microseconds"),
        "actor_id": str(entry.actor_id) if entry.actor_id else None,
        "actor_email": entry.actor_email,
        "ip": entry.ip,
        "action": entry.action,
        "entity_type": entry.entity_type,
        "entity_id": entry.entity_id,
        "diff": entry.diff,
        "reason": entry.reason,
        "request_id": entry.request_id,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def compute_hash(prev_hash: str, entry: AuditLog) -> str:
    return hashlib.sha256((prev_hash + _canonical(entry)).encode()).hexdigest()


def record(
    session: Session,
    actor: Actor,
    action: str,
    entity_type: str,
    entity_id: str | None = None,
    diff: dict[str, Any] | None = None,
    reason: str | None = None,
    at: datetime | None = None,
) -> AuditLog:
    """Append one entry. Flushes but does not commit: it joins the caller's transaction."""
    if session.get_bind().dialect.name == "postgresql":
        session.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": _ADVISORY_LOCK_KEY})
    last = session.scalar(select(AuditLog).order_by(AuditLog.seq.desc()).limit(1))
    prev_hash = last.hash if last else GENESIS
    entry = AuditLog(
        at=at or utcnow(),
        actor_id=actor.id,
        actor_email=actor.email,
        ip=actor.ip,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        diff=diff,
        reason=reason,
        request_id=actor.request_id,
        prev_hash=prev_hash,
        hash="",
    )
    entry.hash = compute_hash(prev_hash, entry)
    session.add(entry)
    session.flush()
    return entry


def verify_chain(session: Session) -> ChainCheck:
    prev_hash = GENESIS
    checked = 0
    for entry in session.scalars(select(AuditLog).order_by(AuditLog.seq).execution_options(yield_per=1000)):
        if entry.prev_hash != prev_hash or compute_hash(prev_hash, entry) != entry.hash:
            return ChainCheck(ok=False, checked=checked, first_bad_seq=entry.seq)
        prev_hash = entry.hash
        checked += 1
    return ChainCheck(ok=True, checked=checked, first_bad_seq=None)
```
`backend/src/assayr/migrations/versions/0002_audit_log.py`:
```python
"""audit log

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-07
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

_PG_FUNCTION = """
CREATE OR REPLACE FUNCTION audit_log_append_only() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'audit_log is append-only';
END
$$;
"""
_PG_TRIGGER = """
CREATE TRIGGER audit_log_no_change BEFORE UPDATE OR DELETE ON audit_log
FOR EACH ROW EXECUTE FUNCTION audit_log_append_only();
"""


def upgrade() -> None:
    op.create_table(
        "audit_log",
        sa.Column("seq", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), autoincrement=True, nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("actor_email", sa.String(length=320), nullable=True),
        sa.Column("ip", sa.String(length=45), nullable=True),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("entity_type", sa.String(length=60), nullable=False),
        sa.Column("entity_id", sa.String(length=80), nullable=True),
        sa.Column("diff", sa.JSON(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("request_id", sa.String(length=64), nullable=True),
        sa.Column("prev_hash", sa.String(length=64), nullable=False),
        sa.Column("hash", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("seq", name="pk_audit_log"),
    )
    op.create_index("ix_audit_log_entity", "audit_log", ["entity_type", "entity_id"])
    if op.get_bind().dialect.name == "postgresql":
        op.execute(_PG_FUNCTION)
        op.execute(_PG_TRIGGER)


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS audit_log_no_change ON audit_log")
        op.execute("DROP FUNCTION IF EXISTS audit_log_append_only()")
    op.drop_index("ix_audit_log_entity", table_name="audit_log")
    op.drop_table("audit_log")
```

Append to `backend/src/assayr/models.py`:
```python
from assayr.audit.models import AuditLog  # noqa: F401
```

- [ ] **Step 4: Run to verify pass**

Run: `cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && cd backend && uv run pytest`
Expected: all pass; the PostgreSQL-only test is reported as skipped.

- [ ] **Step 5: Commit**

```bash
cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && (cd backend && uv run ruff format . && uv run ruff check --fix .) && git add -A && git commit -m "feat(audit): hash-chained append-only audit log" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Role and permission model

**Files:**
- Create: `backend/src/assayr/identity/rbac.py`
- Test: `backend/tests/test_rbac.py`

**Interfaces:**
- Produces: `Role` (StrEnum: `platform_admin`, `isms_manager`, `control_owner`, `risk_owner`, `contributor`, `internal_auditor`, `external_auditor`, `executive`, `employee`, `viewer`); `Perm` (StrEnum: `controls:read`, `controls:write`, `controls:write_own`, `users:manage`, `audit_log:read`, `settings:manage`); `ROLE_PERMISSIONS: dict[Role, frozenset[Perm]]`; `Grant(all_scopes: bool, scope_ids: frozenset[UUID])` with `.allows(scope_id) -> bool` and `.any -> bool`; `grant_for(assignments: Iterable[tuple[str, UUID | None]], perm: Perm) -> Grant`; `permissions_for(assignments) -> list[str]` (sorted).

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_rbac.py`:
```python
import uuid

from assayr.identity.rbac import ROLE_PERMISSIONS, Perm, Role, grant_for, permissions_for


def test_every_role_has_an_entry():
    assert set(ROLE_PERMISSIONS) == set(Role)


def test_global_assignment_grants_every_scope():
    grant = grant_for([("isms_manager", None)], Perm.CONTROLS_WRITE)
    assert grant.all_scopes and grant.allows(uuid.uuid4())


def test_scoped_assignment_only_grants_its_scope():
    scope = uuid.uuid4()
    grant = grant_for([("viewer", scope)], Perm.CONTROLS_READ)
    assert grant.any and not grant.all_scopes
    assert grant.allows(scope)
    assert not grant.allows(uuid.uuid4())


def test_role_without_permission_grants_nothing():
    assert not grant_for([("employee", None)], Perm.CONTROLS_READ).any


def test_unknown_role_strings_are_ignored():
    assert not grant_for([("legacy_role", None)], Perm.CONTROLS_READ).any
    assert permissions_for([("legacy_role", None), ("viewer", None)]) == ["controls:read"]


def test_permissions_are_a_sorted_union():
    assert permissions_for([("platform_admin", None), ("isms_manager", None)]) == [
        "audit_log:read",
        "controls:read",
        "controls:write",
        "settings:manage",
        "users:manage",
    ]
```

- [ ] **Step 2: Run to verify failure**

Run: `cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && cd backend && uv run pytest tests/test_rbac.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'assayr.identity.rbac'`.

- [ ] **Step 3: Implement**

`backend/src/assayr/identity/rbac.py`:
```python
"""Roles, permissions and scope-aware grants (see vault: 03-Product/RBAC Matrix.md)."""

import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum


class Role(StrEnum):
    PLATFORM_ADMIN = "platform_admin"
    ISMS_MANAGER = "isms_manager"
    CONTROL_OWNER = "control_owner"
    RISK_OWNER = "risk_owner"
    CONTRIBUTOR = "contributor"
    INTERNAL_AUDITOR = "internal_auditor"
    EXTERNAL_AUDITOR = "external_auditor"
    EXECUTIVE = "executive"
    EMPLOYEE = "employee"
    VIEWER = "viewer"


class Perm(StrEnum):
    CONTROLS_READ = "controls:read"
    CONTROLS_WRITE = "controls:write"
    CONTROLS_WRITE_OWN = "controls:write_own"
    USERS_MANAGE = "users:manage"
    AUDIT_LOG_READ = "audit_log:read"
    SETTINGS_MANAGE = "settings:manage"


ROLE_PERMISSIONS: dict[Role, frozenset[Perm]] = {
    Role.PLATFORM_ADMIN: frozenset({Perm.CONTROLS_READ, Perm.USERS_MANAGE, Perm.SETTINGS_MANAGE, Perm.AUDIT_LOG_READ}),
    Role.ISMS_MANAGER: frozenset({Perm.CONTROLS_READ, Perm.CONTROLS_WRITE, Perm.AUDIT_LOG_READ}),
    Role.CONTROL_OWNER: frozenset({Perm.CONTROLS_READ, Perm.CONTROLS_WRITE_OWN}),
    Role.RISK_OWNER: frozenset({Perm.CONTROLS_READ}),
    Role.CONTRIBUTOR: frozenset({Perm.CONTROLS_READ}),
    Role.INTERNAL_AUDITOR: frozenset({Perm.CONTROLS_READ, Perm.AUDIT_LOG_READ}),
    Role.EXTERNAL_AUDITOR: frozenset({Perm.CONTROLS_READ}),
    Role.EXECUTIVE: frozenset({Perm.CONTROLS_READ}),
    Role.EMPLOYEE: frozenset(),
    Role.VIEWER: frozenset({Perm.CONTROLS_READ}),
}


@dataclass(frozen=True)
class Grant:
    all_scopes: bool
    scope_ids: frozenset[uuid.UUID]

    def allows(self, scope_id: uuid.UUID) -> bool:
        return self.all_scopes or scope_id in self.scope_ids

    @property
    def any(self) -> bool:
        return self.all_scopes or bool(self.scope_ids)


def _role(name: str) -> Role | None:
    try:
        return Role(name)
    except ValueError:
        return None


def grant_for(assignments: Iterable[tuple[str, uuid.UUID | None]], perm: Perm) -> Grant:
    all_scopes = False
    scopes: set[uuid.UUID] = set()
    for role_name, scope_id in assignments:
        role = _role(role_name)
        if role is None or perm not in ROLE_PERMISSIONS[role]:
            continue
        if scope_id is None:
            all_scopes = True
        else:
            scopes.add(scope_id)
    return Grant(all_scopes=all_scopes, scope_ids=frozenset(scopes))


def permissions_for(assignments: Iterable[tuple[str, uuid.UUID | None]]) -> list[str]:
    perms: set[str] = set()
    for role_name, _scope in assignments:
        role = _role(role_name)
        if role is not None:
            perms.update(p.value for p in ROLE_PERMISSIONS[role])
    return sorted(perms)
```

- [ ] **Step 4: Run to verify pass**

Run: `cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && cd backend && uv run pytest tests/test_rbac.py`
Expected: `6 passed`.

- [ ] **Step 5: Commit**

```bash
cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && (cd backend && uv run ruff format . && uv run ruff check --fix .) && git add -A && git commit -m "feat(identity): role and scope-aware permission model" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Sign-in, sessions, CSRF and the current-user dependency

**Files:**
- Create: `backend/src/assayr/identity/schemas.py`, `backend/src/assayr/identity/deps.py`, `backend/src/assayr/identity/auth_router.py`
- Modify: `backend/src/assayr/main.py`, `backend/tests/conftest.py`
- Test: `backend/tests/test_auth.py`

**Interfaces:**
- Consumes: `User`, `UserSession` (Task 2); security helpers (Task 3); `record`, `Actor` (Task 4); `grant_for`, `permissions_for`, `Perm` (Task 5).
- Produces: constants `SESSION_COOKIE = "assayr_session"`, `CSRF_COOKIE = "assayr_csrf"`, `CSRF_HEADER = "X-CSRF-Token"`; dependencies `current_user(request, db) -> User`, `require(perm: Perm) -> Callable[..., Grant]`, helper `actor_for(request, user) -> Actor`, `get_clock(request)`; schemas `UserOut.from_user(user)`, `RoleGrantIn`, `RoleGrantOut`; routes `POST /api/v1/auth/login`, `POST /api/v1/auth/logout` (204), `GET /api/v1/auth/me`; test helpers in conftest `create_user(db, email, password=PASSWORD, roles=(("isms_manager", None),), full_name="Test User", active=True) -> User`, `sign_in(client, email, password=PASSWORD) -> Response` (also sets the CSRF header on the client), constant `PASSWORD = "correct-horse-battery"`.

- [ ] **Step 1: Add test helpers to conftest**

Append to `backend/tests/conftest.py`:
```python
from assayr.identity.models import RoleAssignment, User
from assayr.identity.security import hash_password, normalize_email

PASSWORD = "correct-horse-battery"


def create_user(db, email, password=PASSWORD, roles=(("isms_manager", None),), full_name="Test User", active=True):
    user = User(
        email=normalize_email(email),
        full_name=full_name,
        password_hash=hash_password(password),
        is_active=active,
        role_assignments=[RoleAssignment(role=role, scope_id=scope_id) for role, scope_id in roles],
    )
    db.add(user)
    db.commit()
    return user


def sign_in(client, email, password=PASSWORD):
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    if response.status_code == 200:
        client.headers["X-CSRF-Token"] = client.cookies.get("assayr_csrf")
    return response
```
(Move these imports to the top of the file.)

- [ ] **Step 2: Write the failing tests**

`backend/tests/test_auth.py`:
```python
from sqlalchemy import func, select

from assayr.audit.models import AuditLog
from assayr.identity.models import UserSession
from tests.conftest import PASSWORD, create_user, sign_in

GENERIC = "Email or password is incorrect, or the account is temporarily locked."


def test_login_sets_http_only_session_cookie_and_returns_permissions(client, db):
    create_user(db, "sana@acme.com", full_name="Sana Malik")
    response = sign_in(client, "sana@acme.com")
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "sana@acme.com"
    assert "controls:write" in body["permissions"]
    cookies = response.headers.get_list("set-cookie")
    session_cookie = next(c for c in cookies if c.startswith("assayr_session="))
    assert "HttpOnly" in session_cookie and "SameSite=strict" in session_cookie
    csrf_cookie = next(c for c in cookies if c.startswith("assayr_csrf="))
    assert "HttpOnly" not in csrf_cookie


def test_secure_flag_is_set_when_configured(app, client, db):
    app.state.settings = app.state.settings.model_copy(update={"secure_cookies": True})
    create_user(db, "sana@acme.com")
    response = client.post("/api/v1/auth/login", json={"email": "sana@acme.com", "password": PASSWORD})
    assert all("Secure" in c for c in response.headers.get_list("set-cookie"))


def test_me_requires_a_session(client):
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert response.json() == {"detail": "Not signed in."}


def test_login_is_case_insensitive(client, db):
    create_user(db, "sana@acme.com")
    assert sign_in(client, "  Sana@ACME.com ").status_code == 200


def test_unknown_and_wrong_password_look_identical(client, db):
    create_user(db, "sana@acme.com")
    unknown = sign_in(client, "nobody@acme.com")
    wrong = sign_in(client, "sana@acme.com", "not-the-right-password")
    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json() == wrong.json() == {"detail": GENERIC}


def test_lockout_after_five_failures(client, db, clock):
    create_user(db, "sana@acme.com")
    for _ in range(5):
        assert sign_in(client, "sana@acme.com", "not-the-right-password").status_code == 401
    locked = sign_in(client, "sana@acme.com")
    assert locked.status_code == 401 and locked.json() == {"detail": GENERIC}
    clock.advance(minutes=16)
    assert sign_in(client, "sana@acme.com").status_code == 200


def test_inactive_user_cannot_sign_in(client, db):
    create_user(db, "gone@acme.com", active=False)
    assert sign_in(client, "gone@acme.com").status_code == 401


def test_logout_requires_csrf_and_ends_the_session(client, db):
    create_user(db, "sana@acme.com")
    sign_in(client, "sana@acme.com")
    token = client.headers.pop("X-CSRF-Token")
    assert client.post("/api/v1/auth/logout").status_code == 403
    assert client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": token}).status_code == 204
    assert client.get("/api/v1/auth/me").status_code == 401


def test_idle_session_expires(client, db, clock):
    create_user(db, "sana@acme.com")
    sign_in(client, "sana@acme.com")
    clock.advance(minutes=31)
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert response.json() == {"detail": "Your session has expired. Sign in again."}
    assert db.scalar(select(func.count()).select_from(UserSession)) == 0


def test_active_session_still_ends_after_twelve_hours(client, db, clock):
    create_user(db, "sana@acme.com")
    sign_in(client, "sana@acme.com")
    for _ in range(35):
        clock.advance(minutes=20)
        assert client.get("/api/v1/auth/me").status_code == 200
    clock.advance(minutes=20)
    assert client.get("/api/v1/auth/me").status_code == 401


def test_sign_in_and_failures_are_audited(client, db):
    create_user(db, "sana@acme.com")
    sign_in(client, "sana@acme.com", "not-the-right-password")
    sign_in(client, "sana@acme.com")
    actions = list(db.scalars(select(AuditLog.action).order_by(AuditLog.seq)))
    assert actions == ["auth.login_failed", "auth.login"]
```

Create `backend/tests/__init__.py` (empty) so `from tests.conftest import …` resolves, and add to `pyproject.toml` under `[tool.pytest.ini_options]`:
```toml
pythonpath = ["."]
```

- [ ] **Step 3: Run to verify failure**

Run: `cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && cd backend && uv run pytest tests/test_auth.py`
Expected: FAIL — `404 Not Found` responses (routes do not exist yet).

- [ ] **Step 4: Implement schemas, dependencies and routes**

`backend/src/assayr/identity/schemas.py`:
```python
import uuid

from pydantic import BaseModel, Field

from assayr.identity.models import User
from assayr.identity.rbac import Role, permissions_for

EMAIL_PATTERN = r"^\s*[^@\s]+@[^@\s]+\.[^@\s]+\s*$"


class LoginIn(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=256)


class RoleGrantIn(BaseModel):
    role: Role
    scope_id: uuid.UUID | None = None


class RoleGrantOut(BaseModel):
    role: str
    scope_id: uuid.UUID | None


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    is_active: bool
    roles: list[RoleGrantOut]
    permissions: list[str]

    @classmethod
    def from_user(cls, user: User) -> "UserOut":
        pairs = [(a.role, a.scope_id) for a in user.role_assignments]
        return cls(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            is_active=user.is_active,
            roles=[RoleGrantOut(role=r, scope_id=s) for r, s in pairs],
            permissions=permissions_for(pairs),
        )


class UserCreateIn(BaseModel):
    email: str = Field(max_length=320, pattern=EMAIL_PATTERN)
    full_name: str = Field(min_length=1, max_length=200)
    password: str = Field(max_length=256)
    roles: list[RoleGrantIn] = []


class UserUpdateIn(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=200)
    is_active: bool | None = None
    roles: list[RoleGrantIn] | None = None
```

`backend/src/assayr/identity/deps.py`:
```python
import secrets
from collections.abc import Callable
from datetime import datetime, timedelta

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from assayr.audit.service import Actor
from assayr.db import get_session
from assayr.identity.models import User, UserSession
from assayr.identity.rbac import Grant, Perm, grant_for
from assayr.identity.security import token_digest

SESSION_COOKIE = "assayr_session"
CSRF_COOKIE = "assayr_csrf"
CSRF_HEADER = "X-CSRF-Token"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
_LAST_SEEN_RESOLUTION = timedelta(seconds=60)


def get_clock(request: Request) -> Callable[[], datetime]:
    return request.app.state.clock


def current_user(request: Request, db: Session = Depends(get_session)) -> User:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not signed in.")
    settings = request.app.state.settings
    now = get_clock(request)()
    session = db.get(UserSession, token_digest(token))
    expired = session is not None and (
        now >= session.expires_at or now - session.last_seen_at > timedelta(minutes=settings.session_idle_minutes)
    )
    if session is None or expired:
        if session is not None:
            db.delete(session)
            db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Your session has expired. Sign in again.")
    if request.method not in SAFE_METHODS:
        supplied = request.headers.get(CSRF_HEADER, "")
        if not supplied or not secrets.compare_digest(supplied, session.csrf_token):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Missing or invalid CSRF token. Reload the page and try again.")
    user = db.get(User, session.user_id)
    if user is None or not user.is_active:
        db.delete(session)
        db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Your session has expired. Sign in again.")
    if now - session.last_seen_at > _LAST_SEEN_RESOLUTION:
        session.last_seen_at = now
        db.commit()
    request.state.session_id = session.id
    return user


def require(perm: Perm) -> Callable[..., Grant]:
    def dependency(user: User = Depends(current_user)) -> Grant:
        grant = grant_for(((a.role, a.scope_id) for a in user.role_assignments), perm)
        if not grant.any:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "You don't have permission to do this.")
        return grant

    return dependency


def actor_for(request: Request, user: User | None, email: str | None = None) -> Actor:
    return Actor(
        id=user.id if user else None,
        email=user.email if user else email,
        ip=request.client.host if request.client else None,
        request_id=getattr(request.state, "request_id", None),
    )
```

`backend/src/assayr/identity/auth_router.py`:
```python
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from assayr.audit.service import record
from assayr.db import get_session
from assayr.identity.deps import CSRF_COOKIE, SESSION_COOKIE, actor_for, current_user, get_clock
from assayr.identity.models import User, UserSession
from assayr.identity.schemas import LoginIn, UserOut
from assayr.identity.security import (
    dummy_hash,
    hash_password,
    needs_rehash,
    new_token,
    normalize_email,
    token_digest,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])

GENERIC_FAILURE = "Email or password is incorrect, or the account is temporarily locked."


@router.post("/login", response_model=UserOut)
def login(body: LoginIn, request: Request, response: Response, db: Session = Depends(get_session)) -> UserOut:
    settings = request.app.state.settings
    now = get_clock(request)()
    email = normalize_email(body.email)
    user = db.scalar(select(User).where(User.email == email))

    def fail(reason: str) -> HTTPException:
        record(db, actor_for(request, user, email), "auth.login_failed", "user", str(user.id) if user else None,
               diff={"reason": reason})
        db.commit()
        return HTTPException(status.HTTP_401_UNAUTHORIZED, GENERIC_FAILURE)

    if user is None:
        verify_password(dummy_hash(), body.password)
        raise fail("unknown_user")
    if user.locked_until and user.locked_until > now:
        verify_password(dummy_hash(), body.password)
        raise fail("locked")
    if not user.is_active or not user.password_hash or not verify_password(user.password_hash, body.password):
        user.failed_logins += 1
        if user.failed_logins >= settings.login_max_failures:
            user.locked_until = now + timedelta(minutes=settings.login_lockout_minutes)
            user.failed_logins = 0
        raise fail("inactive" if not user.is_active else "bad_password")

    user.failed_logins = 0
    user.locked_until = None
    user.last_login_at = now
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(body.password)
    token, csrf = new_token(), new_token()
    absolute = timedelta(hours=settings.session_absolute_hours)
    db.add(UserSession(
        id=token_digest(token),
        user_id=user.id,
        csrf_token=csrf,
        created_at=now,
        last_seen_at=now,
        expires_at=now + absolute,
        ip=request.client.host if request.client else None,
    ))
    record(db, actor_for(request, user), "auth.login", "user", str(user.id))
    db.commit()
    max_age = int(absolute.total_seconds())
    response.set_cookie(SESSION_COOKIE, token, max_age=max_age, httponly=True, secure=settings.secure_cookies,
                        samesite="strict", path="/")
    response.set_cookie(CSRF_COOKIE, csrf, max_age=max_age, httponly=False, secure=settings.secure_cookies,
                        samesite="strict", path="/")
    return UserOut.from_user(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, user: User = Depends(current_user), db: Session = Depends(get_session)) -> Response:
    session = db.get(UserSession, request.state.session_id)
    if session is not None:
        db.delete(session)
    record(db, actor_for(request, user), "auth.logout", "user", str(user.id))
    db.commit()
    secure = request.app.state.settings.secure_cookies
    resp = Response(status_code=status.HTTP_204_NO_CONTENT)
    resp.delete_cookie(SESSION_COOKIE, path="/", secure=secure, httponly=True, samesite="strict")
    resp.delete_cookie(CSRF_COOKIE, path="/", secure=secure, samesite="strict")
    return resp


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)) -> UserOut:
    return UserOut.from_user(user)
```
Note: `fail()` closes over `user`, so for unknown users `actor_for(request, None, email)` records the attempted email; for known users it records the account.

In `backend/src/assayr/main.py` add the router:
```python
from assayr.identity.auth_router import router as auth_router
```
```python
    app.include_router(auth_router, prefix="/api/v1")
```

- [ ] **Step 5: Run to verify pass**

Run: `cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && cd backend && uv run pytest`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && (cd backend && uv run ruff format . && uv run ruff check --fix .) && git add -A && git commit -m "feat(identity): local sign-in with sessions, lockout and CSRF" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: User administration and audit-log endpoints

**Files:**
- Create: `backend/src/assayr/identity/users_router.py`, `backend/src/assayr/audit/router.py`
- Modify: `backend/src/assayr/main.py`
- Test: `backend/tests/test_users.py`, `backend/tests/test_audit_api.py`

**Interfaces:**
- Consumes: `current_user`, `require`, `actor_for` (Task 6); `UserCreateIn`, `UserUpdateIn`, `UserOut`; `record`, `verify_chain` (Task 4).
- Produces: `GET /api/v1/users`, `POST /api/v1/users` (201), `PATCH /api/v1/users/{user_id}`; `GET /api/v1/audit-log?limit&before_seq&entity_type&entity_id` → `{items: [...], next_before_seq}`, `GET /api/v1/audit-log/verify` → `{ok, checked, first_bad_seq}`.

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_users.py`:
```python
from fastapi.testclient import TestClient
from sqlalchemy import select

from assayr.audit.models import AuditLog
from tests.conftest import create_user, sign_in

ADMIN = (("platform_admin", None),)


def test_admin_lists_users_and_others_are_forbidden(app, client, db):
    create_user(db, "admin@acme.com", roles=ADMIN)
    create_user(db, "viewer@acme.com", roles=(("viewer", None),))
    sign_in(client, "admin@acme.com")
    assert [u["email"] for u in client.get("/api/v1/users").json()] == ["admin@acme.com", "viewer@acme.com"]
    with TestClient(app) as other:
        sign_in(other, "viewer@acme.com")
        response = other.get("/api/v1/users")
        assert response.status_code == 403
        assert response.json() == {"detail": "You don't have permission to do this."}


def test_created_user_can_sign_in_and_password_is_not_audited(app, client, db):
    create_user(db, "admin@acme.com", roles=ADMIN)
    sign_in(client, "admin@acme.com")
    response = client.post("/api/v1/users", json={
        "email": "Bilal@Acme.com", "full_name": "Bilal Khan", "password": "another-long-password",
        "roles": [{"role": "control_owner"}],
    })
    assert response.status_code == 201
    assert response.json()["email"] == "bilal@acme.com"
    entry = db.scalar(select(AuditLog).where(AuditLog.action == "user.create"))
    assert "another-long-password" not in str(entry.diff)
    with TestClient(app) as bilal:
        assert sign_in(bilal, "bilal@acme.com", "another-long-password").status_code == 200


def test_duplicate_email_rejected_case_insensitively(client, db):
    create_user(db, "admin@acme.com", roles=ADMIN)
    sign_in(client, "admin@acme.com")
    response = client.post("/api/v1/users", json={
        "email": "ADMIN@acme.com", "full_name": "Dup", "password": "another-long-password"})
    assert response.status_code == 409
    assert response.json() == {"detail": "A user with this email already exists."}


def test_weak_password_and_unknown_role_are_rejected(client, db):
    create_user(db, "admin@acme.com", roles=ADMIN)
    sign_in(client, "admin@acme.com")
    weak = client.post("/api/v1/users", json={"email": "x@acme.com", "full_name": "X", "password": "short"})
    assert weak.status_code == 422 and weak.json() == {"detail": "Use at least 12 characters."}
    bad_role = client.post("/api/v1/users", json={
        "email": "y@acme.com", "full_name": "Y", "password": "another-long-password", "roles": [{"role": "wizard"}]})
    assert bad_role.status_code == 422


def test_admin_cannot_deactivate_themselves(client, db):
    admin = create_user(db, "admin@acme.com", roles=ADMIN)
    sign_in(client, "admin@acme.com")
    response = client.patch(f"/api/v1/users/{admin.id}", json={"is_active": False})
    assert response.status_code == 409
    assert response.json() == {"detail": "You can't deactivate your own account."}


def test_deactivating_a_user_ends_their_sessions(app, client, db):
    create_user(db, "admin@acme.com", roles=ADMIN)
    bilal = create_user(db, "bilal@acme.com", roles=(("viewer", None),))
    with TestClient(app) as bilal_client:
        sign_in(bilal_client, "bilal@acme.com")
        sign_in(client, "admin@acme.com")
        assert client.patch(f"/api/v1/users/{bilal.id}", json={"is_active": False}).status_code == 200
        assert bilal_client.get("/api/v1/auth/me").status_code == 401


def test_roles_can_be_replaced_including_re_adding_an_existing_one(client, db):
    create_user(db, "admin@acme.com", roles=ADMIN)
    bilal = create_user(db, "bilal@acme.com", roles=(("viewer", None), ("contributor", None)))
    sign_in(client, "admin@acme.com")
    response = client.patch(f"/api/v1/users/{bilal.id}", json={"roles": [{"role": "viewer"}, {"role": "control_owner"}]})
    assert response.status_code == 200
    assert sorted(r["role"] for r in response.json()["roles"]) == ["control_owner", "viewer"]
```

`backend/tests/test_audit_api.py`:
```python
from sqlalchemy import update

from assayr.audit.models import AuditLog
from tests.conftest import create_user, sign_in


def test_audit_log_lists_newest_first_and_verifies(client, db):
    create_user(db, "sana@acme.com")
    sign_in(client, "sana@acme.com")
    page = client.get("/api/v1/audit-log").json()
    assert page["items"][0]["action"] == "auth.login"
    assert client.get("/api/v1/audit-log/verify").json() == {"ok": True, "checked": 1, "first_bad_seq": None}


def test_verify_reports_tampering(client, db):
    create_user(db, "sana@acme.com")
    sign_in(client, "sana@acme.com")
    db.execute(update(AuditLog).values(actor_email="mallory@acme.com"))
    db.commit()
    assert client.get("/api/v1/audit-log/verify").json()["ok"] is False


def test_audit_log_needs_permission(client, db):
    create_user(db, "viewer@acme.com", roles=(("viewer", None),))
    sign_in(client, "viewer@acme.com")
    assert client.get("/api/v1/audit-log").status_code == 403
```

- [ ] **Step 2: Run to verify failure**

Run: `cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && cd backend && uv run pytest tests/test_users.py tests/test_audit_api.py`
Expected: FAIL (404s).

- [ ] **Step 3: Implement**

`backend/src/assayr/identity/users_router.py`:
```python
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from assayr.audit.service import record
from assayr.db import get_session
from assayr.identity.deps import actor_for, current_user, require
from assayr.identity.models import RoleAssignment, Scope, User, UserSession
from assayr.identity.rbac import Perm, Role
from assayr.identity.schemas import RoleGrantIn, UserCreateIn, UserOut, UserUpdateIn
from assayr.identity.security import WeakPasswordError, hash_password, normalize_email

router = APIRouter(prefix="/users", tags=["users"])


def _desired_roles(db: Session, grants: list[RoleGrantIn]) -> set[tuple[str, uuid.UUID | None]]:
    desired = {(g.role.value, g.scope_id) for g in grants}
    for _role, scope_id in desired:
        if scope_id is not None and db.get(Scope, scope_id) is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Unknown scope.")
    return desired


@router.get("", response_model=list[UserOut])
def list_users(_grant=Depends(require(Perm.USERS_MANAGE)), db: Session = Depends(get_session)) -> list[UserOut]:
    return [UserOut.from_user(u) for u in db.scalars(select(User).order_by(User.email))]


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    body: UserCreateIn,
    request: Request,
    actor: User = Depends(current_user),
    _grant=Depends(require(Perm.USERS_MANAGE)),
    db: Session = Depends(get_session),
) -> UserOut:
    email = normalize_email(body.email)
    if db.scalar(select(User.id).where(User.email == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "A user with this email already exists.")
    try:
        password_hash = hash_password(body.password)
    except WeakPasswordError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    roles = _desired_roles(db, body.roles)
    user = User(
        email=email,
        full_name=body.full_name.strip(),
        password_hash=password_hash,
        role_assignments=[RoleAssignment(role=r, scope_id=s) for r, s in sorted(roles, key=str)],
    )
    db.add(user)
    db.flush()
    record(db, actor_for(request, actor), "user.create", "user", str(user.id),
           diff={"email": [None, email], "roles": [None, sorted(r for r, _ in roles)]})
    db.commit()
    return UserOut.from_user(user)


@router.patch("/{user_id}", response_model=UserOut)
def update_user(
    user_id: uuid.UUID,
    body: UserUpdateIn,
    request: Request,
    actor: User = Depends(current_user),
    _grant=Depends(require(Perm.USERS_MANAGE)),
    db: Session = Depends(get_session),
) -> UserOut:
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found.")
    diff: dict[str, list] = {}
    if body.full_name is not None and body.full_name.strip() != target.full_name:
        diff["full_name"] = [target.full_name, body.full_name.strip()]
        target.full_name = body.full_name.strip()
    if body.is_active is not None and body.is_active != target.is_active:
        if target.id == actor.id and body.is_active is False:
            raise HTTPException(status.HTTP_409_CONFLICT, "You can't deactivate your own account.")
        diff["is_active"] = [target.is_active, body.is_active]
        target.is_active = body.is_active
        if not body.is_active:
            db.execute(delete(UserSession).where(UserSession.user_id == target.id))
    if body.roles is not None:
        desired = _desired_roles(db, body.roles)
        current = {(a.role, a.scope_id) for a in target.role_assignments}
        if target.id == actor.id and (Role.PLATFORM_ADMIN.value, None) in current - desired:
            raise HTTPException(status.HTTP_409_CONFLICT, "You can't remove your own administrator role.")
        if desired != current:
            diff["roles"] = [sorted(r for r, _ in current), sorted(r for r, _ in desired)]
            target.role_assignments = [a for a in target.role_assignments if (a.role, a.scope_id) in desired] + [
                RoleAssignment(role=r, scope_id=s) for r, s in sorted(desired - current, key=str)
            ]
    if diff:
        record(db, actor_for(request, actor), "user.update", "user", str(target.id), diff=diff)
    db.commit()
    return UserOut.from_user(target)
```

`backend/src/assayr/audit/router.py`:
```python
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from assayr.audit.models import AuditLog
from assayr.audit.service import verify_chain
from assayr.db import get_session
from assayr.identity.deps import require
from assayr.identity.rbac import Perm

router = APIRouter(prefix="/audit-log", tags=["audit"])


class AuditEntryOut(BaseModel):
    seq: int
    at: datetime
    actor_id: uuid.UUID | None
    actor_email: str | None
    ip: str | None
    action: str
    entity_type: str
    entity_id: str | None
    diff: dict[str, Any] | None
    reason: str | None
    request_id: str | None
    hash: str


class AuditPage(BaseModel):
    items: list[AuditEntryOut]
    next_before_seq: int | None


class ChainOut(BaseModel):
    ok: bool
    checked: int
    first_bad_seq: int | None


@router.get("", response_model=AuditPage)
def list_entries(
    _grant=Depends(require(Perm.AUDIT_LOG_READ)),
    db: Session = Depends(get_session),
    limit: int = Query(50, ge=1, le=500),
    before_seq: int | None = Query(None, ge=1),
    entity_type: str | None = Query(None, max_length=60),
    entity_id: str | None = Query(None, max_length=80),
) -> AuditPage:
    stmt = select(AuditLog).order_by(AuditLog.seq.desc())
    if before_seq is not None:
        stmt = stmt.where(AuditLog.seq < before_seq)
    if entity_type:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
    if entity_id:
        stmt = stmt.where(AuditLog.entity_id == entity_id)
    rows = list(db.scalars(stmt.limit(limit + 1)))
    items = rows[:limit]
    return AuditPage(
        items=[AuditEntryOut.model_validate(r, from_attributes=True) for r in items],
        next_before_seq=items[-1].seq if len(rows) > limit else None,
    )


@router.get("/verify", response_model=ChainOut)
def verify(_grant=Depends(require(Perm.AUDIT_LOG_READ)), db: Session = Depends(get_session)) -> ChainOut:
    result = verify_chain(db)
    return ChainOut(ok=result.ok, checked=result.checked, first_bad_seq=result.first_bad_seq)
```

In `backend/src/assayr/main.py` add:
```python
from assayr.audit.router import router as audit_router
from assayr.identity.users_router import router as users_router
```
```python
    app.include_router(users_router, prefix="/api/v1")
    app.include_router(audit_router, prefix="/api/v1")
```

- [ ] **Step 4: Run to verify pass**

Run: `cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && cd backend && uv run pytest`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && (cd backend && uv run ruff format . && uv run ruff check --fix .) && git add -A && git commit -m "feat: user administration and audit-log API" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: ISO 27001 catalogue models and idempotent seed

**Files:**
- Create: `backend/src/assayr/catalogue/__init__.py` (empty), `backend/src/assayr/catalogue/models.py`, `backend/src/assayr/catalogue/iso27001_clauses.py`, `backend/src/assayr/catalogue/seed.py`, `backend/src/assayr/catalogue/data/iso27001_2022_annex_a.json` (copied), `backend/src/assayr/migrations/versions/0003_catalogue.py`
- Modify: `backend/src/assayr/models.py`, `backend/tests/conftest.py`
- Test: `backend/tests/test_seed.py`

**Interfaces:**
- Consumes: `Base`, mixins, `Scope`, `Organization`, `User` (Task 2).
- Produces: models `Framework`, `Requirement`, `Control`, `ControlRequirement`, `EvidenceSlot`; `Control.owner` (relationship to `User`), `Control.slots`, `Control.requirements` (view-only); `FRAMEWORK_CODE = "ISO27001:2022"`; `ensure_default_scope(db, org_name) -> Scope`; `seed_iso27001(db, scope, path=SEED_PATH) -> SeedResult(framework_created: bool, requirements_created: int, controls_created: int, slots_created: int)`; fixture `seeded` → default `Scope` with 93 controls.

- [ ] **Step 1: Copy the seed data**

```bash
mkdir -p "E:/Work/GRC Tool/assayr/backend/src/assayr/catalogue/data" && cp "E:/Work/GRC Tool/Assayr-Vault/_data/annex_a_controls.json" "E:/Work/GRC Tool/assayr/backend/src/assayr/catalogue/data/iso27001_2022_annex_a.json"
```

- [ ] **Step 2: Write the failing tests**

Append to `backend/tests/conftest.py`:
```python
from assayr.catalogue.seed import ensure_default_scope, seed_iso27001


@pytest.fixture
def seeded(db, settings):
    scope = ensure_default_scope(db, settings.org_name)
    seed_iso27001(db, scope)
    db.commit()
    return scope
```
(Move the import to the top of the file.)

`backend/tests/test_seed.py`:
```python
from sqlalchemy import func, select

from assayr.catalogue.models import Control, Requirement
from assayr.catalogue.seed import ensure_default_scope, seed_iso27001
from assayr.identity.models import Organization


def count(db, model, *where):
    return db.scalar(select(func.count()).select_from(model).where(*where))


def test_seed_creates_clauses_themes_and_all_93_controls(db, seeded):
    assert count(db, Requirement, Requirement.kind.in_(["clause_group", "clause"])) == 41
    assert count(db, Requirement, Requirement.kind == "theme") == 4
    assert count(db, Requirement, Requirement.kind == "annex_control") == 93
    assert count(db, Control, Control.scope_id == seeded.id) == 93


def test_controls_carry_slots_rules_and_freshness(db, seeded):
    db.expunge_all()
    backup = db.scalar(select(Control).where(Control.code == "A.8.13"))
    assert backup.title == "Information backup"
    assert backup.theme == "Technological"
    assert backup.status == "not_started"
    assert [s.name for s in backup.slots] == ["Backup policy", "Backup job success report", "Restore test record"]
    assert all(s.freshness_days == 31 for s in backup.slots)
    assert "V-FRESH" in backup.slots[0].rules
    assert [r.ref for r in backup.requirements] == ["A.8.13"]


def test_controls_are_in_natural_order(db, seeded):
    codes = list(db.scalars(select(Control.code).order_by(Control.sort_order).limit(11)))
    assert codes[:3] == ["A.5.1", "A.5.2", "A.5.3"]
    assert codes[9] == "A.5.10"


def test_seed_is_idempotent_and_preserves_edits(db, seeded, settings):
    control = db.scalar(select(Control).where(Control.code == "A.5.1"))
    control.implementation_status = "implemented"
    control.implementation_text = "Approved by the board in January."
    db.commit()
    again = seed_iso27001(db, ensure_default_scope(db, settings.org_name))
    db.commit()
    assert (again.framework_created, again.requirements_created, again.controls_created) == (False, 0, 0)
    assert count(db, Control) == 93
    db.expunge_all()
    reloaded = db.scalar(select(Control).where(Control.code == "A.5.1"))
    assert reloaded.implementation_status == "implemented"
    assert reloaded.implementation_text == "Approved by the board in January."


def test_default_scope_is_created_once_with_the_configured_name(db, settings):
    first = ensure_default_scope(db, settings.org_name)
    second = ensure_default_scope(db, "Something else")
    db.commit()
    assert first.id == second.id
    assert db.scalar(select(Organization.name)) == "Acme Financial Services"
```

- [ ] **Step 3: Run to verify failure**

Run: `cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && cd backend && uv run pytest tests/test_seed.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'assayr.catalogue'`.

- [ ] **Step 4: Implement models, clauses, seed and migration**

`backend/src/assayr/catalogue/models.py`:
```python
from __future__ import annotations

import uuid

from sqlalchemy import JSON, Float, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from assayr.db import Base, IdMixin, TimestampMixin
from assayr.identity.models import User


class Framework(IdMixin, TimestampMixin, Base):
    __tablename__ = "framework"

    code: Mapped[str] = mapped_column(String(60), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    version: Mapped[str] = mapped_column(String(20))


class Requirement(IdMixin, Base):
    """Something a framework asks for: a clause, a clause group, an Annex A theme or an Annex A control."""

    __tablename__ = "requirement"
    __table_args__ = (UniqueConstraint("framework_id", "ref", name="uq_requirement_framework_ref"),)

    framework_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("framework.id", ondelete="CASCADE"))
    ref: Mapped[str] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(300))
    kind: Mapped[str] = mapped_column(String(20))
    parent_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("requirement.id", ondelete="CASCADE"))
    attributes: Mapped[dict] = mapped_column(JSON, default=dict)
    guidance: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(default=0)


class ControlRequirement(Base):
    __tablename__ = "control_requirement"

    control_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("control.id", ondelete="CASCADE"), primary_key=True)
    requirement_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("requirement.id", ondelete="CASCADE"), primary_key=True
    )
    coverage: Mapped[str] = mapped_column(String(10), default="full")


class Control(IdMixin, TimestampMixin, Base):
    """What the organization does. Mapped to one or more requirements (ADR-006)."""

    __tablename__ = "control"
    __table_args__ = (
        UniqueConstraint("scope_id", "code", name="uq_control_scope_code"),
        Index("ix_control_scope_sort", "scope_id", "sort_order"),
    )

    scope_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("scope.id", ondelete="CASCADE"))
    code: Mapped[str] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(300))
    theme: Mapped[str | None] = mapped_column(String(40))
    description: Mapped[str | None] = mapped_column(Text)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user_account.id", ondelete="SET NULL"))
    default_owner_role: Mapped[str | None] = mapped_column(String(60))
    review_frequency: Mapped[str | None] = mapped_column(String(30))
    implementation_status: Mapped[str] = mapped_column(String(30), default="not_started")
    implementation_text: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="not_started")
    sort_order: Mapped[int] = mapped_column(default=0)

    owner: Mapped[User | None] = relationship(lazy="joined")
    slots: Mapped[list[EvidenceSlot]] = relationship(
        back_populates="control", cascade="all, delete-orphan", lazy="selectin", order_by="EvidenceSlot.sort_order"
    )
    requirements: Mapped[list[Requirement]] = relationship(
        secondary="control_requirement", lazy="selectin", viewonly=True, order_by="Requirement.sort_order"
    )


class EvidenceSlot(IdMixin, Base):
    """A named piece of evidence a control needs, with freshness and verification rules."""

    __tablename__ = "evidence_slot"

    control_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("control.id", ondelete="CASCADE"))
    requirement_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("requirement.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(300))
    evidence_type: Mapped[str] = mapped_column(String(40))
    required: Mapped[bool] = mapped_column(default=True)
    freshness_days: Mapped[int | None] = mapped_column()
    min_confidence: Mapped[float | None] = mapped_column(Float)
    rules: Mapped[list[str]] = mapped_column(JSON, default=list)
    required_concepts: Mapped[list[str]] = mapped_column(JSON, default=list)
    sort_order: Mapped[int] = mapped_column(default=0)

    control: Mapped[Control | None] = relationship(back_populates="slots")
```

`backend/src/assayr/catalogue/iso27001_clauses.py`:
```python
"""ISO/IEC 27001:2022 management-system clause identifiers and headings: (ref, title, parent_ref)."""

CLAUSES: list[tuple[str, str, str | None]] = [
    ("4", "Context of the organization", None),
    ("4.1", "Understanding the organization and its context", "4"),
    ("4.2", "Understanding the needs and expectations of interested parties", "4"),
    ("4.3", "Determining the scope of the information security management system", "4"),
    ("4.4", "Information security management system", "4"),
    ("5", "Leadership", None),
    ("5.1", "Leadership and commitment", "5"),
    ("5.2", "Policy", "5"),
    ("5.3", "Organizational roles, responsibilities and authorities", "5"),
    ("6", "Planning", None),
    ("6.1", "Actions to address risks and opportunities", "6"),
    ("6.1.1", "General", "6.1"),
    ("6.1.2", "Information security risk assessment", "6.1"),
    ("6.1.3", "Information security risk treatment", "6.1"),
    ("6.2", "Information security objectives and planning to achieve them", "6"),
    ("6.3", "Planning of changes", "6"),
    ("7", "Support", None),
    ("7.1", "Resources", "7"),
    ("7.2", "Competence", "7"),
    ("7.3", "Awareness", "7"),
    ("7.4", "Communication", "7"),
    ("7.5", "Documented information", "7"),
    ("7.5.1", "General", "7.5"),
    ("7.5.2", "Creating and updating", "7.5"),
    ("7.5.3", "Control of documented information", "7.5"),
    ("8", "Operation", None),
    ("8.1", "Operational planning and control", "8"),
    ("8.2", "Information security risk assessment", "8"),
    ("8.3", "Information security risk treatment", "8"),
    ("9", "Performance evaluation", None),
    ("9.1", "Monitoring, measurement, analysis and evaluation", "9"),
    ("9.2", "Internal audit", "9"),
    ("9.2.1", "General", "9.2"),
    ("9.2.2", "Internal audit programme", "9.2"),
    ("9.3", "Management review", "9"),
    ("9.3.1", "General", "9.3"),
    ("9.3.2", "Management review inputs", "9.3"),
    ("9.3.3", "Management review results", "9.3"),
    ("10", "Improvement", None),
    ("10.1", "Continual improvement", "10"),
    ("10.2", "Nonconformity and corrective action", "10"),
]
```

`backend/src/assayr/catalogue/seed.py`:
```python
"""Load the ISO/IEC 27001:2022 catalogue. Safe to run on every start: it only adds what is missing."""

import json
import uuid
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from assayr.catalogue.iso27001_clauses import CLAUSES
from assayr.catalogue.models import Control, ControlRequirement, EvidenceSlot, Framework, Requirement
from assayr.identity.models import Organization, Scope

SEED_PATH = Path(__file__).resolve().parent / "data" / "iso27001_2022_annex_a.json"
FRAMEWORK_CODE = "ISO27001:2022"
THEME_REF = {"Organizational": "A.5", "People": "A.6", "Physical": "A.7", "Technological": "A.8"}
THEME_TITLE = {
    "A.5": "Organizational controls",
    "A.6": "People controls",
    "A.7": "Physical controls",
    "A.8": "Technological controls",
}
FREQ_DAYS = {
    "Annual": 365, "Semi-annual": 182, "Quarterly": 90, "Monthly": 31, "Continuous": 31,
    "Per release": 90, "Per event": 365, "Per hire": 365, "Per contract": 365, "Per project": 365, "Per audit": 365,
}


@dataclass
class SeedResult:
    framework_created: bool = False
    requirements_created: int = 0
    controls_created: int = 0
    slots_created: int = 0


def ensure_default_scope(db: Session, org_name: str) -> Scope:
    scope = db.scalar(select(Scope).where(Scope.is_default.is_(True)))
    if scope is not None:
        return scope
    org = db.scalar(select(Organization))
    if org is None:
        org = Organization(id=uuid.uuid4(), name=org_name, aliases=[])
        db.add(org)
    scope = Scope(id=uuid.uuid4(), organization_id=org.id, name="Default ISMS scope", is_default=True)
    db.add(scope)
    db.flush()
    return scope


def seed_iso27001(db: Session, scope: Scope, path: Path = SEED_PATH) -> SeedResult:
    data = json.loads(path.read_text(encoding="utf-8"))
    result = SeedResult()

    framework = db.scalar(select(Framework).where(Framework.code == FRAMEWORK_CODE))
    if framework is None:
        framework = Framework(id=uuid.uuid4(), code=FRAMEWORK_CODE, name="ISO/IEC 27001", version="2022")
        db.add(framework)
        result.framework_created = True

    requirements = {r.ref: r for r in db.scalars(select(Requirement).where(Requirement.framework_id == framework.id))}
    order = 0

    def ensure(ref: str, title: str, kind: str, parent_ref: str | None, attributes=None, guidance=None) -> Requirement:
        nonlocal order
        order += 1
        if ref in requirements:
            return requirements[ref]
        req = Requirement(
            id=uuid.uuid4(), framework_id=framework.id, ref=ref, title=title, kind=kind,
            parent_id=requirements[parent_ref].id if parent_ref else None,
            attributes=attributes or {}, guidance=guidance, sort_order=order,
        )
        db.add(req)
        requirements[ref] = req
        result.requirements_created += 1
        return req

    for ref, title, parent in CLAUSES:
        ensure(ref, title, "clause" if parent else "clause_group", parent)
    for theme_ref, theme_title in THEME_TITLE.items():
        ensure(theme_ref, theme_title, "theme", None)

    existing = set(db.scalars(select(Control.code).where(Control.scope_id == scope.id)))
    for index, item in enumerate(data["controls"], start=1):
        req = ensure(
            item["ref"], item["title"], "annex_control", THEME_REF[item["theme"]],
            attributes={
                "control_type": item["control_type"],
                "security_properties": item["security_properties"],
                "cybersecurity_concepts": item["cybersecurity_concepts"],
                "new_in_2022": item["new_in_2022"],
            },
            guidance=item["intent"],
        )
        if item["ref"] in existing:
            continue
        control = Control(
            id=uuid.uuid4(), scope_id=scope.id, code=item["ref"], title=item["title"], theme=item["theme"],
            description=item["intent"], default_owner_role=item["default_owner_role"],
            review_frequency=item["review_frequency"], sort_order=index,
        )
        for slot_index, evidence in enumerate(item["evidence_requirements"], start=1):
            control.slots.append(EvidenceSlot(
                id=uuid.uuid4(), name=evidence["example"], evidence_type=evidence["type"], required=True,
                freshness_days=FREQ_DAYS.get(item["review_frequency"]),
                rules=list(item["verification"]["rules"]),
                required_concepts=list(item["verification"]["required_concepts"]),
                sort_order=slot_index,
            ))
            result.slots_created += 1
        db.add(control)
        db.add(ControlRequirement(control_id=control.id, requirement_id=req.id))
        result.controls_created += 1

    db.flush()
    return result
```

`backend/src/assayr/migrations/versions/0003_catalogue.py`:
```python
"""catalogue: frameworks, requirements, controls, evidence slots

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-07
"""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "framework",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=60), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("version", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_framework"),
        sa.UniqueConstraint("code", name="uq_framework_code"),
    )
    op.create_table(
        "requirement",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("framework_id", sa.Uuid(), nullable=False),
        sa.Column("ref", sa.String(length=20), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("parent_id", sa.Uuid(), nullable=True),
        sa.Column("attributes", sa.JSON(), nullable=False),
        sa.Column("guidance", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["framework_id"], ["framework.id"], name="fk_requirement_framework_id_framework",
                                ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parent_id"], ["requirement.id"], name="fk_requirement_parent_id_requirement",
                                ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_requirement"),
        sa.UniqueConstraint("framework_id", "ref", name="uq_requirement_framework_ref"),
    )
    op.create_table(
        "control",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("scope_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("theme", sa.String(length=40), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("owner_id", sa.Uuid(), nullable=True),
        sa.Column("default_owner_role", sa.String(length=60), nullable=True),
        sa.Column("review_frequency", sa.String(length=30), nullable=True),
        sa.Column("implementation_status", sa.String(length=30), nullable=False),
        sa.Column("implementation_text", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["scope_id"], ["scope.id"], name="fk_control_scope_id_scope", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["owner_id"], ["user_account.id"], name="fk_control_owner_id_user_account",
                                ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_control"),
        sa.UniqueConstraint("scope_id", "code", name="uq_control_scope_code"),
    )
    op.create_index("ix_control_scope_sort", "control", ["scope_id", "sort_order"])
    op.create_table(
        "control_requirement",
        sa.Column("control_id", sa.Uuid(), nullable=False),
        sa.Column("requirement_id", sa.Uuid(), nullable=False),
        sa.Column("coverage", sa.String(length=10), nullable=False),
        sa.ForeignKeyConstraint(["control_id"], ["control.id"], name="fk_control_requirement_control_id_control",
                                ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requirement_id"], ["requirement.id"],
                                name="fk_control_requirement_requirement_id_requirement", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("control_id", "requirement_id", name="pk_control_requirement"),
    )
    op.create_table(
        "evidence_slot",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("control_id", sa.Uuid(), nullable=True),
        sa.Column("requirement_id", sa.Uuid(), nullable=True),
        sa.Column("name", sa.String(length=300), nullable=False),
        sa.Column("evidence_type", sa.String(length=40), nullable=False),
        sa.Column("required", sa.Boolean(), nullable=False),
        sa.Column("freshness_days", sa.Integer(), nullable=True),
        sa.Column("min_confidence", sa.Float(), nullable=True),
        sa.Column("rules", sa.JSON(), nullable=False),
        sa.Column("required_concepts", sa.JSON(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["control_id"], ["control.id"], name="fk_evidence_slot_control_id_control",
                                ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requirement_id"], ["requirement.id"],
                                name="fk_evidence_slot_requirement_id_requirement", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_evidence_slot"),
    )


def downgrade() -> None:
    op.drop_table("evidence_slot")
    op.drop_table("control_requirement")
    op.drop_index("ix_control_scope_sort", table_name="control")
    op.drop_table("control")
    op.drop_table("requirement")
    op.drop_table("framework")
```

Append to `backend/src/assayr/models.py`:
```python
from assayr.catalogue.models import (  # noqa: F401
    Control,
    ControlRequirement,
    EvidenceSlot,
    Framework,
    Requirement,
)
```

- [ ] **Step 5: Run to verify pass**

Run: `cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && cd backend && uv run pytest`
Expected: all pass, including `test_migrations_match_models_and_downgrade_cleanly` (proves migration 0003 matches the models).

- [ ] **Step 6: Commit**

```bash
cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && (cd backend && uv run ruff format . && uv run ruff check --fix .) && git add -A && git commit -m "feat(catalogue): ISO 27001:2022 models and idempotent seed of 93 controls" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: Catalogue API

**Files:**
- Create: `backend/src/assayr/catalogue/schemas.py`, `backend/src/assayr/catalogue/router.py`
- Modify: `backend/src/assayr/main.py`
- Test: `backend/tests/test_controls_api.py`

**Interfaces:**
- Consumes: catalogue models and `seeded` fixture (Task 8); `current_user`, `require`, `actor_for` (Task 6); `grant_for`, `Perm` (Task 5); `record` (Task 4).
- Produces (all under `/api/v1`, optional `scope_id` query param defaults to the default scope):
  - `GET /frameworks` → `[{id, code, name, version, requirement_count}]`
  - `GET /controls?theme&status&q&owner&limit&cursor` → `{items: ControlSummary[], next_cursor: int | null}`
  - `GET /controls/summary` → `{scope_id, total, by_status: {status: n}, by_theme: {theme: n}}`
  - `GET /controls/{code}` → `ControlDetail`
  - `PATCH /controls/{code}` body `{owner_id?, implementation_status?, implementation_text?}` → `ControlDetail`
  - `ControlSummary = {id, scope_id, code, title, theme, status, implementation_status, owner: {id, full_name} | null, evidence_required}`; `ControlDetail` adds `{description, review_frequency, default_owner_role, implementation_text, slots: [{id, name, evidence_type, required, freshness_days, rules}], requirements: [{ref, title}]}`.

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_controls_api.py`:
```python
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from assayr.audit.models import AuditLog
from assayr.catalogue.models import Control
from tests.conftest import create_user, sign_in


def manager(client, db):
    user = create_user(db, "sana@acme.com", full_name="Sana Malik")
    sign_in(client, "sana@acme.com")
    return user


def test_list_pages_through_all_93_controls(client, db, seeded):
    manager(client, db)
    first = client.get("/api/v1/controls").json()
    assert len(first["items"]) == 50 and first["next_cursor"] == 50
    assert first["items"][0]["code"] == "A.5.1"
    second = client.get("/api/v1/controls", params={"cursor": first["next_cursor"]}).json()
    assert len(second["items"]) == 43 and second["next_cursor"] is None


def test_filters_by_theme_and_search(client, db, seeded):
    manager(client, db)
    people = client.get("/api/v1/controls", params={"theme": "People", "limit": 200}).json()["items"]
    assert len(people) == 8
    backup = client.get("/api/v1/controls", params={"q": "BACKUP"}).json()["items"]
    assert [c["code"] for c in backup] == ["A.8.13"]


def test_search_treats_wildcards_literally(client, db, seeded):
    manager(client, db)
    assert client.get("/api/v1/controls", params={"q": "%"}).json()["items"] == []
    assert client.get("/api/v1/controls", params={"q": "_"}).json()["items"] == []


def test_owner_me_filter(client, db, seeded):
    user = manager(client, db)
    control = db.scalar(select(Control).where(Control.code == "A.5.15"))
    control.owner_id = user.id
    db.commit()
    items = client.get("/api/v1/controls", params={"owner": "me"}).json()["items"]
    assert [c["code"] for c in items] == ["A.5.15"]
    assert items[0]["owner"] == {"id": str(user.id), "full_name": "Sana Malik"}


def test_summary_counts_by_theme_and_status(client, db, seeded):
    manager(client, db)
    summary = client.get("/api/v1/controls/summary").json()
    assert summary["total"] == 93
    assert summary["by_theme"] == {"Organizational": 37, "People": 8, "Physical": 14, "Technological": 34}
    assert summary["by_status"] == {"not_started": 93}


def test_detail_includes_slots_and_requirements(client, db, seeded):
    manager(client, db)
    detail = client.get("/api/v1/controls/A.8.13").json()
    assert detail["title"] == "Information backup"
    assert len(detail["slots"]) == 3
    assert detail["requirements"] == [{"ref": "A.8.13", "title": "Information backup"}]
    assert client.get("/api/v1/controls/A.9.99").status_code == 404


def test_manager_updates_implementation_and_it_is_audited(client, db, seeded):
    manager(client, db)
    response = client.patch("/api/v1/controls/A.8.13", json={
        "implementation_status": "partial", "implementation_text": "Nightly Veeam jobs; restore tests quarterly."})
    assert response.status_code == 200
    assert response.json()["implementation_status"] == "partial"
    entry = db.scalar(select(AuditLog).where(AuditLog.action == "control.update"))
    assert entry.entity_id == "A.8.13"
    assert entry.diff["implementation_status"] == ["not_started", "partial"]


def test_no_op_update_writes_no_audit_entry(client, db, seeded):
    manager(client, db)
    client.patch("/api/v1/controls/A.8.13", json={"implementation_status": "not_started"})
    assert db.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.action == "control.update")) == 0


def test_control_owner_can_edit_only_their_own_controls(app, client, db, seeded):
    owner = create_user(db, "bilal@acme.com", roles=(("control_owner", None),), full_name="Bilal Khan")
    own = db.scalar(select(Control).where(Control.code == "A.8.13"))
    own.owner_id = owner.id
    db.commit()
    sign_in(client, "bilal@acme.com")
    assert client.patch("/api/v1/controls/A.8.13", json={"implementation_text": "Mine."}).status_code == 200
    assert client.patch("/api/v1/controls/A.5.1", json={"implementation_text": "Not mine."}).status_code == 403
    response = client.patch("/api/v1/controls/A.8.13", json={"owner_id": None})
    assert response.status_code == 403
    assert response.json() == {"detail": "Only an ISMS manager can change the owner."}


def test_owner_must_be_an_active_user(client, db, seeded):
    manager(client, db)
    gone = create_user(db, "gone@acme.com", active=False)
    for owner_id in (str(uuid.uuid4()), str(gone.id)):
        response = client.patch("/api/v1/controls/A.8.13", json={"owner_id": owner_id})
        assert response.status_code == 422
        assert response.json() == {"detail": "Owner must be an active user."}


def test_scoped_user_cannot_read_another_scope(app, client, db, seeded):
    other_scope = uuid.uuid4()
    from assayr.identity.models import Scope

    db.add(Scope(id=other_scope, organization_id=seeded.organization_id, name="Subsidiary"))
    db.commit()
    create_user(db, "aud@other.com", roles=(("viewer", other_scope),))
    sign_in(client, "aud@other.com")
    assert client.get("/api/v1/controls").status_code == 403
    assert client.get("/api/v1/controls", params={"scope_id": str(other_scope)}).json()["items"] == []


def test_patch_without_csrf_is_rejected(client, db, seeded):
    manager(client, db)
    client.headers.pop("X-CSRF-Token")
    assert client.patch("/api/v1/controls/A.8.13", json={"implementation_text": "x"}).status_code == 403


def test_frameworks_lists_iso27001(client, db, seeded):
    manager(client, db)
    frameworks = client.get("/api/v1/frameworks").json()
    assert frameworks[0]["code"] == "ISO27001:2022"
    assert frameworks[0]["requirement_count"] == 41 + 4 + 93
```

- [ ] **Step 2: Run to verify failure**

Run: `cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && cd backend && uv run pytest tests/test_controls_api.py`
Expected: FAIL (404s).

- [ ] **Step 3: Implement**

`backend/src/assayr/catalogue/schemas.py`:
```python
import uuid
from typing import Literal

from pydantic import BaseModel, Field

from assayr.catalogue.models import Control

ImplementationStatus = Literal["not_started", "planned", "partial", "implemented"]


class OwnerOut(BaseModel):
    id: uuid.UUID
    full_name: str


class ControlSummaryOut(BaseModel):
    id: uuid.UUID
    scope_id: uuid.UUID
    code: str
    title: str
    theme: str | None
    status: str
    implementation_status: str
    owner: OwnerOut | None
    evidence_required: int


class ControlPage(BaseModel):
    items: list[ControlSummaryOut]
    next_cursor: int | None


class SlotOut(BaseModel):
    id: uuid.UUID
    name: str
    evidence_type: str
    required: bool
    freshness_days: int | None
    rules: list[str]


class RequirementRefOut(BaseModel):
    ref: str
    title: str


class ControlDetailOut(ControlSummaryOut):
    description: str | None
    review_frequency: str | None
    default_owner_role: str | None
    implementation_text: str | None
    slots: list[SlotOut]
    requirements: list[RequirementRefOut]


class ControlStatsOut(BaseModel):
    scope_id: uuid.UUID
    total: int
    by_status: dict[str, int]
    by_theme: dict[str, int]


class FrameworkOut(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    version: str
    requirement_count: int


class ControlUpdateIn(BaseModel):
    owner_id: uuid.UUID | None = None
    implementation_status: ImplementationStatus | None = None
    implementation_text: str | None = Field(default=None, max_length=20000)


def summary_out(control: Control) -> ControlSummaryOut:
    return ControlSummaryOut(
        id=control.id, scope_id=control.scope_id, code=control.code, title=control.title, theme=control.theme,
        status=control.status, implementation_status=control.implementation_status,
        owner=OwnerOut(id=control.owner.id, full_name=control.owner.full_name) if control.owner else None,
        evidence_required=sum(1 for s in control.slots if s.required),
    )


def detail_out(control: Control) -> ControlDetailOut:
    return ControlDetailOut(
        **summary_out(control).model_dump(),
        description=control.description,
        review_frequency=control.review_frequency,
        default_owner_role=control.default_owner_role,
        implementation_text=control.implementation_text,
        slots=[SlotOut(id=s.id, name=s.name, evidence_type=s.evidence_type, required=s.required,
                       freshness_days=s.freshness_days, rules=s.rules) for s in control.slots],
        requirements=[RequirementRefOut(ref=r.ref, title=r.title) for r in control.requirements],
    )
```

`backend/src/assayr/catalogue/router.py`:
```python
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from assayr.audit.service import record
from assayr.catalogue.models import Control, Framework, Requirement
from assayr.catalogue.schemas import (
    ControlDetailOut,
    ControlPage,
    ControlStatsOut,
    ControlUpdateIn,
    FrameworkOut,
    detail_out,
    summary_out,
)
from assayr.db import get_session
from assayr.identity.deps import actor_for, current_user, require
from assayr.identity.models import Scope, User
from assayr.identity.rbac import Grant, Perm, grant_for

router = APIRouter(tags=["catalogue"])
FORBIDDEN = "You don't have permission to do this."


def resolve_scope(db: Session, scope_id: uuid.UUID | None, grant: Grant) -> Scope:
    if scope_id is None:
        scope = db.scalar(select(Scope).where(Scope.is_default.is_(True)))
        if scope is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "No ISMS scope exists yet. Run `assayr seed`.")
    else:
        scope = db.get(Scope, scope_id)
        if scope is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Scope not found.")
    if not grant.allows(scope.id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, FORBIDDEN)
    return scope


def _like(term: str) -> str:
    escaped = term.lower().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _get_control(db: Session, scope: Scope, code: str) -> Control:
    control = db.scalar(select(Control).where(Control.scope_id == scope.id, Control.code == code))
    if control is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Control not found.")
    return control


@router.get("/frameworks", response_model=list[FrameworkOut])
def list_frameworks(_grant=Depends(require(Perm.CONTROLS_READ)), db: Session = Depends(get_session)):
    counts = dict(db.execute(select(Requirement.framework_id, func.count()).group_by(Requirement.framework_id)).all())
    return [
        FrameworkOut(id=f.id, code=f.code, name=f.name, version=f.version, requirement_count=counts.get(f.id, 0))
        for f in db.scalars(select(Framework).order_by(Framework.code))
    ]


@router.get("/controls", response_model=ControlPage)
def list_controls(
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.CONTROLS_READ)),
    db: Session = Depends(get_session),
    scope_id: uuid.UUID | None = None,
    theme: str | None = Query(None, max_length=40),
    status_: str | None = Query(None, alias="status", max_length=30),
    q: str | None = Query(None, max_length=100),
    owner: str | None = Query(None, max_length=40),
    limit: int = Query(50, ge=1, le=200),
    cursor: int | None = Query(None, ge=0),
) -> ControlPage:
    scope = resolve_scope(db, scope_id, grant)
    stmt = select(Control).where(Control.scope_id == scope.id)
    if theme:
        stmt = stmt.where(Control.theme == theme)
    if status_:
        stmt = stmt.where(Control.status == status_)
    if q and q.strip():
        like = _like(q.strip())
        stmt = stmt.where(or_(func.lower(Control.title).like(like, escape="\\"),
                              func.lower(Control.code).like(like, escape="\\")))
    if owner == "me":
        stmt = stmt.where(Control.owner_id == user.id)
    elif owner:
        try:
            stmt = stmt.where(Control.owner_id == uuid.UUID(owner))
        except ValueError as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "owner must be 'me' or a user id.") from exc
    if cursor is not None:
        stmt = stmt.where(Control.sort_order > cursor)
    rows = list(db.scalars(stmt.order_by(Control.sort_order).limit(limit + 1)).unique())
    items = rows[:limit]
    return ControlPage(items=[summary_out(c) for c in items],
                       next_cursor=items[-1].sort_order if len(rows) > limit else None)


@router.get("/controls/summary", response_model=ControlStatsOut)
def controls_summary(
    grant: Grant = Depends(require(Perm.CONTROLS_READ)),
    db: Session = Depends(get_session),
    scope_id: uuid.UUID | None = None,
) -> ControlStatsOut:
    scope = resolve_scope(db, scope_id, grant)
    base = select(func.count()).select_from(Control).where(Control.scope_id == scope.id)
    by_status = dict(db.execute(
        select(Control.status, func.count()).where(Control.scope_id == scope.id).group_by(Control.status)).all())
    by_theme = dict(db.execute(
        select(Control.theme, func.count()).where(Control.scope_id == scope.id).group_by(Control.theme)).all())
    return ControlStatsOut(scope_id=scope.id, total=db.scalar(base), by_status=by_status,
                           by_theme={k or "Other": v for k, v in by_theme.items()})


@router.get("/controls/{code}", response_model=ControlDetailOut)
def get_control(
    code: str,
    grant: Grant = Depends(require(Perm.CONTROLS_READ)),
    db: Session = Depends(get_session),
    scope_id: uuid.UUID | None = None,
) -> ControlDetailOut:
    return detail_out(_get_control(db, resolve_scope(db, scope_id, grant), code))


@router.patch("/controls/{code}", response_model=ControlDetailOut)
def update_control(
    code: str,
    body: ControlUpdateIn,
    request: Request,
    user: User = Depends(current_user),
    read_grant: Grant = Depends(require(Perm.CONTROLS_READ)),
    db: Session = Depends(get_session),
    scope_id: uuid.UUID | None = None,
) -> ControlDetailOut:
    scope = resolve_scope(db, scope_id, read_grant)
    control = _get_control(db, scope, code)
    pairs = [(a.role, a.scope_id) for a in user.role_assignments]
    can_write_all = grant_for(pairs, Perm.CONTROLS_WRITE).allows(scope.id)
    can_write_own = grant_for(pairs, Perm.CONTROLS_WRITE_OWN).allows(scope.id) and control.owner_id == user.id
    if not (can_write_all or can_write_own):
        raise HTTPException(status.HTTP_403_FORBIDDEN, FORBIDDEN)
    fields = body.model_fields_set
    if "owner_id" in fields and not can_write_all:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only an ISMS manager can change the owner.")

    diff: dict[str, list] = {}
    if "owner_id" in fields and body.owner_id != control.owner_id:
        if body.owner_id is not None:
            new_owner = db.get(User, body.owner_id)
            if new_owner is None or not new_owner.is_active:
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Owner must be an active user.")
        diff["owner_id"] = [str(control.owner_id) if control.owner_id else None,
                            str(body.owner_id) if body.owner_id else None]
        control.owner_id = body.owner_id
    if body.implementation_status is not None and body.implementation_status != control.implementation_status:
        diff["implementation_status"] = [control.implementation_status, body.implementation_status]
        control.implementation_status = body.implementation_status
    if "implementation_text" in fields and body.implementation_text != control.implementation_text:
        diff["implementation_text"] = [control.implementation_text, body.implementation_text]
        control.implementation_text = body.implementation_text
    if diff:
        record(db, actor_for(request, user), "control.update", "control", control.code, diff=diff)
        db.commit()
        db.refresh(control)
    return detail_out(control)
```

In `backend/src/assayr/main.py` add:
```python
from assayr.catalogue.router import router as catalogue_router
```
```python
    app.include_router(catalogue_router, prefix="/api/v1")
```

- [ ] **Step 4: Run to verify pass**

Run: `cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && cd backend && uv run pytest`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && (cd backend && uv run ruff format . && uv run ruff check --fix .) && git add -A && git commit -m "feat(catalogue): frameworks and controls API with scoped RBAC" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: Administration CLI

**Files:**
- Create: `backend/src/assayr/cli.py`, `backend/.env.example`
- Test: `backend/tests/test_cli.py`

**Interfaces:**
- Consumes: `upgrade` (Task 2), `ensure_default_scope`, `seed_iso27001` (Task 8), `hash_password`, `normalize_email` (Task 3), `record`, `SYSTEM`, `verify_chain` (Task 4), `get_settings` (Task 1).
- Produces: `assayr migrate`, `assayr seed`, `assayr create-admin --email E [--full-name N] [--password P | env ASSAYR_ADMIN_PASSWORD | prompt]`, `assayr audit-verify` (exit 2 when the chain is broken).

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_cli.py`:
```python
import os

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from typer.testing import CliRunner

from assayr.cli import app
from assayr.config import get_settings
from assayr.db import Base
from assayr.identity.models import User

runner = CliRunner()


@pytest.fixture
def cli_db(tmp_path, monkeypatch):
    url = os.environ.get("ASSAYR_TEST_DATABASE_URL") or f"sqlite+pysqlite:///{(tmp_path / 'cli.db').as_posix()}"
    engine = create_engine(url)
    Base.metadata.drop_all(engine)
    with engine.begin() as conn:
        conn.exec_driver_sql("DROP TABLE IF EXISTS alembic_version")
    monkeypatch.setenv("ASSAYR_DATABASE_URL", url)
    monkeypatch.setenv("ASSAYR_ORG_NAME", "Acme Financial Services")
    get_settings.cache_clear()
    yield engine
    get_settings.cache_clear()
    Base.metadata.drop_all(engine)
    with engine.begin() as conn:
        conn.exec_driver_sql("DROP TABLE IF EXISTS alembic_version")
    engine.dispose()


def run(*args, env=None):
    return runner.invoke(app, list(args), env=env)


def test_full_bootstrap(cli_db):
    assert run("migrate").exit_code == 0
    first = run("seed")
    assert first.exit_code == 0 and "93 controls created" in first.output
    assert "0 controls created" in run("seed").output
    created = run("create-admin", "--email", "Admin@Acme.com", "--password", "a-very-long-password")
    assert created.exit_code == 0, created.output
    with Session(cli_db) as session:
        admin = session.scalar(select(User))
        assert admin.email == "admin@acme.com"
        assert sorted(a.role for a in admin.role_assignments) == ["isms_manager", "platform_admin"]
    verified = run("audit-verify")
    assert verified.exit_code == 0 and "Audit chain intact" in verified.output


def test_create_admin_reads_password_from_environment(cli_db):
    run("migrate")
    result = run("create-admin", "--email", "env@acme.com", env={"ASSAYR_ADMIN_PASSWORD": "from-the-environment"})
    assert result.exit_code == 0, result.output


def test_create_admin_refuses_duplicates_and_weak_passwords(cli_db):
    run("migrate")
    run("create-admin", "--email", "admin@acme.com", "--password", "a-very-long-password")
    duplicate = run("create-admin", "--email", "ADMIN@acme.com", "--password", "a-very-long-password")
    assert duplicate.exit_code == 1 and "already exists" in duplicate.output
    weak = run("create-admin", "--email", "new@acme.com", "--password", "short")
    assert weak.exit_code == 1 and "Use at least 12 characters." in weak.output
```

- [ ] **Step 2: Run to verify failure**

Run: `cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && cd backend && uv run pytest tests/test_cli.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'assayr.cli'`.

- [ ] **Step 3: Implement**

`backend/src/assayr/cli.py`:
```python
"""`assayr` administration commands."""

import typer
from sqlalchemy import select

from assayr.audit.service import SYSTEM, record, verify_chain
from assayr.catalogue.seed import ensure_default_scope, seed_iso27001
from assayr.config import get_settings
from assayr.db import Database
from assayr.identity.models import RoleAssignment, User
from assayr.identity.rbac import Role
from assayr.identity.security import WeakPasswordError, hash_password, normalize_email
from assayr.migrate import upgrade

app = typer.Typer(help="Assayr administration commands.", no_args_is_help=True)


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
        session.commit()
    typer.echo(f"Seed complete: {result.requirements_created} requirements and "
               f"{result.controls_created} controls created.")


@app.command("create-admin")
def create_admin(
    email: str = typer.Option(..., help="Sign-in email for the administrator."),
    full_name: str = typer.Option("Administrator", help="Display name."),
    password: str = typer.Option(..., prompt=True, hide_input=True, confirmation_prompt=True,
                                 envvar="ASSAYR_ADMIN_PASSWORD", help="At least 12 characters."),
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
            email=normalized, full_name=full_name, password_hash=password_hash,
            role_assignments=[RoleAssignment(role=Role.PLATFORM_ADMIN.value),
                              RoleAssignment(role=Role.ISMS_MANAGER.value)],
        )
        session.add(user)
        session.flush()
        record(session, SYSTEM, "user.create", "user", str(user.id),
               diff={"email": [None, normalized], "roles": [None, ["isms_manager", "platform_admin"]]})
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
    typer.echo(f"Audit chain broken at entry {result.first_bad_seq} "
               f"({result.checked} entries verified before it).", err=True)
    raise typer.Exit(2)
```

`backend/.env.example`:
```dotenv
# Copy to backend/.env for local development.
ASSAYR_DATABASE_URL=sqlite+pysqlite:///./assayr-dev.db
ASSAYR_SECURE_COOKIES=false
ASSAYR_ORG_NAME=Acme Financial Services
```

Note: `CliRunner` mixes stderr into `output` by default in Typer, which is what the tests read.

- [ ] **Step 4: Run to verify pass**

Run: `cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && cd backend && uv run pytest`
Expected: all pass.

- [ ] **Step 5: Manually exercise the local API**

```bash
cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && cd backend && cp .env.example .env && uv run assayr migrate && uv run assayr seed && ASSAYR_ADMIN_PASSWORD=local-dev-password uv run assayr create-admin --email admin@acme.com --full-name "Sana Malik"
```
Expected output ends with `Administrator admin@acme.com created.` Then start the server in the background with `uv run uvicorn assayr.main:create_app --factory --port 8000` and check `curl -s localhost:8000/api/v1/readyz` → `{"status":"ready","database":"ok"}`. Stop the server afterwards.

- [ ] **Step 6: Commit**

```bash
cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && (cd backend && uv run ruff format . && uv run ruff check --fix .) && git add -A && git commit -m "feat: assayr CLI for migrate, seed, create-admin and audit-verify" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 11: Frontend scaffold, Strata tokens and base components

**Files:**
- Create: `frontend/package.json` (via npm), `frontend/tsconfig.json`, `frontend/vite.config.ts`, `frontend/index.html`, `frontend/public/favicon.svg`, `frontend/src/main.tsx`, `frontend/src/styles/tokens.css`, `frontend/src/styles/global.css`, `frontend/src/components/icons.tsx`, `frontend/src/components/Button.tsx`, `frontend/src/components/StatusPill.tsx`, `frontend/src/components/ControlId.tsx`, `frontend/src/pages/Styleguide.tsx`, `frontend/src/test/setup.ts`
- Test: `frontend/src/components/StatusPill.test.tsx`, `frontend/src/components/Button.test.tsx`

**Interfaces:**
- Produces: `Icon({ name, size?, className? })` with names `compliant | at_risk | non_compliant | in_review | in_progress | not_started | excluded | home | controls | evidence | soa | policy | risk | audit | theme | logout`; `Button(props: ButtonHTMLAttributes & { variant?: "primary" | "secondary" | "ghost"; size?: "sm" | "md" })`; `StatusPill({ status: string })`, `STATUS_LABEL: Record<ControlStatus, string>`, type `ControlStatus`; `ControlId({ code })`; `Styleguide` page component (default export not used — named export `Styleguide`).

- [ ] **Step 1: Create the project and install dependencies**

```bash
cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && mkdir -p frontend && cd frontend && npm init -y >/dev/null && npm pkg set name=assayr-web private=true version=0.1.0 type=module scripts.dev=vite "scripts.build=tsc --noEmit && vite build" "scripts.typecheck=tsc --noEmit" "scripts.test=vitest run" "scripts.preview=vite preview" && npm pkg delete main description keywords author license && npm install react@19 react-dom@19 @tanstack/react-query@5 @tanstack/react-router@1 @fontsource/ibm-plex-sans@5 @fontsource/ibm-plex-mono@5 @fontsource/schibsted-grotesk@5 && npm install -D typescript@5.7 vite@6 @vitejs/plugin-react@4 vitest@3 jsdom@26 tailwindcss@4 @tailwindcss/vite@4 @testing-library/react@16 @testing-library/dom@10 @testing-library/jest-dom@6 @testing-library/user-event@14 @types/react@19 @types/react-dom@19
```
Expected: `package-lock.json` created, no errors. If `@fontsource/schibsted-grotesk` is not found, install `@fontsource-variable/schibsted-grotesk` instead and adjust the import in `main.tsx` to `@fontsource-variable/schibsted-grotesk`.

`frontend/tsconfig.json`:
```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["ES2023", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "moduleResolution": "bundler",
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "skipLibCheck": true,
    "isolatedModules": true,
    "resolveJsonModule": true,
    "noEmit": true,
    "types": ["vitest/globals", "@testing-library/jest-dom"]
  },
  "include": ["src", "vite.config.ts"]
}
```

`frontend/vite.config.ts`:
```ts
import tailwindcss from "@tailwindcss/vite"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vitest/config"

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { proxy: { "/api": "http://127.0.0.1:8000" } },
  test: { environment: "jsdom", globals: true, setupFiles: ["./src/test/setup.ts"], css: false },
})
```

`frontend/index.html`:
```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <link rel="icon" href="/favicon.svg" type="image/svg+xml" />
    <title>Assayr</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

```bash
mkdir -p "E:/Work/GRC Tool/assayr/frontend/public" && cp "E:/Work/GRC Tool/Assayr-Vault/02-Brand/assets/assayr-mark.svg" "E:/Work/GRC Tool/assayr/frontend/public/favicon.svg"
```

`frontend/src/test/setup.ts`:
```ts
import "@testing-library/jest-dom/vitest"
import { cleanup } from "@testing-library/react"
import { afterEach, vi } from "vitest"

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  document.cookie = "assayr_csrf=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/"
  delete document.documentElement.dataset.theme
})
```

- [ ] **Step 2: Write the failing tests**

`frontend/src/components/StatusPill.test.tsx`:
```tsx
import { render, screen } from "@testing-library/react"
import { StatusPill } from "./StatusPill"

test("shows the label with a decorative icon", () => {
  render(<StatusPill status="at_risk" />)
  const pill = screen.getByText("At risk")
  expect(pill.parentElement?.querySelector("svg")).toHaveAttribute("aria-hidden", "true")
})

test("every known status has a human label", () => {
  const { container } = render(
    <>
      {["not_started", "in_progress", "in_review", "at_risk", "non_compliant", "compliant", "excluded"].map((s) => (
        <StatusPill key={s} status={s} />
      ))}
    </>,
  )
  expect(container.textContent).toBe(
    "Not startedIn progressIn reviewAt riskNon-compliantCompliantExcluded",
  )
})

test("unknown statuses from a newer server still render readably", () => {
  render(<StatusPill status="awaiting_magic" />)
  expect(screen.getByText("Awaiting magic")).toBeInTheDocument()
})
```

`frontend/src/components/Button.test.tsx`:
```tsx
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { Button } from "./Button"

test("primary button calls its handler", async () => {
  const onClick = vi.fn()
  render(<Button onClick={onClick}>Upload evidence</Button>)
  await userEvent.click(screen.getByRole("button", { name: "Upload evidence" }))
  expect(onClick).toHaveBeenCalledOnce()
  expect(screen.getByRole("button")).toHaveClass("bg-primary")
})

test("disabled button ignores clicks", async () => {
  const onClick = vi.fn()
  render(<Button disabled onClick={onClick}>Save</Button>)
  await userEvent.click(screen.getByRole("button", { name: "Save" }))
  expect(onClick).not.toHaveBeenCalled()
})
```

- [ ] **Step 3: Run to verify failure**

Run: `cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && cd frontend && npm test`
Expected: FAIL — `Failed to resolve import "./StatusPill"`.

- [ ] **Step 4: Implement tokens, styles and components**

`frontend/src/styles/tokens.css`:
```css
/* Strata design tokens — see vault 07-Design/Design System.md */
:root {
  --canvas: #f5f6fa; --surface: #ffffff; --subtle: #eef0f6; --line: #e1e5ee; --line-2: #c9d0dd;
  --text: #0e1424; --text-2: #4a5368; --text-3: #687188;
  --primary: #2f4bff; --primary-hover: #2238d9; --primary-soft: #eceffe; --on-primary: #ffffff;
  --ink: #0a0f1f; --brass: #cfae4e;
  --ok: #15803d; --ok-soft: #e6f5eb; --warn: #b45309; --warn-soft: #fcf1df; --bad: #c62828; --bad-soft: #fcebeb;
  --review: #6d28d9; --review-soft: #f0eafe; --idle: #5e6a80; --idle-soft: #eef0f5; --na: #8c95a8;
  --f-display: "Schibsted Grotesk", "IBM Plex Sans", system-ui, sans-serif;
  --f-body: "IBM Plex Sans", system-ui, -apple-system, "Segoe UI", sans-serif;
  --f-mono: "IBM Plex Mono", ui-monospace, "Cascadia Mono", Consolas, monospace;
  color-scheme: light;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --canvas: #0a0f1f; --surface: #11172a; --subtle: #182037; --line: #252f4d; --line-2: #37426c;
    --text: #edf0f7; --text-2: #aeb6ca; --text-3: #8690a8;
    --primary: #6e83ff; --primary-hover: #8a9bff; --primary-soft: #1a2350; --on-primary: #0a0f1f;
    --ok: #4cc17e; --ok-soft: #0f2e1e; --warn: #e6a645; --warn-soft: #33260f; --bad: #f26b66; --bad-soft: #3a1517;
    --review: #b39bff; --review-soft: #261a45; --idle: #95a0b8; --idle-soft: #1b2340; --na: #6e7894;
    color-scheme: dark;
  }
}
:root[data-theme="dark"] {
  --canvas: #0a0f1f; --surface: #11172a; --subtle: #182037; --line: #252f4d; --line-2: #37426c;
  --text: #edf0f7; --text-2: #aeb6ca; --text-3: #8690a8;
  --primary: #6e83ff; --primary-hover: #8a9bff; --primary-soft: #1a2350; --on-primary: #0a0f1f;
  --ok: #4cc17e; --ok-soft: #0f2e1e; --warn: #e6a645; --warn-soft: #33260f; --bad: #f26b66; --bad-soft: #3a1517;
  --review: #b39bff; --review-soft: #261a45; --idle: #95a0b8; --idle-soft: #1b2340; --na: #6e7894;
  color-scheme: dark;
}
```

`frontend/src/styles/global.css`:
```css
@import "tailwindcss";
@import "./tokens.css";

@theme inline {
  --color-canvas: var(--canvas);
  --color-surface: var(--surface);
  --color-subtle: var(--subtle);
  --color-line: var(--line);
  --color-line-2: var(--line-2);
  --color-fg: var(--text);
  --color-fg-2: var(--text-2);
  --color-fg-3: var(--text-3);
  --color-primary: var(--primary);
  --color-primary-hover: var(--primary-hover);
  --color-primary-soft: var(--primary-soft);
  --color-on-primary: var(--on-primary);
  --color-ink: var(--ink);
  --color-brass: var(--brass);
  --color-ok: var(--ok);
  --color-ok-soft: var(--ok-soft);
  --color-warn: var(--warn);
  --color-warn-soft: var(--warn-soft);
  --color-bad: var(--bad);
  --color-bad-soft: var(--bad-soft);
  --color-review: var(--review);
  --color-review-soft: var(--review-soft);
  --color-idle: var(--idle);
  --color-idle-soft: var(--idle-soft);
  --color-na: var(--na);
  --font-display: var(--f-display);
  --font-sans: var(--f-body);
  --font-mono: var(--f-mono);
}

html, body, #root { height: 100%; }
body {
  background: var(--canvas);
  color: var(--text);
  font-family: var(--f-body);
  font-size: 14px;
  line-height: 1.55;
  -webkit-font-smoothing: antialiased;
}
h1, h2, h3 { text-wrap: balance; }
:focus-visible { outline: 2px solid var(--primary); outline-offset: 2px; border-radius: 4px; }
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { animation-duration: 0.01ms !important; transition-duration: 0.01ms !important; }
}
```

`frontend/src/components/icons.tsx`:
```tsx
const PATHS: Record<string, string> = {
  compliant:
    "M12 3l2.2 1.6 2.7-.2.9 2.6 2.3 1.5-.8 2.6.8 2.6-2.3 1.5-.9 2.6-2.7-.2L12 21l-2.2-1.6-2.7.2-.9-2.6-2.3-1.5.8-2.6-.8-2.6 2.3-1.5.9-2.6 2.7.2zM8.5 12l2.3 2.3 4.7-4.7",
  at_risk: "M12 3.5a8.5 8.5 0 1 0 0 17 8.5 8.5 0 0 0 0-17zM12 7.5V12l3 2",
  non_compliant: "M8 2.8h8L21.2 8v8L16 21.2H8L2.8 16V8zM9 9l6 6m0-6-6 6",
  in_review: "M2.5 12s3.5-6.5 9.5-6.5S21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12zM12 9.4a2.6 2.6 0 1 0 0 5.2 2.6 2.6 0 0 0 0-5.2z",
  in_progress: "M12 3.5a8.5 8.5 0 1 0 0 17 8.5 8.5 0 0 0 0-17zM12 3.5v17",
  not_started: "M12 3.5a8.5 8.5 0 1 0 0 17 8.5 8.5 0 0 0 0-17z",
  excluded: "M12 3.5a8.5 8.5 0 1 0 0 17 8.5 8.5 0 0 0 0-17zM8 12h8",
  home: "M3.5 11 12 4l8.5 7v8.5a1 1 0 0 1-1 1H15v-6H9v6H4.5a1 1 0 0 1-1-1z",
  controls: "M12 3.5a8.5 8.5 0 1 0 0 17 8.5 8.5 0 0 0 0-17zM12 7.5a4.5 4.5 0 1 0 0 9 4.5 4.5 0 0 0 0-9z",
  evidence: "M7 3.5h7l4 4V20.5H6.5V3.5zM14 3.5V8h4M9.5 13l2 2 3.5-3.5",
  soa: "M4 3.5h16v17H4zM8 8h8M8 12h8M8 16h5",
  policy: "M5 4.5h10l4 4v12H4v-16zM8 12h8M8 16h6",
  risk: "M3.5 3.5h7v7h-7zM13.5 3.5h7v7h-7zM3.5 13.5h7v7h-7zM13.5 13.5h7v7h-7z",
  audit: "M5 21V4h11l-2 4 2 4H5",
  theme: "M12 3.5a8.5 8.5 0 1 0 0 17zM12 3.5a8.5 8.5 0 0 1 0 17",
  logout: "M15 4h4v16h-4M10 8l-4 4 4 4M6 12h10",
}

export type IconName = keyof typeof PATHS

export function Icon({ name, size = 16, className }: { name: string; size?: number; className?: string }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      className={className}
    >
      <path d={PATHS[name] ?? PATHS.not_started} />
    </svg>
  )
}
```

`frontend/src/components/StatusPill.tsx`:
```tsx
import { Icon } from "./icons"

export type ControlStatus =
  | "not_started" | "in_progress" | "in_review" | "at_risk" | "non_compliant" | "compliant" | "excluded"

export const STATUS_LABEL: Record<ControlStatus, string> = {
  not_started: "Not started",
  in_progress: "In progress",
  in_review: "In review",
  at_risk: "At risk",
  non_compliant: "Non-compliant",
  compliant: "Compliant",
  excluded: "Excluded",
}

const STYLE: Record<ControlStatus, string> = {
  compliant: "bg-ok-soft text-ok border-ok/25",
  at_risk: "bg-warn-soft text-warn border-warn/25",
  non_compliant: "bg-bad-soft text-bad border-bad/25",
  in_review: "bg-review-soft text-review border-review/25",
  in_progress: "bg-primary-soft text-primary border-primary/25",
  not_started: "bg-idle-soft text-idle border-idle/25",
  excluded: "bg-transparent text-na border-line-2 border-dashed",
}

function humanize(value: string): string {
  const text = value.replace(/[_-]+/g, " ").trim()
  return text.charAt(0).toUpperCase() + text.slice(1)
}

export function StatusPill({ status }: { status: string }) {
  const known = status in STATUS_LABEL ? (status as ControlStatus) : null
  const label = known ? STATUS_LABEL[known] : humanize(status)
  const style = known ? STYLE[known] : STYLE.not_started
  return (
    <span
      className={`inline-flex h-6 items-center gap-1.5 whitespace-nowrap rounded-full border pl-[7px] pr-[9px] text-xs font-medium ${style}`}
    >
      <Icon name={known ?? "not_started"} size={14} />
      <span>{label}</span>
    </span>
  )
}
```

`frontend/src/components/Button.tsx`:
```tsx
import type { ButtonHTMLAttributes } from "react"

type Variant = "primary" | "secondary" | "ghost"
type Size = "sm" | "md"

const VARIANT: Record<Variant, string> = {
  primary: "bg-primary text-on-primary border-primary hover:bg-primary-hover hover:border-primary-hover",
  secondary: "bg-surface text-fg border-line-2 hover:border-fg-3",
  ghost: "bg-transparent text-fg-2 border-transparent hover:bg-subtle",
}
const SIZE: Record<Size, string> = { sm: "px-2.5 py-1 text-[13px]", md: "px-3.5 py-2 text-sm" }

export function Button({
  variant = "primary",
  size = "md",
  className = "",
  type = "button",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; size?: Size }) {
  return (
    <button
      type={type}
      className={`inline-flex items-center gap-2 whitespace-nowrap rounded-lg border font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${VARIANT[variant]} ${SIZE[size]} ${className}`}
      {...props}
    />
  )
}
```

`frontend/src/components/ControlId.tsx`:
```tsx
export function ControlId({ code }: { code: string }) {
  return <span className="whitespace-nowrap font-mono text-[12.5px] font-medium text-fg-2">{code}</span>
}
```

`frontend/src/pages/Styleguide.tsx`:
```tsx
import { Button } from "../components/Button"
import { ControlId } from "../components/ControlId"
import { StatusPill, STATUS_LABEL } from "../components/StatusPill"

const SWATCHES = [
  ["Attest cobalt", "var(--primary)"], ["Ink", "var(--ink)"], ["Seal brass", "var(--brass)"],
  ["Compliant", "var(--ok)"], ["At risk", "var(--warn)"], ["Non-compliant", "var(--bad)"], ["In review", "var(--review)"],
] as const

export function Styleguide() {
  return (
    <div className="mx-auto grid max-w-4xl gap-10 py-2">
      <header>
        <p className="text-[11px] font-medium uppercase tracking-[0.08em] text-fg-3">Strata design system</p>
        <h1 className="font-display text-[26px] font-extrabold tracking-tight">Styleguide</h1>
      </header>
      <section className="grid gap-3">
        <h2 className="text-[15px] font-semibold">Colour</h2>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {SWATCHES.map(([name, value]) => (
            <div key={name} className="overflow-hidden rounded-xl border border-line bg-surface">
              <div className="h-16" style={{ background: value }} />
              <div className="px-3 py-2 text-[13px]">{name}</div>
            </div>
          ))}
        </div>
      </section>
      <section className="grid gap-3">
        <h2 className="text-[15px] font-semibold">Type</h2>
        <p className="font-display text-5xl font-extrabold tracking-tight">Readiness 87%</p>
        <p className="max-w-[65ch] text-fg-2">
          This access review is dated 3 Mar 2026; reviews must fall within 90 days. Upload the latest review to keep{" "}
          <ControlId code="A.5.18" /> compliant.
        </p>
      </section>
      <section className="grid gap-3">
        <h2 className="text-[15px] font-semibold">Status</h2>
        <div className="flex flex-wrap gap-2">
          {Object.keys(STATUS_LABEL).map((s) => <StatusPill key={s} status={s} />)}
        </div>
      </section>
      <section className="grid gap-3">
        <h2 className="text-[15px] font-semibold">Buttons</h2>
        <div className="flex flex-wrap gap-2">
          <Button>Upload evidence</Button>
          <Button variant="secondary">Export</Button>
          <Button variant="ghost">Cancel</Button>
          <Button disabled>Saving…</Button>
        </div>
      </section>
    </div>
  )
}
```

`frontend/src/main.tsx` (temporary — replaced in Task 12):
```tsx
import "@fontsource/ibm-plex-sans/400.css"
import "@fontsource/ibm-plex-sans/500.css"
import "@fontsource/ibm-plex-sans/600.css"
import "@fontsource/ibm-plex-mono/400.css"
import "@fontsource/ibm-plex-mono/500.css"
import "@fontsource/schibsted-grotesk/600.css"
import "@fontsource/schibsted-grotesk/800.css"
import "./styles/global.css"
import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import { Styleguide } from "./pages/Styleguide"

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <main className="p-6"><Styleguide /></main>
  </StrictMode>,
)
```

- [ ] **Step 5: Run tests, typecheck and build**

Run: `cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && cd frontend && npm test && npm run build`
Expected: `5 passed`; build writes `dist/` with no type errors. Confirm no font requests leave the machine: `grep -r "fonts.googleapis" dist || echo "no external fonts"` prints `no external fonts`.

- [ ] **Step 6: Commit**

```bash
cd "E:/Work/GRC Tool/assayr" && git add -A && git commit -m "feat(web): Vite React scaffold with Strata tokens and base components" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 12: API client, sign-in flow and routing

**Files:**
- Create: `frontend/src/api/client.ts`, `frontend/src/api/types.ts`, `frontend/src/auth/session.ts`, `frontend/src/router.tsx`, `frontend/src/layouts/AppLayout.tsx`, `frontend/src/pages/Login.tsx`, `frontend/src/pages/Dashboard.tsx` (placeholder), `frontend/src/pages/Controls.tsx` (placeholder), `frontend/src/test/render.tsx`
- Modify: `frontend/src/main.tsx`
- Test: `frontend/src/api/client.test.ts`, `frontend/src/auth/session.test.ts`, `frontend/src/pages/Login.test.tsx`

**Interfaces:**
- Consumes: `Button`, `Styleguide` (Task 11); backend `/auth/login`, `/auth/logout`, `/auth/me` (Task 6).
- Produces: `api<T>(path: string, init?: RequestInit): Promise<T>` (prefixes `/api/v1`, sets JSON content type when a body is present, adds `X-CSRF-Token` from the `assayr_csrf` cookie on non-GET/HEAD, dispatches `window` event `assayr:unauthorized` on 401, throws `ApiError(status, message)` using the server's `detail`); `readCookie(name)`; types `Me`, `RoleGrant`, `Owner`, `ControlSummary`, `ControlPage`, `EvidenceSlot`, `ControlDetail`, `ControlStats`; hooks `useMe()`, `useLogin()`, `useLogout()`; `safeNext(next?: string): string`; `createAppRouter(history?: RouterHistory)`; test helpers `renderApp(path)`, `mockApi(routes)`, `json(status, body)`, constant `ME`.

- [ ] **Step 1: Write the failing tests**

`frontend/src/test/render.tsx`:
```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { createMemoryHistory, RouterProvider } from "@tanstack/react-router"
import { render } from "@testing-library/react"
import type { Me } from "../api/types"
import { createAppRouter } from "../router"

export const ME: Me = {
  id: "00000000-0000-0000-0000-000000000001",
  email: "sana@acme.com",
  full_name: "Sana Malik",
  is_active: true,
  roles: [{ role: "isms_manager", scope_id: null }],
  permissions: ["audit_log:read", "controls:read", "controls:write"],
}

export const json = (status: number, body: unknown) =>
  new Response(status === 204 ? null : JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  })

type Handler = (url: URL, init: RequestInit) => Response | Promise<Response>

/** Stub fetch. Keys look like "GET /controls" (path after /api/v1, no query string). */
export function mockApi(routes: Record<string, Handler>) {
  const calls: { method: string; url: URL; init: RequestInit }[] = []
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init: RequestInit = {}) => {
    const url = new URL(String(input), "http://localhost")
    const method = (init.method ?? "GET").toUpperCase()
    calls.push({ method, url, init })
    const handler = routes[`${method} ${url.pathname.replace(/^\/api\/v1/, "")}`]
    return handler ? handler(url, init) : json(404, { detail: `No mock for ${method} ${url.pathname}` })
  })
  vi.stubGlobal("fetch", fetchMock)
  return calls
}

export function renderApp(path: string) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const router = createAppRouter(createMemoryHistory({ initialEntries: [path] }))
  render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
  return { router, queryClient }
}
```

`frontend/src/api/client.test.ts`:
```ts
import { api, ApiError } from "./client"
import { json, mockApi } from "../test/render"

test("GET requests do not send the CSRF header", async () => {
  document.cookie = "assayr_csrf=token-123; path=/"
  const calls = mockApi({ "GET /auth/me": () => json(200, { ok: true }) })
  await api("/auth/me")
  expect(new Headers(calls[0].init.headers).has("X-CSRF-Token")).toBe(false)
})

test("POST requests send the CSRF header from the cookie and a JSON content type", async () => {
  document.cookie = "assayr_csrf=token-123; path=/"
  const calls = mockApi({ "POST /auth/logout": () => json(204, null) })
  await expect(api("/auth/logout", { method: "POST", body: "{}" })).resolves.toBeUndefined()
  const headers = new Headers(calls[0].init.headers)
  expect(headers.get("X-CSRF-Token")).toBe("token-123")
  expect(headers.get("Content-Type")).toBe("application/json")
})

test("errors carry the server's message", async () => {
  mockApi({ "GET /controls/A.9.99": () => json(404, { detail: "Control not found." }) })
  await expect(api("/controls/A.9.99")).rejects.toEqual(new ApiError(404, "Control not found."))
})

test("401 responses announce that the session ended", async () => {
  mockApi({ "GET /auth/me": () => json(401, { detail: "Not signed in." }) })
  const listener = vi.fn()
  window.addEventListener("assayr:unauthorized", listener)
  await expect(api("/auth/me")).rejects.toBeInstanceOf(ApiError)
  window.removeEventListener("assayr:unauthorized", listener)
  expect(listener).toHaveBeenCalledOnce()
})
```

`frontend/src/auth/session.test.ts`:
```ts
import { safeNext } from "./session"

test.each([
  [undefined, "/"],
  ["/controls?theme=People", "/controls?theme=People"],
  ["//evil.com", "/"],
  ["https://evil.com/x", "/"],
  ["/\\evil.com", "/"],
  ["javascript:alert(1)", "/"],
  ["/login?next=/x", "/"],
])("safeNext(%s) -> %s", (input, expected) => {
  expect(safeNext(input)).toBe(expected)
})
```

`frontend/src/pages/Login.test.tsx`:
```tsx
import { screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { json, ME, mockApi, renderApp } from "../test/render"

test("redirects to sign-in and returns to the requested page afterwards", async () => {
  let signedIn = false
  mockApi({
    "GET /auth/me": () => (signedIn ? json(200, ME) : json(401, { detail: "Not signed in." })),
    "POST /auth/login": () => {
      signedIn = true
      return json(200, ME)
    },
  })
  const { router } = renderApp("/styleguide")
  await screen.findByRole("heading", { name: "Sign in to Assayr" })
  expect(router.state.location.search).toEqual({ next: "/styleguide" })
  await userEvent.type(screen.getByLabelText("Email"), "sana@acme.com")
  await userEvent.type(screen.getByLabelText("Password"), "correct-horse-battery")
  await userEvent.click(screen.getByRole("button", { name: "Sign in" }))
  await screen.findByRole("heading", { name: "Styleguide" })
})

test("shows the server's message when sign-in fails", async () => {
  mockApi({
    "GET /auth/me": () => json(401, { detail: "Not signed in." }),
    "POST /auth/login": () =>
      json(401, { detail: "Email or password is incorrect, or the account is temporarily locked." }),
  })
  renderApp("/login")
  await userEvent.type(await screen.findByLabelText("Email"), "sana@acme.com")
  await userEvent.type(screen.getByLabelText("Password"), "wrong-password-here")
  await userEvent.click(screen.getByRole("button", { name: "Sign in" }))
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Email or password is incorrect, or the account is temporarily locked.",
  )
})
```

- [ ] **Step 2: Run to verify failure**

Run: `cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && cd frontend && npm test`
Expected: FAIL — unresolved imports `./client`, `./session`, `../router`.

- [ ] **Step 3: Implement**

`frontend/src/api/types.ts`:
```ts
export interface RoleGrant { role: string; scope_id: string | null }
export interface Me {
  id: string
  email: string
  full_name: string
  is_active: boolean
  roles: RoleGrant[]
  permissions: string[]
}
export interface Owner { id: string; full_name: string }
export interface ControlSummary {
  id: string
  scope_id: string
  code: string
  title: string
  theme: string | null
  status: string
  implementation_status: string
  owner: Owner | null
  evidence_required: number
}
export interface ControlPage { items: ControlSummary[]; next_cursor: number | null }
export interface EvidenceSlot {
  id: string
  name: string
  evidence_type: string
  required: boolean
  freshness_days: number | null
  rules: string[]
}
export interface ControlDetail extends ControlSummary {
  description: string | null
  review_frequency: string | null
  default_owner_role: string | null
  implementation_text: string | null
  slots: EvidenceSlot[]
  requirements: { ref: string; title: string }[]
}
export interface ControlStats {
  scope_id: string
  total: number
  by_status: Record<string, number>
  by_theme: Record<string, number>
}
```

`frontend/src/api/client.ts`:
```ts
export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message)
    this.name = "ApiError"
  }
}

export function readCookie(name: string): string | undefined {
  const prefix = `${name}=`
  const found = document.cookie.split("; ").find((c) => c.startsWith(prefix))
  return found ? decodeURIComponent(found.slice(prefix.length)) : undefined
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const method = (init.method ?? "GET").toUpperCase()
  const headers = new Headers(init.headers)
  if (init.body !== undefined && !headers.has("Content-Type")) headers.set("Content-Type", "application/json")
  if (method !== "GET" && method !== "HEAD") {
    const csrf = readCookie("assayr_csrf")
    if (csrf) headers.set("X-CSRF-Token", csrf)
  }
  const response = await fetch(`/api/v1${path}`, { ...init, method, headers, credentials: "same-origin" })
  if (response.status === 401) window.dispatchEvent(new CustomEvent("assayr:unauthorized"))
  if (!response.ok) {
    let message = response.statusText || `Request failed (${response.status})`
    try {
      const body = await response.json()
      if (typeof body?.detail === "string") message = body.detail
    } catch {
      /* non-JSON error body: keep the status text */
    }
    throw new ApiError(response.status, message)
  }
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}
```

`frontend/src/auth/session.ts`:
```ts
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { api } from "../api/client"
import type { Me } from "../api/types"

export function useMe() {
  return useQuery({ queryKey: ["me"], queryFn: () => api<Me>("/auth/me"), retry: false, staleTime: 60_000 })
}

export function useLogin() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (credentials: { email: string; password: string }) =>
      api<Me>("/auth/login", { method: "POST", body: JSON.stringify(credentials) }),
    onSuccess: (me) => queryClient.setQueryData(["me"], me),
  })
}

export function useLogout() {
  return useMutation({ mutationFn: () => api<void>("/auth/logout", { method: "POST" }) })
}

/** Only allow same-site relative paths after sign-in; anything else goes home. */
export function safeNext(next: string | undefined): string {
  if (!next || !next.startsWith("/") || next.startsWith("//") || next.includes("\\")) return "/"
  if (next === "/login" || next.startsWith("/login?")) return "/"
  return next
}
```

`frontend/src/pages/Login.tsx`:
```tsx
import { useRouter, useSearch } from "@tanstack/react-router"
import { type FormEvent, useState } from "react"
import { safeNext, useLogin } from "../auth/session"
import { Button } from "../components/Button"

export function LoginPage() {
  const { next } = useSearch({ from: "/login" })
  const router = useRouter()
  const login = useLogin()
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    try {
      await login.mutateAsync({ email, password })
      router.history.push(safeNext(next))
    } catch {
      /* the error is rendered from login.error */
    }
  }

  return (
    <main className="grid min-h-full place-items-center px-4 py-12">
      <form onSubmit={onSubmit} className="grid w-full max-w-sm gap-4 rounded-xl border border-line bg-surface p-6" noValidate>
        <div className="flex items-center gap-2.5">
          <img src="/favicon.svg" alt="" width={32} height={32} />
          <span className="font-display text-xl font-extrabold tracking-tight">assayr</span>
        </div>
        <h1 className="font-display text-2xl font-extrabold tracking-tight">Sign in to Assayr</h1>
        {login.error && (
          <p role="alert" className="rounded-lg bg-bad-soft px-3 py-2 text-[13px] text-fg">
            {login.error.message}
          </p>
        )}
        <label className="grid gap-1 text-[13px] font-medium" htmlFor="login-email">
          Email
          <input id="login-email" type="email" autoComplete="username" required value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="rounded-lg border border-line-2 bg-surface px-3 py-2 text-sm font-normal" />
        </label>
        <label className="grid gap-1 text-[13px] font-medium" htmlFor="login-password">
          Password
          <input id="login-password" type="password" autoComplete="current-password" required value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="rounded-lg border border-line-2 bg-surface px-3 py-2 text-sm font-normal" />
        </label>
        <Button type="submit" disabled={login.isPending} className="justify-center">
          {login.isPending ? "Signing in…" : "Sign in"}
        </Button>
      </form>
    </main>
  )
}
```

`frontend/src/layouts/AppLayout.tsx`:
```tsx
import { useQueryClient } from "@tanstack/react-query"
import { Navigate, Outlet, useLocation } from "@tanstack/react-router"
import { useEffect } from "react"
import { ApiError } from "../api/client"
import { useMe } from "../auth/session"

export function AppLayout() {
  const me = useMe()
  const location = useLocation()
  const queryClient = useQueryClient()

  useEffect(() => {
    const onUnauthorized = () => queryClient.invalidateQueries({ queryKey: ["me"] })
    window.addEventListener("assayr:unauthorized", onUnauthorized)
    return () => window.removeEventListener("assayr:unauthorized", onUnauthorized)
  }, [queryClient])

  if (me.isPending) return <p role="status" className="p-8 text-fg-3">Loading…</p>
  if (me.isError) {
    if (me.error instanceof ApiError && me.error.status === 401) {
      return <Navigate to="/login" search={{ next: location.href }} replace />
    }
    return (
      <p role="alert" className="p-8">
        Can't reach the Assayr server. Check that the API is running, then reload this page.
      </p>
    )
  }
  return (
    <main className="p-6">
      <Outlet />
    </main>
  )
}
```

`frontend/src/pages/Dashboard.tsx` (placeholder, replaced in Task 13):
```tsx
export function DashboardPage() {
  return <h1 className="font-display text-[26px] font-extrabold tracking-tight">Home</h1>
}
```

`frontend/src/pages/Controls.tsx` (placeholder, replaced in Task 13):
```tsx
export function ControlsPage() {
  return <h1 className="font-display text-[26px] font-extrabold tracking-tight">Controls</h1>
}
```

`frontend/src/router.tsx`:
```tsx
import { createRootRoute, createRoute, createRouter, Outlet, type RouterHistory } from "@tanstack/react-router"
import { AppLayout } from "./layouts/AppLayout"
import { ControlsPage } from "./pages/Controls"
import { DashboardPage } from "./pages/Dashboard"
import { LoginPage } from "./pages/Login"
import { Styleguide } from "./pages/Styleguide"

const rootRoute = createRootRoute({ component: () => <Outlet /> })

const loginRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/login",
  validateSearch: (search: Record<string, unknown>): { next?: string } => ({
    next: typeof search.next === "string" ? search.next : undefined,
  }),
  component: LoginPage,
})

const appRoute = createRoute({ getParentRoute: () => rootRoute, id: "app", component: AppLayout })
const dashboardRoute = createRoute({ getParentRoute: () => appRoute, path: "/", component: DashboardPage })
const controlsRoute = createRoute({ getParentRoute: () => appRoute, path: "/controls", component: ControlsPage })
const styleguideRoute = createRoute({ getParentRoute: () => appRoute, path: "/styleguide", component: Styleguide })

export const routeTree = rootRoute.addChildren([
  loginRoute,
  appRoute.addChildren([dashboardRoute, controlsRoute, styleguideRoute]),
])

export function createAppRouter(history?: RouterHistory) {
  return createRouter({ routeTree, history })
}

declare module "@tanstack/react-router" {
  interface Register {
    router: ReturnType<typeof createAppRouter>
  }
}
```

Replace `frontend/src/main.tsx`:
```tsx
import "@fontsource/ibm-plex-sans/400.css"
import "@fontsource/ibm-plex-sans/500.css"
import "@fontsource/ibm-plex-sans/600.css"
import "@fontsource/ibm-plex-mono/400.css"
import "@fontsource/ibm-plex-mono/500.css"
import "@fontsource/schibsted-grotesk/600.css"
import "@fontsource/schibsted-grotesk/800.css"
import "./styles/global.css"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { RouterProvider } from "@tanstack/react-router"
import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import { ApiError } from "./api/client"
import { createAppRouter } from "./router"

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: (count, error) => !(error instanceof ApiError && error.status < 500) && count < 2 },
  },
})
const router = createAppRouter()

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </StrictMode>,
)
```

- [ ] **Step 4: Run tests and build**

Run: `cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && cd frontend && npm test && npm run build`
Expected: all tests pass (`18 passed` including Task 11's), build succeeds.

- [ ] **Step 5: Commit**

```bash
cd "E:/Work/GRC Tool/assayr" && git add -A && git commit -m "feat(web): API client, sign-in flow and protected routes" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 13: App shell, dashboard, controls list and control detail

**Files:**
- Create: `frontend/src/lib/theme.ts`, `frontend/src/components/AppShell.tsx`, `frontend/src/api/controls.ts`, `frontend/src/pages/ControlDetail.tsx`
- Modify (replace): `frontend/src/pages/Dashboard.tsx`, `frontend/src/pages/Controls.tsx`, `frontend/src/layouts/AppLayout.tsx`, `frontend/src/router.tsx`, `frontend/src/main.tsx`
- Test: `frontend/src/components/AppShell.test.tsx`, `frontend/src/pages/Dashboard.test.tsx`, `frontend/src/pages/Controls.test.tsx`, `frontend/src/pages/ControlDetail.test.tsx`, `frontend/src/lib/theme.test.ts`

**Interfaces:**
- Consumes: `api`, types, `useMe`, `useLogout` (Task 12); `Button`, `StatusPill`, `ControlId`, `Icon` (Task 11); backend controls API (Task 9).
- Produces: `useControls(filters: { theme?: string; q?: string })` (infinite query), `useControl(code)`, `useUpdateControl(code)`, `useControlStats()`; `IMPLEMENTATION_LABEL`; `initTheme()`, `toggleTheme(): "light" | "dark"`, `effectiveTheme()`; `AppShell({ me, children })`; routes `/controls` with search `{ theme?, q? }` and `/controls/$code`.

- [ ] **Step 1: Write the failing tests**

`frontend/src/lib/theme.test.ts`:
```ts
import { effectiveTheme, initTheme, toggleTheme } from "./theme"

test("toggling flips the theme and remembers it", () => {
  expect(effectiveTheme()).toBe("light")
  expect(toggleTheme()).toBe("dark")
  expect(document.documentElement.dataset.theme).toBe("dark")
  delete document.documentElement.dataset.theme
  initTheme()
  expect(document.documentElement.dataset.theme).toBe("dark")
  localStorage.clear()
})

test("blocked storage does not break theming", () => {
  vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
    throw new Error("blocked")
  })
  expect(() => toggleTheme()).not.toThrow()
  vi.restoreAllMocks()
})
```

`frontend/src/components/AppShell.test.tsx`:
```tsx
import { screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { json, ME, mockApi, renderApp } from "../test/render"

test("signing out ends the session and shows the sign-in page", async () => {
  let signedIn = true
  const calls = mockApi({
    "GET /auth/me": () => (signedIn ? json(200, ME) : json(401, { detail: "Not signed in." })),
    "GET /controls/summary": () => json(200, { scope_id: "s", total: 93, by_status: { not_started: 93 }, by_theme: {} }),
    "POST /auth/logout": () => {
      signedIn = false
      return json(204, null)
    },
  })
  renderApp("/")
  await userEvent.click(await screen.findByRole("button", { name: "Sign out" }))
  await screen.findByRole("heading", { name: "Sign in to Assayr" })
  expect(calls.some((c) => c.method === "POST" && c.url.pathname === "/api/v1/auth/logout")).toBe(true)
})

test("navigation marks the current page and lists upcoming modules as unavailable", async () => {
  mockApi({
    "GET /auth/me": () => json(200, ME),
    "GET /controls": () => json(200, { items: [], next_cursor: null }),
  })
  renderApp("/controls")
  expect(await screen.findByRole("link", { name: "Controls" })).toHaveAttribute("aria-current", "page")
  expect(screen.getByText("Risks").closest("[aria-disabled]")).toHaveAttribute("aria-disabled", "true")
})
```

`frontend/src/pages/Dashboard.test.tsx`:
```tsx
import { screen } from "@testing-library/react"
import { json, ME, mockApi, renderApp } from "../test/render"

test("shows control totals by theme and an explanation where readiness will appear", async () => {
  mockApi({
    "GET /auth/me": () => json(200, ME),
    "GET /controls/summary": () =>
      json(200, {
        scope_id: "s",
        total: 93,
        by_status: { not_started: 93 },
        by_theme: { Organizational: 37, People: 8, Physical: 14, Technological: 34 },
      }),
  })
  renderApp("/")
  expect((await screen.findByText("Controls in scope")).parentElement).toHaveTextContent("93")
  expect(screen.getByText("Organizational").closest("tr")).toHaveTextContent("37")
  expect(screen.getByText(/Readiness appears once the first evidence is verified/)).toBeInTheDocument()
})
```

`frontend/src/pages/Controls.test.tsx`:
```tsx
import { screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import type { ControlSummary } from "../api/types"
import { json, ME, mockApi, renderApp } from "../test/render"

const row = (n: number, code: string, title: string, theme = "Organizational"): ControlSummary => ({
  id: `id-${n}`, scope_id: "s", code, title, theme, status: "not_started",
  implementation_status: "not_started", owner: null, evidence_required: 2,
})

test("lists controls, loads more and filters by theme through the URL", async () => {
  const calls = mockApi({
    "GET /auth/me": () => json(200, ME),
    "GET /controls": (url) => {
      if (url.searchParams.get("theme") === "People") {
        return json(200, { items: [row(9, "A.6.1", "Screening", "People")], next_cursor: null })
      }
      return url.searchParams.get("cursor") === "2"
        ? json(200, { items: [row(3, "A.5.3", "Segregation of duties")], next_cursor: null })
        : json(200, { items: [row(1, "A.5.1", "Policies for information security"), row(2, "A.5.2", "Information security roles and responsibilities")], next_cursor: 2 })
    },
  })
  const { router } = renderApp("/controls")
  expect(await screen.findByRole("link", { name: "Policies for information security" })).toHaveAttribute("href", "/controls/A.5.1")
  await userEvent.click(screen.getByRole("button", { name: "Load more" }))
  expect(await screen.findByText("Segregation of duties")).toBeInTheDocument()
  await userEvent.selectOptions(screen.getByLabelText("Theme"), "People")
  expect(await screen.findByText("Screening")).toBeInTheDocument()
  expect(router.state.location.search).toEqual({ theme: "People" })
  expect(calls.some((c) => c.url.searchParams.get("theme") === "People")).toBe(true)
})
```

`frontend/src/pages/ControlDetail.test.tsx`:
```tsx
import { screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import type { ControlDetail } from "../api/types"
import { json, ME, mockApi, renderApp } from "../test/render"

const DETAIL: ControlDetail = {
  id: "c1", scope_id: "s", code: "A.8.13", title: "Information backup", theme: "Technological",
  status: "not_started", implementation_status: "not_started", owner: null, evidence_required: 3,
  description: "Backup copies are maintained and regularly tested.", review_frequency: "Monthly",
  default_owner_role: "IT Manager", implementation_text: null,
  slots: [{ id: "s1", name: "Backup policy", evidence_type: "Policy", required: true, freshness_days: 31, rules: ["V-FMT"] }],
  requirements: [{ ref: "A.8.13", title: "Information backup" }],
}

test("a manager saves the implementation description", async () => {
  document.cookie = "assayr_csrf=token-xyz; path=/"
  const calls = mockApi({
    "GET /auth/me": () => json(200, ME),
    "GET /controls/A.8.13": () => json(200, DETAIL),
    "PATCH /controls/A.8.13": (_url, init) =>
      json(200, { ...DETAIL, ...JSON.parse(String(init.body)) }),
  })
  renderApp("/controls/A.8.13")
  expect(await screen.findByRole("heading", { name: "Information backup" })).toBeInTheDocument()
  expect(screen.getByText("Backup policy")).toBeInTheDocument()
  expect(screen.getByText("Refresh every 31 days")).toBeInTheDocument()
  await userEvent.type(screen.getByLabelText("How we do it"), "Nightly Veeam jobs.")
  await userEvent.selectOptions(screen.getByLabelText("Implementation status"), "partial")
  await userEvent.click(screen.getByRole("button", { name: "Save changes" }))
  expect(await screen.findByRole("status")).toHaveTextContent("Saved")
  const patch = calls.find((c) => c.method === "PATCH")!
  expect(JSON.parse(String(patch.init.body))).toEqual({
    implementation_status: "partial",
    implementation_text: "Nightly Veeam jobs.",
  })
  expect(new Headers(patch.init.headers).get("X-CSRF-Token")).toBe("token-xyz")
})

test("people without write access see the description read-only", async () => {
  mockApi({
    "GET /auth/me": () => json(200, { ...ME, permissions: ["controls:read"] }),
    "GET /controls/A.8.13": () => json(200, { ...DETAIL, implementation_text: "Nightly jobs." }),
  })
  renderApp("/controls/A.8.13")
  expect(await screen.findByText("Nightly jobs.")).toBeInTheDocument()
  expect(screen.queryByRole("button", { name: "Save changes" })).not.toBeInTheDocument()
})

test("an unknown control shows a helpful message", async () => {
  mockApi({
    "GET /auth/me": () => json(200, ME),
    "GET /controls/A.9.99": () => json(404, { detail: "Control not found." }),
  })
  renderApp("/controls/A.9.99")
  expect(await screen.findByRole("alert")).toHaveTextContent("Control not found.")
})
```

- [ ] **Step 2: Run to verify failure**

Run: `cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && cd frontend && npm test`
Expected: FAIL — `./theme` unresolved; dashboard/controls assertions fail against placeholders.

- [ ] **Step 3: Implement**

`frontend/src/lib/theme.ts`:
```ts
export type Theme = "light" | "dark"
const KEY = "assayr-theme"

function stored(): Theme | null {
  try {
    const value = localStorage.getItem(KEY)
    return value === "light" || value === "dark" ? value : null
  } catch {
    return null
  }
}

export function effectiveTheme(): Theme {
  const explicit = document.documentElement.dataset.theme
  if (explicit === "light" || explicit === "dark") return explicit
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light"
}

export function initTheme(): void {
  const theme = stored()
  if (theme) document.documentElement.dataset.theme = theme
}

export function toggleTheme(): Theme {
  const next: Theme = effectiveTheme() === "dark" ? "light" : "dark"
  document.documentElement.dataset.theme = next
  try {
    localStorage.setItem(KEY, next)
  } catch {
    /* storage blocked: the choice lasts for this page view only */
  }
  return next
}
```

`frontend/src/api/controls.ts`:
```ts
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { api } from "./client"
import type { ControlDetail, ControlPage, ControlStats } from "./types"

export const IMPLEMENTATION_LABEL: Record<string, string> = {
  not_started: "Not started",
  planned: "Planned",
  partial: "Partially implemented",
  implemented: "Implemented",
}

export function useControls(filters: { theme?: string; q?: string }) {
  return useInfiniteQuery({
    queryKey: ["controls", filters],
    initialPageParam: undefined as number | undefined,
    queryFn: ({ pageParam }) => {
      const params = new URLSearchParams()
      if (filters.theme) params.set("theme", filters.theme)
      if (filters.q) params.set("q", filters.q)
      if (pageParam !== undefined) params.set("cursor", String(pageParam))
      const query = params.toString()
      return api<ControlPage>(`/controls${query ? `?${query}` : ""}`)
    },
    getNextPageParam: (last) => last.next_cursor ?? undefined,
  })
}

export function useControl(code: string) {
  return useQuery({ queryKey: ["control", code], queryFn: () => api<ControlDetail>(`/controls/${encodeURIComponent(code)}`) })
}

export function useControlStats() {
  return useQuery({ queryKey: ["controls", "summary"], queryFn: () => api<ControlStats>("/controls/summary") })
}

export function useUpdateControl(code: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (changes: { implementation_status?: string; implementation_text?: string | null }) =>
      api<ControlDetail>(`/controls/${encodeURIComponent(code)}`, { method: "PATCH", body: JSON.stringify(changes) }),
    onSuccess: (detail) => {
      queryClient.setQueryData(["control", code], detail)
      queryClient.invalidateQueries({ queryKey: ["controls"] })
    },
  })
}
```

`frontend/src/components/AppShell.tsx`:
```tsx
import { useQueryClient } from "@tanstack/react-query"
import { Link, useRouter } from "@tanstack/react-router"
import type { ReactNode } from "react"
import type { Me } from "../api/types"
import { useLogout } from "../auth/session"
import { toggleTheme } from "../lib/theme"
import { Button } from "./Button"
import { Icon } from "./icons"

type NavItem = { label: string; icon: string; to?: "/" | "/controls" }
const NAV: { group: string | null; items: NavItem[] }[] = [
  { group: null, items: [{ label: "Home", icon: "home", to: "/" }] },
  { group: "Comply", items: [
    { label: "Controls", icon: "controls", to: "/controls" },
    { label: "Evidence", icon: "evidence" },
    { label: "SoA", icon: "soa" },
    { label: "Policies", icon: "policy" },
  ] },
  { group: "Risk", items: [{ label: "Risks", icon: "risk" }] },
  { group: "Assure", items: [{ label: "Audits", icon: "audit" }] },
]

const itemClass = "flex items-center gap-2.5 rounded-lg px-2.5 py-[7px] font-medium"

export function AppShell({ me, children }: { me: Me; children: ReactNode }) {
  const logout = useLogout()
  const router = useRouter()
  const queryClient = useQueryClient()

  async function signOut() {
    await logout.mutateAsync()
    router.history.push("/login")
    queryClient.removeQueries({ queryKey: ["me"] })
  }

  return (
    <div className="grid h-full grid-cols-1 md:grid-cols-[236px_minmax(0,1fr)]">
      <nav aria-label="Main navigation" className="hidden flex-col gap-1 border-r border-line bg-surface px-3 py-4 md:flex">
        <div className="flex items-center gap-2.5 px-2 pb-4">
          <img src="/favicon.svg" alt="" width={28} height={28} />
          <span className="font-display text-[21px] font-extrabold tracking-tight">assayr</span>
        </div>
        {NAV.map((section) => (
          <div key={section.group ?? "top"} className="grid gap-0.5">
            {section.group && (
              <p className="px-2.5 pb-1.5 pt-4 text-[11px] font-medium uppercase tracking-[0.08em] text-fg-3">{section.group}</p>
            )}
            {section.items.map((item) =>
              item.to ? (
                <Link key={item.label} to={item.to} activeOptions={{ exact: item.to === "/" }}
                  className={`${itemClass} text-fg-2 hover:bg-subtle hover:text-fg data-[status=active]:bg-primary-soft data-[status=active]:text-primary`}>
                  <Icon name={item.icon} size={18} />
                  <span>{item.label}</span>
                </Link>
              ) : (
                <span key={item.label} aria-disabled="true" className={`${itemClass} cursor-default text-fg-3`}>
                  <Icon name={item.icon} size={18} />
                  <span>{item.label}</span>
                  <span className="ml-auto font-mono text-[10px]">soon</span>
                </span>
              ),
            )}
          </div>
        ))}
        <p className="mt-auto border-t border-line px-2.5 pt-3 text-xs text-fg-3">On-prem · no data leaves your network</p>
      </nav>
      <div className="flex min-w-0 flex-col overflow-hidden">
        <header className="flex items-center gap-3 border-b border-line bg-surface px-4 py-2.5 md:px-6">
          <span className="font-display text-lg font-extrabold tracking-tight md:hidden">assayr</span>
          <div className="ml-auto flex items-center gap-2">
            <Button variant="ghost" size="sm" onClick={() => toggleTheme()} aria-label="Toggle light or dark theme">
              <Icon name="theme" />
            </Button>
            <span className="hidden text-[13px] text-fg-2 sm:inline">{me.full_name}</span>
            <Button variant="secondary" size="sm" onClick={signOut} disabled={logout.isPending}>
              <Icon name="logout" />
              Sign out
            </Button>
          </div>
        </header>
        <main className="flex-1 overflow-y-auto px-4 py-6 md:px-7">{children}</main>
      </div>
    </div>
  )
}
```
Note: TanStack Router's `Link` sets `aria-current="page"` and `data-status="active"` on the active link.

Replace `frontend/src/layouts/AppLayout.tsx` — change only the final `return` to render the shell:
```tsx
import { AppShell } from "../components/AppShell"
```
```tsx
  return (
    <AppShell me={me.data}>
      <Outlet />
    </AppShell>
  )
```

Replace `frontend/src/pages/Dashboard.tsx`:
```tsx
import { useControlStats } from "../api/controls"
import { StatusPill } from "../components/StatusPill"
import { useMe } from "../auth/session"

export function DashboardPage() {
  const me = useMe()
  const stats = useControlStats()
  const firstName = me.data?.full_name.split(" ")[0] ?? ""

  return (
    <div className="mx-auto grid max-w-5xl gap-4">
      <header className="mb-2">
        <p className="mb-2 text-[11px] font-medium uppercase tracking-[0.08em] text-fg-3">ISO/IEC 27001:2022</p>
        <h1 className="font-display text-[26px] font-extrabold tracking-tight">Welcome, {firstName}</h1>
      </header>
      {stats.isError && <p role="alert">{stats.error.message}</p>}
      {stats.data && (
        <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)]">
          <section className="grid content-start gap-3 rounded-xl border border-line bg-surface p-5">
            <p className="text-[11px] font-medium uppercase tracking-[0.08em] text-fg-3">Controls in scope</p>
            <p className="font-display text-4xl font-extrabold tabular-nums tracking-tight">{stats.data.total}</p>
            <div className="flex flex-wrap gap-2">
              {Object.entries(stats.data.by_status).map(([status, n]) => (
                <span key={status} className="inline-flex items-center gap-1.5 text-[13px]">
                  <StatusPill status={status} /> <b className="tabular-nums">{n}</b>
                </span>
              ))}
            </div>
            <p className="text-[13px] text-fg-2">
              Readiness appears once the first evidence is verified. Start by describing how each control is
              implemented.
            </p>
          </section>
          <section className="rounded-xl border border-line bg-surface">
            <h2 className="border-b border-line px-5 py-3.5 text-[15px] font-semibold">By Annex A theme</h2>
            <table className="w-full text-[13.5px]">
              <tbody>
                {Object.entries(stats.data.by_theme).map(([theme, n]) => (
                  <tr key={theme} className="border-b border-line last:border-0">
                    <td className="px-5 py-2.5">{theme}</td>
                    <td className="px-5 py-2.5 text-right font-medium tabular-nums">{n}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        </div>
      )}
    </div>
  )
}
```

Replace `frontend/src/pages/Controls.tsx`:
```tsx
import { Link, useNavigate, useSearch } from "@tanstack/react-router"
import { type FormEvent, useState } from "react"
import { useControls } from "../api/controls"
import { Button } from "../components/Button"
import { ControlId } from "../components/ControlId"
import { StatusPill } from "../components/StatusPill"

const THEMES = ["Organizational", "People", "Physical", "Technological"]

export function ControlsPage() {
  const search = useSearch({ from: "/app/controls" })
  const navigate = useNavigate({ from: "/controls" })
  const [query, setQuery] = useState(search.q ?? "")
  const controls = useControls({ theme: search.theme, q: search.q })
  const rows = controls.data?.pages.flatMap((p) => p.items) ?? []

  function onSearch(event: FormEvent) {
    event.preventDefault()
    navigate({ search: (prev) => ({ ...prev, q: query.trim() || undefined }) })
  }

  return (
    <div className="mx-auto grid max-w-6xl gap-4">
      <header>
        <p className="mb-2 text-[11px] font-medium uppercase tracking-[0.08em] text-fg-3">ISO/IEC 27001:2022 · Annex A</p>
        <h1 className="font-display text-[26px] font-extrabold tracking-tight">Controls</h1>
      </header>
      <section className="rounded-xl border border-line bg-surface">
        <div className="flex flex-wrap items-center gap-2 border-b border-line px-3.5 py-3">
          <label htmlFor="theme-filter" className="text-[13px] text-fg-2">Theme</label>
          <select id="theme-filter" value={search.theme ?? ""}
            onChange={(e) => navigate({ search: (prev) => ({ ...prev, theme: e.target.value || undefined }) })}
            className="rounded-lg border border-line-2 bg-surface px-2.5 py-1.5 text-[13px]">
            <option value="">All themes</option>
            {THEMES.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
          <form onSubmit={onSearch} className="ml-auto flex min-w-0 flex-1 justify-end gap-2" role="search">
            <label htmlFor="control-search" className="sr-only">Search controls</label>
            <input id="control-search" value={query} onChange={(e) => setQuery(e.target.value)}
              placeholder="Filter by ID or title"
              className="w-full max-w-72 min-w-0 rounded-lg border border-line-2 bg-surface px-2.5 py-1.5 text-[13px]" />
            <Button type="submit" variant="secondary" size="sm">Search</Button>
          </form>
        </div>
        {controls.isError && <p role="alert" className="p-4">{controls.error.message}</p>}
        <div className="overflow-x-auto">
          <table className="w-full text-[13.5px]">
            <thead>
              <tr className="text-left text-[11.5px] uppercase tracking-[0.06em] text-fg-3">
                <th className="px-3.5 py-3 font-medium">ID</th>
                <th className="px-3.5 py-3 font-medium">Control</th>
                <th className="px-3.5 py-3 font-medium">Status</th>
                <th className="px-3.5 py-3 font-medium">Evidence</th>
                <th className="px-3.5 py-3 font-medium">Owner</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((c) => (
                <tr key={c.id} className="border-t border-line hover:bg-subtle">
                  <td className="px-3.5 py-2.5"><ControlId code={c.code} /></td>
                  <td className="min-w-60 px-3.5 py-2.5">
                    <Link to="/controls/$code" params={{ code: c.code }} className="text-fg hover:text-primary">{c.title}</Link>
                  </td>
                  <td className="px-3.5 py-2.5"><StatusPill status={c.status} /></td>
                  <td className="whitespace-nowrap px-3.5 py-2.5 tabular-nums text-fg-2">0 / {c.evidence_required}</td>
                  <td className="whitespace-nowrap px-3.5 py-2.5 text-fg-2">{c.owner?.full_name ?? "Unassigned"}</td>
                </tr>
              ))}
              {controls.isSuccess && rows.length === 0 && (
                <tr><td colSpan={5} className="px-3.5 py-8 text-center text-fg-3">No controls match these filters.</td></tr>
              )}
            </tbody>
          </table>
        </div>
        {controls.hasNextPage && (
          <div className="border-t border-line p-3 text-center">
            <Button variant="secondary" onClick={() => controls.fetchNextPage()} disabled={controls.isFetchingNextPage}>
              {controls.isFetchingNextPage ? "Loading…" : "Load more"}
            </Button>
          </div>
        )}
      </section>
    </div>
  )
}
```

`frontend/src/pages/ControlDetail.tsx`:
```tsx
import { Link, useParams } from "@tanstack/react-router"
import { type FormEvent, useEffect, useState } from "react"
import { IMPLEMENTATION_LABEL, useControl, useUpdateControl } from "../api/controls"
import type { ControlDetail as Detail } from "../api/types"
import { useMe } from "../auth/session"
import { Button } from "../components/Button"
import { ControlId } from "../components/ControlId"
import { StatusPill } from "../components/StatusPill"

export function ControlDetailPage() {
  const { code } = useParams({ from: "/app/controls/$code" })
  const control = useControl(code)
  const me = useMe()

  if (control.isPending) return <p role="status" className="text-fg-3">Loading…</p>
  if (control.isError) return <p role="alert">{control.error.message}</p>
  const c = control.data
  const perms = me.data?.permissions ?? []
  const canEdit = perms.includes("controls:write") || (perms.includes("controls:write_own") && c.owner?.id === me.data?.id)

  return (
    <div className="mx-auto grid max-w-5xl gap-4">
      <nav aria-label="Breadcrumb" className="text-[13px] text-fg-3">
        <Link to="/controls" className="hover:text-fg">Controls</Link> <span aria-hidden="true">›</span> <ControlId code={c.code} />
      </nav>
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <p className="mb-2 font-mono text-[13px] text-fg-3">{c.code} · {c.theme} controls</p>
          <h1 className="font-display text-[28px] font-extrabold tracking-tight">{c.title}</h1>
          <p className="mt-2 text-[13px] text-fg-2">
            Owner: {c.owner?.full_name ?? `Unassigned (suggested: ${c.default_owner_role ?? "ISMS manager"})`} · Review:{" "}
            {c.review_frequency?.toLowerCase() ?? "not set"}
          </p>
        </div>
        <StatusPill status={c.status} />
      </header>
      <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_300px]">
        <div className="grid content-start gap-4">
          <section className="rounded-xl border border-line bg-surface">
            <h2 className="border-b border-line px-5 py-3.5 text-[15px] font-semibold">Evidence</h2>
            <ul>
              {c.slots.map((s) => (
                <li key={s.id} className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-5 py-3.5 last:border-0">
                  <div className="min-w-0">
                    <p className="font-semibold">{s.name}</p>
                    <p className="text-[12.5px] text-fg-3">
                      {s.evidence_type}
                      {s.freshness_days ? ` · ` : ""}
                      {s.freshness_days ? `Refresh every ${s.freshness_days} days` : ""}
                    </p>
                  </div>
                  <StatusPill status="not_started" />
                </li>
              ))}
            </ul>
          </section>
          <ImplementationSection control={c} canEdit={canEdit} />
        </div>
        <aside className="grid content-start gap-4">
          <section className="rounded-xl border border-line bg-surface p-5">
            <h3 className="mb-2.5 text-[11px] font-medium uppercase tracking-[0.08em] text-fg-3">What auditors look for</h3>
            <p className="text-[13px] text-fg-2">{c.description}</p>
          </section>
          <section className="rounded-xl border border-line bg-surface p-5">
            <h3 className="mb-2.5 text-[11px] font-medium uppercase tracking-[0.08em] text-fg-3">Maps to</h3>
            <ul className="grid gap-1 text-[13px]">
              {c.requirements.map((r) => <li key={r.ref}><ControlId code={r.ref} /> {r.title}</li>)}
            </ul>
          </section>
        </aside>
      </div>
    </div>
  )
}

function ImplementationSection({ control, canEdit }: { control: Detail; canEdit: boolean }) {
  const update = useUpdateControl(control.code)
  const [status, setStatus] = useState(control.implementation_status)
  const [text, setText] = useState(control.implementation_text ?? "")
  const [saved, setSaved] = useState(false)

  useEffect(() => setSaved(false), [status, text])

  if (!canEdit) {
    return (
      <section className="rounded-xl border border-line bg-surface p-5">
        <h2 className="mb-2 text-[15px] font-semibold">How we do it</h2>
        <p className="text-fg-2">{control.implementation_text || "Not described yet."}</p>
        <p className="mt-2 text-[13px] text-fg-3">{IMPLEMENTATION_LABEL[control.implementation_status]}</p>
      </section>
    )
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    const changes: { implementation_status?: string; implementation_text?: string | null } = {}
    if (status !== control.implementation_status) changes.implementation_status = status
    if (text !== (control.implementation_text ?? "")) changes.implementation_text = text || null
    await update.mutateAsync(changes)
    setSaved(true)
  }

  return (
    <form onSubmit={onSubmit} className="grid gap-3 rounded-xl border border-line bg-surface p-5">
      <label htmlFor="impl-text" className="text-[15px] font-semibold">How we do it</label>
      <textarea id="impl-text" rows={4} value={text} onChange={(e) => setText(e.target.value)}
        className="rounded-lg border border-line-2 bg-surface px-3 py-2 text-sm" />
      <div className="flex flex-wrap items-center gap-3">
        <label htmlFor="impl-status" className="text-[13px] text-fg-2">Implementation status</label>
        <select id="impl-status" value={status} onChange={(e) => setStatus(e.target.value)}
          className="rounded-lg border border-line-2 bg-surface px-2.5 py-1.5 text-[13px]">
          {Object.entries(IMPLEMENTATION_LABEL).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select>
        <Button type="submit" className="ml-auto" disabled={update.isPending}>
          {update.isPending ? "Saving…" : "Save changes"}
        </Button>
      </div>
      {update.isError && <p role="alert" className="text-[13px] text-bad">{update.error.message}</p>}
      {saved && <p role="status" className="text-[13px] text-ok">Saved</p>}
    </form>
  )
}
```

Replace `frontend/src/router.tsx` route definitions for the app branch (keep the rest):
```tsx
import { ControlDetailPage } from "./pages/ControlDetail"
```
```tsx
const controlsRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/controls",
  validateSearch: (search: Record<string, unknown>): { theme?: string; q?: string } => ({
    theme: typeof search.theme === "string" && search.theme ? search.theme : undefined,
    q: typeof search.q === "string" && search.q ? search.q : undefined,
  }),
  component: ControlsPage,
})
const controlRoute = createRoute({ getParentRoute: () => appRoute, path: "/controls/$code", component: ControlDetailPage })
```
```tsx
export const routeTree = rootRoute.addChildren([
  loginRoute,
  appRoute.addChildren([dashboardRoute, controlsRoute, controlRoute, styleguideRoute]),
])
```

In `frontend/src/main.tsx` add before `createRoot(...)`:
```tsx
import { initTheme } from "./lib/theme"
```
```tsx
initTheme()
```

- [ ] **Step 4: Run tests, typecheck and build**

Run: `cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && cd frontend && npm test && npm run build`
Expected: all tests pass; build succeeds.

- [ ] **Step 5: Try it end to end locally**

Start the backend (from Task 10 Step 5 setup): `cd backend && uv run uvicorn assayr.main:create_app --factory --port 8000` in the background, then `cd frontend && npm run dev` in the background. Open `http://localhost:5173`, sign in as `admin@acme.com` / `local-dev-password`, open Controls → A.8.13, save an implementation description, then confirm `uv run assayr audit-verify` reports an intact chain with a `control.update` entry visible at `GET /api/v1/audit-log`. Stop both servers.

- [ ] **Step 6: Commit**

```bash
cd "E:/Work/GRC Tool/assayr" && git add -A && git commit -m "feat(web): app shell, dashboard, controls list and detail" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 14: Containers and Docker Compose deployment

**Files:**
- Create: `.gitattributes`, `backend/Dockerfile`, `backend/.dockerignore`, `backend/docker-entrypoint.sh`, `frontend/Dockerfile`, `frontend/.dockerignore`, `frontend/Caddyfile`, `deploy/compose.yaml`, `deploy/assayr.env.example`, `deploy/smoke.sh`

**Interfaces:**
- Consumes: `assayr migrate`, `assayr seed`, `assayr create-admin` (Task 10); built SPA (Task 13).
- Produces: images `assayr-api` (port 8000, runs migrations + seed on start) and `assayr-web` (Caddy on 8080, serves SPA, proxies `/api/*`); `deploy/smoke.sh` end-to-end check (exit 0 on success).

- [ ] **Step 1: Write the smoke test (the failing check)**

`deploy/smoke.sh`:
```bash
#!/usr/bin/env bash
# End-to-end check of the compose stack: builds, starts, signs in, counts controls, tears down.
set -euo pipefail
cd "$(dirname "$0")"
ENV_FILE="${ENV_FILE:-assayr.env}"
[ -f "$ENV_FILE" ] || cp assayr.env.example "$ENV_FILE"
compose() { docker compose --env-file "$ENV_FILE" -f compose.yaml "$@"; }
trap 'compose down -v' EXIT

compose up -d --build --wait
compose exec -T -e ASSAYR_ADMIN_PASSWORD=smoke-test-password-123 api \
  assayr create-admin --email admin@example.com --full-name "Smoke Admin"

BASE="http://localhost:${ASSAYR_HTTP_PORT:-8080}"
JAR="$(mktemp)"
curl -fsS "$BASE/api/v1/healthz" >/dev/null
curl -fsS "$BASE/" | grep -q '<div id="root">'
curl -fsS -c "$JAR" -H 'Content-Type: application/json' \
  -d '{"email":"admin@example.com","password":"smoke-test-password-123"}' "$BASE/api/v1/auth/login" >/dev/null
total="$(curl -fsS -b "$JAR" "$BASE/api/v1/controls/summary" | sed -n 's/.*"total":\([0-9]*\).*/\1/p')"
[ "$total" = "93" ] || { echo "Expected 93 controls, got $total" >&2; exit 1; }
compose exec -T api assayr audit-verify
echo "Smoke test passed: stack is up, sign-in works and 93 controls are seeded."
```
```bash
chmod +x "E:/Work/GRC Tool/assayr/deploy/smoke.sh"
```

Run (requires Docker Desktop running): `cd "E:/Work/GRC Tool/assayr" && deploy/smoke.sh`
Expected: FAIL — `open compose.yaml: no such file or directory`. If the Docker daemon is not running, start Docker Desktop first (`docker info` must answer).

- [ ] **Step 2: Write the images and compose file**

`.gitattributes` (keeps shell scripts LF on Windows checkouts, or `/bin/sh` fails inside the container):
```gitattributes
*.sh text eol=lf
Caddyfile text eol=lf
```
Then renormalise: `cd "E:/Work/GRC Tool/assayr" && git add --renormalize .`

`backend/.dockerignore`:
```
.venv
__pycache__
*.pyc
*.db
.env
.pytest_cache
.ruff_cache
tests
```

`backend/docker-entrypoint.sh`:
```sh
#!/bin/sh
set -e
assayr migrate
assayr seed
exec "$@"
```

`backend/Dockerfile`:
```dockerfile
FROM python:3.12-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY src ./src
RUN uv sync --frozen --no-dev --no-editable

FROM python:3.12-slim
RUN useradd --system --uid 10001 --no-create-home assayr
WORKDIR /app
COPY --from=build /app /app
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod 0755 /usr/local/bin/docker-entrypoint.sh
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1
USER assayr
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --retries=12 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/readyz', timeout=3)"
ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["uvicorn", "assayr.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
```

`frontend/.dockerignore`:
```
node_modules
dist
```

`frontend/Caddyfile`:
```caddyfile
{
	admin off
	auto_https off
}

:8080 {
	encode zstd gzip
	header {
		X-Content-Type-Options nosniff
		X-Frame-Options DENY
		Referrer-Policy no-referrer
		Permissions-Policy "camera=(), microphone=(), geolocation=()"
		Content-Security-Policy "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; font-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
		-Server
	}
	handle /api/* {
		reverse_proxy {$ASSAYR_API_UPSTREAM:api:8000}
	}
	handle {
		root * /srv
		try_files {path} /index.html
		file_server
	}
}
```

`frontend/Dockerfile`:
```dockerfile
FROM node:24-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM caddy:2-alpine
COPY Caddyfile /etc/caddy/Caddyfile
COPY --from=build /app/dist /srv
EXPOSE 8080
HEALTHCHECK --interval=10s --timeout=3s --retries=6 CMD wget -q -O /dev/null http://127.0.0.1:8080/ || exit 1
```

`deploy/assayr.env.example`:
```dotenv
# Copy to deploy/assayr.env and change the password before use.
# Use letters and digits only in POSTGRES_PASSWORD (it is embedded in a connection URL).
POSTGRES_PASSWORD=change-me-to-a-long-random-value
ASSAYR_ORG_NAME=Acme Financial Services
ASSAYR_HTTP_PORT=8080
# This stack serves plain HTTP for evaluation. Put it behind TLS and set this to true for real use.
ASSAYR_SECURE_COOKIES=false
```
Note: the example password contains hyphens, which are safe in URLs; the note warns against `@`, `/`, `%`, `:`.

`deploy/compose.yaml`:
```yaml
name: assayr

services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: assayr
      POSTGRES_USER: assayr
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?Set POSTGRES_PASSWORD in assayr.env}
    volumes:
      - dbdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U assayr -d assayr"]
      interval: 5s
      retries: 20
    restart: unless-stopped

  api:
    build: ../backend
    environment:
      ASSAYR_DATABASE_URL: postgresql+pg8000://assayr:${POSTGRES_PASSWORD}@db:5432/assayr
      ASSAYR_ORG_NAME: ${ASSAYR_ORG_NAME:-My Organization}
      ASSAYR_SECURE_COOKIES: ${ASSAYR_SECURE_COOKIES:-false}
    depends_on:
      db:
        condition: service_healthy
    restart: unless-stopped

  web:
    build: ../frontend
    ports:
      - "${ASSAYR_HTTP_PORT:-8080}:8080"
    depends_on:
      api:
        condition: service_healthy
    restart: unless-stopped

volumes:
  dbdata:
```

- [ ] **Step 3: Validate and run the smoke test**

Run: `cd "E:/Work/GRC Tool/assayr/deploy" && cp -n assayr.env.example assayr.env; docker compose --env-file assayr.env config --quiet && echo "compose file valid"`
Expected: `compose file valid` (works without the daemon).

Run (Docker Desktop running): `cd "E:/Work/GRC Tool/assayr" && deploy/smoke.sh`
Expected: last line `Smoke test passed: stack is up, sign-in works and 93 controls are seeded.` If Docker is unavailable on this machine, record that the smoke test is deferred to CI (Task 15) and continue.

- [ ] **Step 4: Commit**

```bash
cd "E:/Work/GRC Tool/assayr" && git add -A && git commit -m "feat(deploy): container images, compose stack and smoke test" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 15: Continuous integration and README

**Files:**
- Create: `.github/workflows/ci.yml`, `README.md`

**Interfaces:**
- Consumes: every test command above; `deploy/smoke.sh`.
- Produces: CI jobs `backend` (ruff + pytest on SQLite and PostgreSQL 16), `frontend` (typecheck, tests, build), `smoke` (compose end-to-end).

- [ ] **Step 1: Write the workflow**

`.github/workflows/ci.yml`:
```yaml
name: ci

on:
  push:
  pull_request:

jobs:
  backend:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_DB: assayr_test
          POSTGRES_USER: assayr
          POSTGRES_PASSWORD: assayr
        ports: ["5432:5432"]
        options: >-
          --health-cmd "pg_isready -U assayr"
          --health-interval 5s
          --health-retries 20
    defaults:
      run:
        working-directory: backend
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v6
      - run: uv sync --python 3.12 --frozen
      - run: uv run ruff check .
      - run: uv run ruff format --check .
      - name: Tests (SQLite)
        run: uv run pytest
      - name: Tests (PostgreSQL 16)
        run: uv run pytest
        env:
          ASSAYR_TEST_DATABASE_URL: postgresql+pg8000://assayr:assayr@localhost:5432/assayr_test

  frontend:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: frontend
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 24
          cache: npm
          cache-dependency-path: frontend/package-lock.json
      - run: npm ci
      - run: npm run typecheck
      - run: npm test
      - run: npm run build

  smoke:
    needs: [backend, frontend]
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: deploy/smoke.sh
```

- [ ] **Step 2: Write the README**

`README.md`:
````markdown
# Assayr

On-premise GRC for ISO/IEC 27001: keep every control, piece of evidence and risk on your own servers.
Product specs, brand and design live in the Obsidian vault at `../Assayr-Vault` (start at `00-Home/Home.md`).

## Layout

| Path | What |
|---|---|
| `backend/` | FastAPI service (`assayr` Python package), Alembic migrations, `assayr` CLI |
| `frontend/` | React + Vite single-page app, served by Caddy in production |
| `deploy/` | Docker Compose stack and smoke test |
| `docs/superpowers/plans/` | Implementation plans |

## Develop locally

Every command assumes the cache redirection script has been sourced (the dev machine's C: drive is full):

```bash
source scripts/dev-env.sh            # Git Bash
# . .\scripts\dev-env.ps1            # PowerShell
```

Backend:

```bash
cd backend
uv sync --python 3.12
cp .env.example .env
uv run assayr migrate && uv run assayr seed
uv run assayr create-admin --email you@example.com
uv run uvicorn assayr.main:create_app --factory --reload --port 8000
uv run pytest
```

Frontend (proxies `/api` to port 8000):

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173
npm test
```

## Run the full stack

Requires Docker.

```bash
cd deploy
cp assayr.env.example assayr.env      # then set POSTGRES_PASSWORD
docker compose --env-file assayr.env up -d --build --wait
docker compose --env-file assayr.env exec api assayr create-admin --email you@example.com
# open http://localhost:8080
```

`deploy/smoke.sh` runs the same steps end to end and tears the stack down.

## Administration

| Command | Purpose |
|---|---|
| `assayr migrate` | Apply database migrations |
| `assayr seed` | Load the ISO/IEC 27001:2022 catalogue (safe to repeat) |
| `assayr create-admin --email …` | Create an administrator (password from prompt or `ASSAYR_ADMIN_PASSWORD`) |
| `assayr audit-verify` | Check the audit trail's hash chain (exit code 2 if broken) |
````

- [ ] **Step 3: Verify everything locally once more**

Run: `cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && (cd backend && uv run ruff check . && uv run ruff format --check . && uv run pytest) && (cd frontend && npm run typecheck && npm test && npm run build)`
Expected: every command succeeds.

- [ ] **Step 4: Commit**

```bash
cd "E:/Work/GRC Tool/assayr" && git add -A && git commit -m "ci: backend, frontend and compose smoke jobs; add README" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

## Self-Review Notes

- **Spec coverage (Phase 0 slice):** repo/CI (Tasks 1, 15), auth + RBAC (5–7), audit trail FR-20.1–20.4 & 20.6 (4, 7, 10), catalogue FR-02.1/02.2/02.4/02.5 and FR-22-style search on controls (8, 9), design tokens and app shell per Information Architecture (11, 13), deployment skeleton per Deployment On-Prem (14). Deferred and called out in the header: LDAP/OIDC (FR-18.2/18.3), Storybook, TLS, Valkey/worker, FR-20.5 SIEM forwarding.
- **Type consistency checked:** `Grant`, `grant_for`, `permissions_for`, `record`, `Actor`, `SYSTEM`, `ensure_default_scope`, `seed_iso27001`, `summary_out`/`detail_out`, frontend `api`, `ApiError`, `useControls`/`useControl`/`useUpdateControl`/`useControlStats`, `safeNext`, `createAppRouter`, `renderApp`/`mockApi`/`json`/`ME` are defined once and used with the same signatures.
