from importlib.metadata import version


def test_healthz_reports_ok_and_version(client):
    response = client.get("/api/v1/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": version("assayr")}


def test_request_id_is_echoed_and_sanitised(client):
    response = client.get("/api/v1/healthz", headers={"X-Request-Id": "abc-123<script>"})
    assert response.headers["X-Request-Id"] == "abc-123script"


def test_request_id_generated_when_missing(client):
    response = client.get("/api/v1/healthz")
    assert len(response.headers["X-Request-Id"]) == 32
