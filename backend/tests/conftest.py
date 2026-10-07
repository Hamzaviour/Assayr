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
