import os
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from assayr.catalogue.seed import ensure_default_scope, seed_iso27001
from assayr.config import Settings
from assayr.db import Base, utcnow
from assayr.identity.models import RoleAssignment, User
from assayr.identity.security import hash_password, normalize_email
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
def seeded(db, settings):
    scope = ensure_default_scope(db, settings.org_name)
    seed_iso27001(db, scope)
    db.commit()
    return scope


@pytest.fixture
def clock(app) -> FakeClock:
    fake = FakeClock()
    app.state.clock = fake
    return fake


PASSWORD = "correct-horse-battery"


def create_user(
    db, email, password=PASSWORD, roles=(("isms_manager", None),), full_name="Test User", active=True
):
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
