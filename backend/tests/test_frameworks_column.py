import uuid

from sqlalchemy import create_engine, func, select, text

from assayr.catalogue.models import Control, iso_controls
from assayr.migrate import upgrade
from assayr.nia.seed import seed_nia
from tests.conftest import create_user, sign_in
from tests.test_migrations import clean, migration_url


def test_iso_controls_default_framework(db, seeded):
    assert {c.framework for c in db.scalars(select(Control))} == {"iso27001"}


def test_nia_only_controls_are_marked_nia(db, seeded):
    seed_nia(db, seeded)
    db.commit()
    nia = db.scalars(select(Control).where(Control.code.like("NIA %"))).all()
    assert nia and {c.framework for c in nia} == {"nia"}
    iso = db.scalar(select(func.count()).select_from(Control).where(iso_controls()))
    assert iso == db.scalar(select(func.count()).select_from(Control).where(~Control.code.like("NIA %")))


def test_other_frameworks_stay_out_of_iso_views(client, db, seeded):
    db.add(
        Control(scope_id=seeded.id, code="AI A.2.2", title="Invented", framework="iso42001", sort_order=999)
    )
    db.commit()
    create_user(db, "ana@acme.com")
    sign_in(client, "ana@acme.com")
    codes = [c["code"] for c in client.get("/api/v1/controls?limit=200").json()["items"]]
    assert "AI A.2.2" not in codes and len(codes) == 93
    assert client.get("/api/v1/controls/summary").json()["total"] == 93
    dash = client.get("/api/v1/dashboard").json()
    assert dash["frameworks"][0]["total"] == 93


def test_0011_backfills_framework(tmp_path):
    url = migration_url(tmp_path)
    engine = create_engine(url)
    clean(engine)
    upgrade(url, "0010")
    scope = uuid.uuid4()
    with engine.begin() as conn:
        for code in ("A.5.1", "NIA IG 1"):
            conn.execute(
                text(
                    "INSERT INTO control (id, scope_id, code, title, implementation_status, status, sort_order,"
                    " applicable, created_at, updated_at) VALUES (:id, :scope, :code, 'x', 'not_started',"
                    " 'not_started', 1, :yes, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                ),
                {"id": uuid.uuid4().hex, "scope": scope.hex, "code": code, "yes": True},
            )
    upgrade(url, "0011")
    with engine.begin() as conn:
        rows = dict(conn.execute(text("SELECT code, framework FROM control")).all())
    assert rows == {"A.5.1": "iso27001", "NIA IG 1": "nia"}
    clean(engine)
    engine.dispose()
