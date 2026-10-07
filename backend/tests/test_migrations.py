import os

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

import assayr.models  # noqa: F401  (registers every table on Base.metadata)
from assayr.audit.service import SYSTEM, record
from assayr.db import Base
from assayr.migrate import alembic_config, downgrade, upgrade

STRUCTURAL = {"add_table", "remove_table", "add_column", "remove_column"}


def migration_url(tmp_path) -> str:
    return (
        os.environ.get("ASSAYR_TEST_DATABASE_URL") or f"sqlite+pysqlite:///{(tmp_path / 'm.db').as_posix()}"
    )


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


@pytest.mark.skipif(
    not os.environ.get("ASSAYR_TEST_DATABASE_URL", "").startswith("postgresql"),
    reason="PostgreSQL-only trigger",
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
