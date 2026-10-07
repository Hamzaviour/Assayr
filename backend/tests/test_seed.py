from sqlalchemy import func, select

from assayr.catalogue.models import Control, Requirement
from assayr.catalogue.seed import ensure_default_scope, seed_iso27001
from assayr.identity.models import Organization


def count(db, model, *where):
    return db.scalar(select(func.count()).select_from(model).where(*where))


def test_seed_creates_clauses_themes_and_all_93_controls(db, seeded):
    assert count(db, Requirement, Requirement.kind.in_(["clause_group", "clause"])) == 41
    assert count(db, Requirement, Requirement.kind == "theme") == 4
    assert count(db, Requirement, Requirement.kind == "annex_control") == 93
    assert count(db, Control, Control.scope_id == seeded.id) == 93


def test_controls_carry_slots_rules_and_freshness(db, seeded):
    db.expunge_all()
    backup = db.scalar(select(Control).where(Control.code == "A.8.13"))
    assert backup.title == "Information backup"
    assert backup.theme == "Technological"
    assert backup.status == "not_started"
    assert [s.name for s in backup.slots] == [
        "Backup policy",
        "Backup job success report",
        "Restore test record",
    ]
    assert all(s.freshness_days == 31 for s in backup.slots)
    assert "V-FRESH" in backup.slots[0].rules
    assert [r.ref for r in backup.requirements] == ["A.8.13"]


def test_controls_are_in_natural_order(db, seeded):
    codes = list(db.scalars(select(Control.code).order_by(Control.sort_order).limit(11)))
    assert codes[:3] == ["A.5.1", "A.5.2", "A.5.3"]
    assert codes[9] == "A.5.10"


def test_seed_is_idempotent_and_preserves_edits(db, seeded, settings):
    control = db.scalar(select(Control).where(Control.code == "A.5.1"))
    control.implementation_status = "implemented"
    control.implementation_text = "Approved by the board in January."
    db.commit()
    again = seed_iso27001(db, ensure_default_scope(db, settings.org_name))
    db.commit()
    assert (again.framework_created, again.requirements_created, again.controls_created) == (False, 0, 0)
    assert count(db, Control) == 93
    db.expunge_all()
    reloaded = db.scalar(select(Control).where(Control.code == "A.5.1"))
    assert reloaded.implementation_status == "implemented"
    assert reloaded.implementation_text == "Approved by the board in January."


def test_default_scope_is_created_once_with_the_configured_name(db, settings):
    first = ensure_default_scope(db, settings.org_name)
    second = ensure_default_scope(db, "Something else")
    db.commit()
    assert first.id == second.id
    assert db.scalar(select(Organization.name)) == "Acme Financial Services"
