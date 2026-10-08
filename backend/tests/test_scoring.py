from datetime import date, timedelta

import pytest
from sqlalchemy import func, select

from assayr.catalogue.models import Control
from assayr.db import utcnow
from assayr.scoring.models import Attestation, ScoreSnapshot, StatusTransition
from assayr.scoring.service import (
    SlotView,
    evaluate,
    freshness_state,
    recompute_control,
    recompute_scope,
    slot_views,
    take_snapshot,
    weighted_readiness,
)
from tests.evidence_helpers import add_link

TODAY = date(2026, 10, 7)


@pytest.mark.parametrize(
    "days_left,expected",
    [
        (None, "verified"),
        (31, "verified"),
        (30, "expiring"),
        (1, "expiring"),
        (0, "expired_grace"),
        (-13, "expired_grace"),
        (-14, "expired"),
    ],
)
def test_freshness_state(days_left, expected):
    expires = None if days_left is None else TODAY + timedelta(days=days_left)
    assert freshness_state(expires, TODAY, warning_days=30, grace_days=14) == expected


def views(*states, required=True):
    return [SlotView(slot_id=None, required=required, state=s, link=None) for s in states]


def test_evaluate_status_and_score():
    assert evaluate("implemented", views("verified", "verified"), True, True)[:2] == ("compliant", 100.0)
    assert evaluate("implemented", views("verified", "verified"), False, True)[:2] == ("at_risk", 90.0)
    assert evaluate("implemented", views("verified", "expiring"), True, True)[:2] == ("at_risk", 90.0)
    assert evaluate("implemented", views("verified", "pending"), True, True).status == "in_review"
    assert evaluate("implemented", views("verified", "missing"), True, True).status == "in_progress"
    assert evaluate("implemented", views("verified", "rejected"), True, True).status == "in_progress"
    expired = evaluate("implemented", views("verified", "verified", "expired"), True, True)
    assert (expired.status, expired.score) == ("non_compliant", 40.0)
    assert evaluate("not_started", views("missing", "missing"), False, False)[:2] == ("not_started", 0.0)
    assert evaluate("planned", views("missing"), False, False).status == "in_progress"


def test_optional_slots_do_not_count():
    result = evaluate("implemented", views("verified") + views("missing", required=False), True, True)
    assert result.status == "compliant"


def control_with_slots(db, code="A.8.13"):
    return db.scalar(select(Control).where(Control.code == code))


def test_slot_views_pick_the_newest_accepted_evidence(db, seeded, app, settings):
    control = control_with_slots(db)
    slot = control.slots[0]
    add_link(db, app.state.store, slot, scope_id=seeded.id, evidence_date=TODAY - timedelta(days=400))
    newest = add_link(db, app.state.store, slot, scope_id=seeded.id, evidence_date=TODAY - timedelta(days=2))
    add_link(db, app.state.store, control.slots[1], scope_id=seeded.id, state="in_review")
    db.commit()
    by_slot = {v.slot_id: v for v in slot_views(db, control, TODAY, settings)}
    assert by_slot[slot.id].state == "verified" and by_slot[slot.id].link.id == newest.id
    assert by_slot[control.slots[1].id].state == "pending"
    assert by_slot[control.slots[2].id].state == "missing"


def test_recompute_records_a_transition_only_when_status_changes(db, seeded, app, settings):
    control = control_with_slots(db)
    now = utcnow()
    add_link(db, app.state.store, control.slots[0], scope_id=seeded.id, evidence_date=now.date())
    result = recompute_control(db, control, now, settings, trigger="Evidence accepted: backup.pdf")
    db.commit()
    assert result.status == "in_progress" and control.status == "in_progress"
    # One of three slots verified: (1 + 0 + 0) / 3 × 100 × 0.9 (not attested) = 30.0
    assert control.score == pytest.approx(30.0)
    recompute_control(db, control, now, settings, trigger="Again")
    db.commit()
    transitions = list(db.scalars(select(StatusTransition)))
    assert [(t.from_status, t.to_status, t.trigger) for t in transitions] == [
        ("not_started", "in_progress", "Evidence accepted: backup.pdf")
    ]


def test_full_evidence_and_attestation_make_a_control_compliant(db, seeded, app, settings):
    now = utcnow()
    control = control_with_slots(db)
    for slot in control.slots:
        add_link(db, app.state.store, slot, scope_id=seeded.id, evidence_date=now.date())
    db.add(
        Attestation(
            control_id=control.id,
            statement="Operates as described.",
            attested_at=now,
            valid_until=now + timedelta(days=31),
        )
    )
    result = recompute_control(db, control, now, settings, trigger="test")
    assert (result.status, result.score) == ("compliant", 100.0)


def test_readiness_and_daily_snapshots(db, seeded, app, settings):
    now = utcnow()
    control = control_with_slots(db)
    add_link(db, app.state.store, control.slots[0], scope_id=seeded.id, evidence_date=now.date())
    recompute_scope(db, seeded.id, now, settings)
    db.commit()
    controls = list(db.scalars(select(Control).where(Control.scope_id == seeded.id)))
    assert weighted_readiness(controls) == pytest.approx(round(control.score / 93, 1), abs=0.1)
    assert db.scalar(select(func.count()).select_from(ScoreSnapshot)) == 1
    assert take_snapshot(db, seeded.id, now) is None
    assert db.scalar(select(func.count()).select_from(ScoreSnapshot)) == 1


def test_readiness_is_none_without_controls():
    assert weighted_readiness([]) is None
