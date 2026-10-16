from sqlalchemy import select

from assayr.identity.models import User
from tests.conftest import PASSWORD, create_user, sign_in

NEW = "a-much-better-passphrase"


def gated(client, db):
    user = create_user(db, "omar@acme.com", roles=(("employee", None),), full_name="Omar Ali")
    user.must_change_password = True
    db.commit()
    sign_in(client, "omar@acme.com")
    return user


def test_a_temporary_password_blocks_everything_but_changing_it(client, db, seeded):
    gated(client, db)
    assert client.get("/api/v1/auth/me").status_code == 200
    blocked = client.get("/api/v1/controls")
    assert blocked.status_code == 403 and blocked.json()["detail"] == "Change your temporary password first."


def test_changing_the_password(client, db, seeded):
    user = gated(client, db)
    url = "/api/v1/auth/password"
    assert client.post(url, json={"current_password": "wrong", "new_password": NEW}).status_code == 422
    assert client.post(url, json={"current_password": PASSWORD, "new_password": "short"}).status_code == 422
    assert client.post(url, json={"current_password": PASSWORD, "new_password": NEW}).status_code == 204
    db.refresh(user)
    assert user.must_change_password is False
    assert client.get("/api/v1/auth/me").json()["must_change_password"] is False
    assert client.get("/api/v1/controls").json()["detail"] != "Change your temporary password first."
    client.cookies.clear()
    client.headers.pop("X-CSRF-Token", None)
    assert sign_in(client, "omar@acme.com", NEW).status_code == 200


def test_any_user_can_change_their_own_password(client, db, seeded):
    create_user(db, "sana@acme.com", full_name="Sana")
    sign_in(client, "sana@acme.com")
    assert (
        client.post(
            "/api/v1/auth/password", json={"current_password": PASSWORD, "new_password": NEW}
        ).status_code
        == 204
    )
    assert db.scalar(select(User).where(User.email == "sana@acme.com")).must_change_password is False
