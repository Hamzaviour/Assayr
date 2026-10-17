from sqlalchemy import func, select

from assayr.catalogue.frameworks import control_code, display_ref, iso_map, seed_iso42001, seed_soc2
from assayr.catalogue.models import Control, iso_controls


def count(db, framework):
    return db.scalar(select(func.count()).select_from(Control).where(Control.framework == framework))


def test_codes():
    assert control_code("iso42001", "A.5.2") == "AI A.5.2" and control_code("soc2", "CC6.1") == "CC6.1"
    assert display_ref("AI A.5.2") == "A.5.2" and display_ref("CC6.1.2") == "CC6.1.2"
    assert iso_map()["AI A.2.2"] == ["A.5.1"] and "A.5.15" in iso_map()["CC6.1"]


def test_seed_creates_controls_with_prefixed_codes(db, seeded):
    a, s = seed_iso42001(db, seeded), seed_soc2(db, seeded)
    db.commit()
    assert count(db, "iso42001") == a.controls_created == 38 + 32
    assert count(db, "soc2") == s.controls_created == 33
    c = db.scalar(select(Control).where(Control.code == "AI A.6.2.4"))
    assert c.framework == "iso42001" and c.theme == "AI system life cycle" and c.slots and c.requirements
    assert c.requirements[0].attributes["iso27001"] == ["A.8.29"]
    assert db.scalar(select(Control).where(Control.code == "AI 6.1.4")).theme == "Planning"
    assert (
        db.scalar(select(Control).where(Control.code == "CC6.1")).theme
        == "Logical and physical access controls"
    )


def test_seed_is_idempotent_and_iso_unchanged(db, seeded):
    iso = db.scalar(select(func.count()).select_from(Control).where(iso_controls()))
    seed_iso42001(db, seeded)
    seed_soc2(db, seeded)
    db.commit()
    again = (seed_iso42001(db, seeded), seed_soc2(db, seeded))
    db.commit()
    assert [(r.controls_created, r.requirements_created) for r in again] == [(0, 0), (0, 0)]
    assert db.scalar(select(func.count()).select_from(Control).where(iso_controls())) == iso
