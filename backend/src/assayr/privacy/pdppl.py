"""PDPPL obligations (our own summaries) and how well the organisation's records evidence each one."""

import json
import uuid
from datetime import date
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from assayr.assets.models import Asset
from assayr.catalogue.models import Control
from assayr.documents.models import Document
from assayr.identity.models import RoleAssignment, User
from assayr.nia.service import derive_status
from assayr.privacy.breaches import notification_overdue
from assayr.privacy.categories import SENSITIVE
from assayr.privacy.dpia import dpia_recommended
from assayr.privacy.models import Breach, Dpia, ProcessingActivity, Processor, SubjectRequest
from assayr.training.models import Course

PDPPL_FILE = Path(__file__).resolve().parents[1] / "catalogue" / "data" / "pdppl.json"
DATA = json.loads(PDPPL_FILE.read_text(encoding="utf-8"))
OBLIGATIONS: list[dict] = DATA["obligations"]
RANK = {"na": 0, "met": 1, "partial": 2, "missing": 3}


class Facts:
    """Everything the evidence checks need, loaded once per evaluation."""

    def __init__(self, db: Session, scope_id: uuid.UUID, now):
        self.today: date = now.date()
        self.now = now
        self.activities = list(
            db.scalars(select(ProcessingActivity).where(ProcessingActivity.scope_id == scope_id)).unique()
        )
        self.active = [a for a in self.activities if a.status == "active"]
        self.dpias = {
            d.activity_id: d
            for d in db.scalars(select(Dpia)).unique()
            if d.activity_id in {a.id for a in self.activities}
        }
        self.requests = list(db.scalars(select(SubjectRequest).where(SubjectRequest.scope_id == scope_id)))
        self.breaches = list(db.scalars(select(Breach).where(Breach.scope_id == scope_id)))
        self.processors = [
            p
            for p in db.scalars(select(Processor).where(Processor.scope_id == scope_id)).unique()
            if p.status == "active"
        ]
        self.documents = list(db.scalars(select(Document).where(Document.scope_id == scope_id)).unique())
        self.pii_assets = db.scalar(
            select(func.count())
            .select_from(Asset)
            .where(Asset.scope_id == scope_id, Asset.holds_pii.is_(True))
        )
        self.courses = db.scalar(
            select(func.count())
            .select_from(Course)
            .where(Course.scope_id == scope_id, Course.status == "published")
        )
        self.officers = db.scalar(
            select(func.count())
            .select_from(RoleAssignment)
            .join(User, RoleAssignment.user_id == User.id)
            .where(RoleAssignment.role == "privacy_officer", User.is_active.is_(True))
        )
        self.controls = {c.code: c for c in db.scalars(select(Control).where(Control.scope_id == scope_id))}

    def approved_dpia(self, a: ProcessingActivity) -> bool:
        d = self.dpias.get(a.id)
        return d is not None and d.status == "approved"


def _share(items: list, ok, what: str) -> tuple[str, str]:
    if not items:
        return "na", f"No {what}."
    good = [i for i in items if ok(i)]
    if len(good) == len(items):
        return "met", f"All {len(items)} {what} are covered."
    names = ", ".join(getattr(i, "name", str(i)) for i in items if not ok(i))[:200]
    return ("partial" if good else "missing"), f"Not yet covered: {names}."


def check(kind: str, f: Facts) -> tuple[str, str]:
    if kind == "records":
        return (
            ("met", f"{len(f.active)} active processing activities.")
            if f.active
            else ("missing", "No active processing activity is recorded.")
        )
    if kind == "inventory":
        return (
            ("met", f"{f.pii_assets} assets hold personal data.")
            if f.pii_assets
            else ("missing", "No asset is marked as holding personal data.")
        )
    if kind == "retention":
        return _share(
            f.active,
            lambda a: bool(a.retention) and not (a.retention_review_due and a.retention_review_due < f.today),
            "active activities with a retention period",
        )
    if kind == "consent":
        consent = [a for a in f.active if a.lawful_basis == "consent"]
        return _share(
            consent, lambda a: bool(a.consent_how) and bool(a.consent_withdrawal), "consent-based activities"
        )
    if kind == "notice":
        found = [
            d
            for d in f.documents
            if d.doc_type == "policy" and d.status == "approved" and "privacy" in d.title.lower()
        ]
        return (
            ("met", f"Approved: {found[0].code} {found[0].title}.")
            if found
            else ("missing", "Approve a privacy policy or notice in Policies.")
        )
    if kind == "requests":
        overdue = [r for r in f.requests if r.status != "closed" and r.due_on < f.today]
        if overdue:
            return "missing", f"{len(overdue)} request(s) overdue: {', '.join(r.code for r in overdue[:5])}."
        procedure = any(d.doc_type == "procedure" and "request" in d.title.lower() for d in f.documents)
        if f.requests or procedure:
            return "met", "Requests are logged and none is overdue."
        return "partial", "No request has been logged and no request procedure is linked yet."
    if kind == "breaches":
        late = [b for b in f.breaches if notification_overdue(b, f.now)]
        if late:
            return "missing", f"Notification overdue for {', '.join(b.code for b in late[:5])}."
        uncontained = [b for b in f.breaches if b.status == "open" and not b.containment]
        if uncontained:
            return "partial", f"No containment recorded for {', '.join(b.code for b in uncontained[:5])}."
        return "met", "No overdue breach notifications."
    if kind == "training":
        return (
            ("met", f"{f.courses} published training course(s).")
            if f.courses
            else ("missing", "Publish a privacy awareness course in Training.")
        )
    if kind == "sensitive":
        items = [a for a in f.active if SENSITIVE & set(a.data_categories or [])]
        return _share(items, f.approved_dpia, "activities with sensitive data and an approved DPIA")
    if kind == "dpia":
        items = [
            a for a in f.activities if a.id in f.dpias and dpia_recommended(f.dpias[a.id].screening or {})
        ]
        return _share(items, f.approved_dpia, "activities where a DPIA is recommended")
    if kind == "children":
        items = [
            a
            for a in f.active
            if "children" in (a.data_categories or []) or "children" in (a.data_subjects or [])
        ]
        return _share(items, f.approved_dpia, "activities with children's data and an approved DPIA")
    if kind == "cross_border":
        items = [a for a in f.active if a.cross_border]
        return _share(items, lambda a: bool(a.transfer_countries), "transfers with destination countries")
    if kind == "processors":
        return _share(f.processors, lambda p: p.dpa_signed, "active processors with a signed agreement")
    if kind == "privacy_officer":
        return (
            ("met", "A privacy officer is assigned.")
            if f.officers
            else ("missing", "Give someone the Privacy officer role in Users.")
        )
    return "na", ""


def evaluate(db: Session, scope_id: uuid.UUID, now) -> list[dict]:
    f = Facts(db, scope_id, now)
    rows = []
    for o in OBLIGATIONS:
        results = [check(kind, f) for kind in o["evidence"]]
        result, reason = (
            max(results, key=lambda r: RANK[r[0]]) if results else ("na", "Shown by the mapped controls.")
        )
        mapped = [f.controls[c] for c in o["iso"] if c in f.controls]
        counted = [c for c in mapped if c.status != "excluded"]
        iso_status = derive_status([c.status for c in counted]) if counted else "not_started"
        if result == "missing":
            final = "at_risk"
        elif result == "partial" and iso_status == "compliant":
            final = "in_progress"
        else:
            final = iso_status
        rows.append(
            {
                **{k: o[k] for k in ("ref", "topic", "title", "summary")},
                "iso": [{"code": c.code, "title": c.title, "status": c.status} for c in mapped],
                "evidence": {"result": result, "reason": reason},
                "status": final,
            }
        )
    return rows


def framework_row(db: Session, scope_id: uuid.UUID, now) -> dict:
    rows = evaluate(db, scope_id, now)
    counts: dict[str, int] = {}
    for r in rows:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    groups: dict[str, list[dict]] = {}
    for r in rows:
        groups.setdefault(r["topic"], []).append(r)
    compliant = counts.get("compliant", 0)
    return {
        "code": DATA["code"],
        "name": DATA["name"],
        "version": DATA["version"],
        "total": len(rows),
        "compliant": compliant,
        "readiness": round(100 * compliant / len(rows), 1) if rows else None,
        "status_counts": counts,
        "excluded": 0,
        "groups": [
            {
                "name": topic,
                "code": None,
                "total": len(items),
                "compliant": sum(1 for i in items if i["status"] == "compliant"),
                "readiness": round(100 * sum(1 for i in items if i["status"] == "compliant") / len(items), 1),
            }
            for topic, items in groups.items()
        ],
    }
