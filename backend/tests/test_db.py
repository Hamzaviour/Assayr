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
    user = User(
        email="a@acme.com", full_name="A", role_assignments=[RoleAssignment(role="viewer", scope_id=scope.id)]
    )
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
