from assayr.catalogue.access import has_perm, rights_for
from assayr.identity.rbac import Perm
from tests.conftest import create_user, sign_in


def test_people_lists_active_users_for_owner_pickers(client, db):
    create_user(db, "sana@acme.com", full_name="Sana Malik")
    create_user(db, "bilal@acme.com", roles=(("risk_owner", None),), full_name="Bilal Khan")
    create_user(db, "gone@acme.com", full_name="Gone User", active=False)
    sign_in(client, "sana@acme.com")
    body = client.get("/api/v1/people").json()
    assert [(p["full_name"], p["roles"]) for p in body] == [
        ("Bilal Khan", ["risk_owner"]),
        ("Sana Malik", ["isms_manager"]),
    ]


def test_people_needs_a_reading_role(client, db):
    create_user(db, "emp@acme.com", roles=(("employee", None),))
    sign_in(client, "emp@acme.com")
    assert client.get("/api/v1/people").status_code == 403


def test_rights_for_owner_and_manager(db, seeded):
    manager = create_user(db, "sana@acme.com")
    owner = create_user(db, "bilal@acme.com", roles=(("risk_owner", None),))
    mine = rights_for(owner, seeded.id, owner.id, Perm.RISKS_WRITE, Perm.RISKS_WRITE_OWN)
    theirs = rights_for(owner, seeded.id, manager.id, Perm.RISKS_WRITE, Perm.RISKS_WRITE_OWN)
    assert (mine.all, mine.own, theirs.any) == (False, True, False)
    assert rights_for(manager, seeded.id, None, Perm.RISKS_WRITE, Perm.RISKS_WRITE_OWN).all
    assert has_perm(manager, seeded.id, Perm.SOA_WRITE) and not has_perm(owner, seeded.id, Perm.SOA_WRITE)
