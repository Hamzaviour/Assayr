"""Build risks through the API in tests."""


def new_risk(client, **body) -> dict:
    payload = {"title": "Test risk", **body}
    response = client.post("/api/v1/risks", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


DIMENSIONS = ("financial", "operational", "legal", "reputation", "data")


def ratings(level: int, **overrides: int) -> dict:
    values = {key: level for key in DIMENSIONS}
    values.update(overrides)
    return values


def assessed_risk(
    client, *, likelihood: int, consequence: int, title: str = "Test risk", owner_id=None
) -> dict:
    """A risk with one finalized assessment and no controls, so current = target = inherent."""
    body = {"title": title}
    if owner_id is not None:
        body["owner_id"] = str(owner_id)
    code = new_risk(client, **body)["code"]
    response = client.patch(
        f"/api/v1/risks/{code}/assessment",
        json={"likelihood": likelihood, "consequence": ratings(consequence)},
    )
    assert response.status_code == 200, response.text
    response = client.post(f"/api/v1/risks/{code}/assessment/finalize")
    assert response.status_code == 200, response.text
    return response.json()
