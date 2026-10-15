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
    url = (
        os.environ.get("ASSAYR_TEST_DATABASE_URL") or f"sqlite+pysqlite:///{(tmp_path / 'cli.db').as_posix()}"
    )
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
    result = run(
        "create-admin", "--email", "env@acme.com", env={"ASSAYR_ADMIN_PASSWORD": "from-the-environment"}
    )
    assert result.exit_code == 0, result.output


def test_create_admin_refuses_duplicates_and_weak_passwords(cli_db):
    run("migrate")
    run("create-admin", "--email", "admin@acme.com", "--password", "a-very-long-password")
    duplicate = run("create-admin", "--email", "ADMIN@acme.com", "--password", "a-very-long-password")
    assert duplicate.exit_code == 1 and "already exists" in duplicate.output
    weak = run("create-admin", "--email", "new@acme.com", "--password", "short")
    assert weak.exit_code == 1 and "Use at least 12 characters." in weak.output


def test_worker_once_processes_queued_jobs(cli_db, monkeypatch):
    from assayr.db import utcnow
    from assayr.jobs import HANDLERS, enqueue

    run("migrate")
    seen = []
    monkeypatch.setitem(HANDLERS, "test.echo", lambda session, payload, env: seen.append(payload))
    with Session(cli_db) as session:
        enqueue(session, "test.echo", {"n": 7}, now=utcnow())
        session.commit()
    result = run("worker", "--once")
    assert result.exit_code == 0 and "Processed 1 job." in result.output
    assert seen == [{"n": 7}]


def test_seed_loads_the_risk_library(cli_db):
    run("migrate")
    first = run("seed")
    assert first.exit_code == 0
    assert "Risk library: 40 threats, 60 vulnerabilities and 25 templates added." in first.output
    assert "Risk library: 0 threats, 0 vulnerabilities and 0 templates added." in run("seed").output


def test_create_admin_if_no_admin_skips_when_one_exists(cli_db):
    run("migrate")
    first = run(
        "create-admin", "--email", "a@acme.com", "--if-no-admin", "--password", "a-very-long-password"
    )
    assert first.exit_code == 0, first.output
    second = run(
        "create-admin", "--email", "b@acme.com", "--if-no-admin", "--password", "a-very-long-password"
    )
    assert second.exit_code == 0 and "already exists" in second.output
    with Session(cli_db) as session:
        assert [u.email for u in session.scalars(select(User))] == ["a@acme.com"]
