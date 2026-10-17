"""Raising findings from audit rows, their derived status, and who may do what."""

import uuid
from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from assayr.audits.models import Audit, AuditItem
from assayr.catalogue.access import has_perm
from assayr.catalogue.models import Control
from assayr.findings.models import Finding
from assayr.identity.models import User
from assayr.identity.rbac import Perm

RAISABLE = {"fail": ("major", "Fail"), "partial": ("minor", "Partial"), "exception": ("minor", "Exception")}
DUE_DAYS = {"major": 30, "minor": 90, "observation": 180, "ofi": 180}
NOT_RAISABLE = "Only fail, partial or exception results can be raised as findings."


def control_code(framework: str, ref: str) -> str:
    return f"AI {ref}" if framework == "iso42001" else f"NIA {ref}" if framework == "nia-2.1" else ref


def control_owner(db: Session, scope_id: uuid.UUID, framework: str, ref: str) -> uuid.UUID | None:
    return db.scalar(
        select(Control.owner_id).where(
            Control.scope_id == scope_id, Control.code == control_code(framework, ref)
        )
    )


def next_code(db: Session, scope_id: uuid.UUID) -> tuple[int, str]:
    seq = (db.scalar(select(func.max(Finding.seq)).where(Finding.scope_id == scope_id)) or 0) + 1
    return seq, f"F-{seq:03d}"


def raise_from_item(
    db: Session, audit: Audit, item: AuditItem, user: User, now: datetime, **overrides
) -> tuple[Finding, bool]:
    """The finding for this audit row, creating it with the defaults for its result. Returns (finding, created)."""
    existing = db.scalar(select(Finding).where(Finding.audit_item_id == item.id))
    if existing is not None:
        return existing, False
    if item.result not in RAISABLE:
        raise ValueError(NOT_RAISABLE)
    default_grade, label = RAISABLE[item.result]
    grade = overrides.get("grade") or default_grade
    seq, code = next_code(db, audit.scope_id)
    owner = (
        overrides["owner_id"]
        if "owner_id" in overrides
        else control_owner(db, audit.scope_id, audit.framework, item.ref)
    )
    finding = Finding(
        scope_id=audit.scope_id,
        code=code,
        seq=seq,
        title=overrides.get("title") or f"{item.ref}: {label}",
        description=overrides.get("description") or item.exception_note or item.notes,
        grade=grade,
        source="internal_audit",
        audit_id=audit.id,
        audit_item_id=item.id,
        framework=audit.framework,
        ref=item.ref,
        owner_id=owner,
        due_date=overrides.get("due_date") or now.date() + timedelta(days=DUE_DAYS[grade]),
        root_cause=overrides.get("root_cause"),
        raised_by_id=user.id,
        raised_at=now,
    )
    try:
        with db.begin_nested():
            db.add(finding)
            db.flush()
    except IntegrityError:
        # Someone raised the same row at the same moment: theirs wins.
        return db.scalar(select(Finding).where(Finding.audit_item_id == item.id)), False
    refresh_status(finding)
    return finding, True


def _needs_new_work(f: Finding) -> bool:
    """After a 'not effective' verdict, the finding waits until an action is added, reopened or done again."""
    if not f.verifications or f.verifications[-1].effective:
        return False
    last = f.verifications[-1].verified_at
    return not any(a.status == "open" or (a.done_at and a.done_at > last) for a in f.actions)


def refresh_status(f: Finding) -> None:
    """Status follows the work: root cause and actions plan it; every action done waits for verification."""
    if f.status == "closed":
        return
    if not f.is_nonconformity:
        f.status = "open"
        return
    if not (f.root_cause or "").strip() or not f.actions:
        f.status = "open"
    elif all(a.status == "done" for a in f.actions) and not _needs_new_work(f):
        f.status = "awaiting_verification"
    else:
        f.status = "action_planned"


def is_overdue(due: date | None, done: bool, today: date) -> bool:
    return due is not None and not done and due < today


def can_manage(user: User, scope_id: uuid.UUID) -> bool:
    return has_perm(user, scope_id, Perm.FINDINGS_MANAGE)


def can_edit_capa(user: User, f: Finding) -> bool:
    return f.status != "closed" and (can_manage(user, f.scope_id) or f.owner_id == user.id)


def verify_problem(user: User, f: Finding) -> tuple[int, str] | None:
    """Why this person can not verify this finding now (HTTP status, message), or None."""
    if not has_perm(user, f.scope_id, Perm.FINDINGS_VERIFY):
        return 403, "Only an ISMS manager or internal auditor can verify findings."
    if user.id == f.owner_id or any(a.owner_id == user.id for a in f.actions):
        return 403, "Someone who did not own this finding or its actions must verify it."
    if not f.is_nonconformity:
        return 409, "Observations and opportunities for improvement close with a response."
    still_open = sum(1 for a in f.actions if a.status == "open")
    if still_open:
        noun = "corrective action is" if still_open == 1 else "corrective actions are"
        return 409, f"{still_open} {noun} still open."
    if f.status != "awaiting_verification":
        return 409, "Record the root cause and complete the corrective actions first."
    return None
