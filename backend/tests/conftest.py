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
