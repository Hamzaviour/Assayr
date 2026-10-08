"""Build risks through the API in tests."""


def new_risk(client, **body) -> dict:
    payload = {"title": "Test risk", **body}
    response = client.post("/api/v1/risks", json=payload)
    assert response.status_code == 201, response.text
    return response.json()
