import pytest
from sqlalchemy import select

from assayr.catalogue.models import Control
from assayr.nia.seed import seed_nia
from assayr.nia.service import derive_status, nia_framework_row, nia_views, set_applicability


@pytest.mark.parametrize(
    ("statuses", "expected"),
    [
        (["compliant", "compliant"], "compliant"),
        (["compliant", "non_compliant"], "non_compliant"),
        (["compliant", "in_progress"], "in_progress"),
        (["at_risk", "in_review"], "in_review"),
        ([], "not_started"),
    ],
)
def test_derive_status(statuses, expected):
    assert derive_status(statuses) == expected


@pytest.fixture
def nia(db, seeded):
    seed_nia(db, seeded)
    db.commit()
    return seeded


def control(db, code):
    return db.scalar(select(Control).where(Control.code == code))


def view(db, scope, ref):
    return next(v for v in nia_views(db, scope.id) if v.ref == ref)


def test_status_and_score_follow_the_mapped_iso_controls(db, nia):
    # PS 8 maps to A.5.15 and A.8.3
    for code, status, score in (("A.5.15", "compliant", 100.0), ("A.8.3", "in_progress", 40.0)):
        c = control(db, code)
        c.status, c.score = status, score
    db.commit()
    v = view(db, nia, "PS 8")
    assert v.status == "in_progress" and v.score == 70.0
    assert sorted(c.code for c in v.mapped) == ["A.5.15", "A.8.3"]


def test_excluded_iso_controls_are_ignored(db, nia):
    a515, a83 = control(db, "A.5.15"), control(db, "A.8.3")
    a515.status, a515.score = "compliant", 100.0
    a83.status = "excluded"
    db.commit()
    assert view(db, nia, "PS 8").status == "compliant"
    a515.status = "excluded"
    db.commit()
    assert view(db, nia, "PS 8").status == "not_started"


def test_nia_only_controls_use_their_own_status(db, nia):
    own = control(db, "NIA RM 1")
    own.status, own.score = "compliant", 100.0
    db.commit()
    assert view(db, nia, "RM 1").status == "compliant"


def test_framework_row_counts_applicable_controls_by_domain(db, nia):
    row = nia_framework_row(db, nia.id, has_evidence=False)
    assert row["name"] == "NIA" and row["version"] == "2.1"
    assert row["total"] == 355 and row["readiness"] is None and row["excluded"] == 0
    assert [g["name"] for g in row["groups"]][:2] == ["Security Governance", "Risk Management"]
    assert sum(g["total"] for g in row["groups"]) == 355
    set_applicability(db, nia.id, "CS 11", applicable=False, reason="We do not use fax", by="sana@acme.com")
    db.commit()
    row = nia_framework_row(db, nia.id, has_evidence=True)
    assert row["total"] == 354 and row["excluded"] == 1 and row["readiness"] is not None
    assert view(db, nia, "CS 11").applicable is False
