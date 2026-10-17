"""The daily summary: what is overdue, due this week or coming up for each person, sent once a day."""

import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from html import escape

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from assayr.ai.models import AiImpactAssessment, AiSystem
from assayr.catalogue.models import Control, EvidenceSlot
from assayr.documents.models import Document
from assayr.evidence.models import ArtefactLink
from assayr.findings.models import Finding
from assayr.identity.models import User
from assayr.identity.rbac import Perm, grant_for
from assayr.mail.crypto import password_of
from assayr.mail.models import MailLog, MailSettings
from assayr.mail.sender import Connection, MailError, Outgoing
from assayr.privacy.models import Breach, Dpia, ProcessingActivity, SubjectRequest
from assayr.risk.models import Risk
from assayr.training.models import Assignment

WEEK = 7
UPCOMING = 30
SECTIONS = (("overdue", "Overdue"), ("week", "Due in the next 7 days"), ("upcoming", "Coming up"))
DOC_LABEL = {"policy": "Policy", "procedure": "Procedure", "guideline": "Guideline"}


@dataclass(frozen=True)
class Item:
    section: str
    title: str
    due: date | None
    path: str


def _section(due: date | None, today: date, reaches: int = WEEK) -> str | None:
    """Which part of the summary a due date belongs to, or None when it is not close enough yet."""
    if due is None:
        return None
    if due < today:
        return "overdue"
    if due <= today + timedelta(days=WEEK):
        return "week"
    if due <= today + timedelta(days=reaches):
        return "upcoming"
    return None


class _Collector:
    def __init__(self, today: date) -> None:
        self.today = today
        self.items: dict[uuid.UUID, list[Item]] = defaultdict(list)

    def add(
        self,
        user_id,
        title: str,
        due: date | None,
        path: str,
        reaches: int = WEEK,
        section: str | None = None,
    ):
        section = section or _section(due, self.today, reaches)
        if user_id is not None and section is not None:
            self.items[user_id].append(Item(section, title, due, path))


def _holders(users: list[User], perm: Perm, scope_id: uuid.UUID) -> list[User]:
    return [
        u
        for u in users
        if grant_for(((a.role, a.scope_id) for a in u.role_assignments), perm).allows(scope_id)
    ]


def collect(db: Session, today: date) -> dict[uuid.UUID, list[Item]]:
    """Every person's items from findings, evidence, documents, training, risks, privacy and AI."""
    c = _Collector(today)
    users = list(db.scalars(select(User).where(User.is_active.is_(True))))

    for f in db.scalars(select(Finding).where(Finding.status != "closed")).unique():
        c.add(f.owner_id, f"Finding {f.code}: {f.title}", f.due_date, f"/findings/{f.id}")
        for a in f.actions:
            if a.status == "open":
                c.add(
                    a.owner_id,
                    f"Corrective action {f.code} #{a.seq}: {a.description}",
                    a.due_date,
                    f"/findings/{f.id}",
                )
        if f.status == "awaiting_verification":
            doers = {f.owner_id, *(a.owner_id for a in f.actions)}
            for u in _holders(users, Perm.FINDINGS_VERIFY, f.scope_id):
                if u.id not in doers:
                    c.add(
                        u.id, f"Verify finding {f.code}: {f.title}", None, f"/findings/{f.id}", section="week"
                    )

    latest: dict[uuid.UUID, ArtefactLink] = {}
    for link in db.scalars(select(ArtefactLink).where(ArtefactLink.state == "accepted")):
        if link.slot_id not in latest or link.created_at > latest[link.slot_id].created_at:
            latest[link.slot_id] = link
    for link in latest.values():
        slot = db.get(EvidenceSlot, link.slot_id)
        control = db.get(Control, slot.control_id) if slot and slot.control_id else None
        if control is not None:
            title = f"Evidence expires for {control.code}: {link.version.artefact.title}"
            c.add(control.owner_id, title, link.expires_on, f"/controls/{control.code}", UPCOMING)

    for d in db.scalars(select(Document).where(Document.status == "approved")):
        label = DOC_LABEL.get(d.doc_type, "Document")
        c.add(d.owner_id, f"{label} {d.code} review: {d.title}", d.review_due, f"/policies/{d.id}", UPCOMING)

    for a in db.scalars(select(Assignment).where(Assignment.status != "passed")):
        c.add(a.user_id, f"Training: {a.course.title}", a.due_at, f"/my-training/{a.course_id}")

    for r in db.scalars(select(Risk).where(Risk.closed_at.is_(None))):
        c.add(r.owner_id, f"Risk {r.code} treatment: {r.title}", r.treatment_due, f"/risks/{r.code}")
        c.add(r.owner_id, f"Risk {r.code} review: {r.title}", r.review_due, f"/risks/{r.code}", UPCOMING)

    privacy: dict[uuid.UUID, list[User]] = {}

    def officers(scope_id: uuid.UUID) -> list[User]:
        if scope_id not in privacy:
            privacy[scope_id] = _holders(users, Perm.PRIVACY_MANAGE, scope_id)
        return privacy[scope_id]

    for q in db.scalars(select(SubjectRequest).where(SubjectRequest.status != "closed")):
        for u in officers(q.scope_id):
            title = f"Data subject request {q.code} ({q.type}) from {q.requester_name}"
            c.add(u.id, title, q.due_on, f"/privacy/requests/{q.id}")
    soon = datetime.combine(today, time.min, tzinfo=UTC) + timedelta(hours=72)
    for b in db.scalars(select(Breach).where(Breach.status == "open")):
        deadline = b.notify_deadline
        if deadline.date() < today or deadline <= soon:
            section = "overdue" if deadline.date() < today else "week"
            for u in officers(b.scope_id):
                title = f"Breach {b.code} notification deadline: {b.title}"
                c.add(u.id, title, deadline.date(), f"/privacy/breaches/{b.id}", section=section)
    for p in db.scalars(select(ProcessingActivity).where(ProcessingActivity.status == "active")):
        for u in officers(p.scope_id):
            c.add(
                u.id,
                f"Processing activity {p.code} review: {p.name}",
                p.review_due,
                f"/privacy/{p.id}",
                UPCOMING,
            )
    for d in db.scalars(select(Dpia).where(Dpia.status == "approved")):
        for u in officers(d.activity.scope_id):
            title = f"DPIA review: {d.activity.code} {d.activity.name}"
            c.add(u.id, title, d.review_due, f"/privacy/{d.activity_id}", UPCOMING)

    for aia in db.scalars(select(AiImpactAssessment).where(AiImpactAssessment.status == "approved")):
        s = db.get(AiSystem, aia.ai_system_id)
        c.add(
            s.owner_id,
            f"AI impact assessment review: {s.code} {s.name}",
            aia.review_due,
            f"/ai/{s.id}",
            UPCOMING,
        )

    return dict(c.items)


def _day(d: date | None) -> str:
    return d.strftime("%d %b %Y").lstrip("0") if d else ""


def compose(user: User, items: list[Item], base_url: str, org_name: str) -> Outgoing:
    counts = {key: sum(1 for i in items if i.section == key) for key, _ in SECTIONS}
    parts = [
        f"{counts['overdue']} overdue" if counts["overdue"] else "",
        f"{counts['week']} due this week" if counts["week"] else "",
        f"{counts['upcoming']} coming up" if counts["upcoming"] else "",
    ]
    subject = "Assayr: " + ", ".join(p for p in parts if p)
    text = [f"Hello {user.full_name},", "", f"This is your daily summary from Assayr ({org_name}).", ""]
    html = [
        f"<p>Hello {escape(user.full_name)},</p><p>This is your daily summary from Assayr ({escape(org_name)}).</p>"
    ]
    for key, heading in SECTIONS:
        section = sorted((i for i in items if i.section == key), key=lambda i: (i.due or date.max, i.title))
        if not section:
            continue
        text += [heading, "-" * len(heading)]
        html.append(f"<h3>{escape(heading)}</h3><ul>")
        for i in section:
            url = f"{base_url}{i.path}"
            when = f" (due {_day(i.due)})" if i.due else ""
            text += [f"- {i.title}{when}", f"  {url}"]
            html.append(f'<li><a href="{escape(url)}">{escape(i.title)}</a>{escape(when)}</li>')
        text.append("")
        html.append("</ul>")
    footer = "You can turn this summary off from your name in the top bar of Assayr."
    text.append(footer)
    html.append(f"<p style='color:#666'>{escape(footer)}</p>")
    return Outgoing(to=user.email, subject=subject, text="\n".join(text), html="".join(html))


def ran_today(db: Session, today: date) -> bool:
    return (
        db.scalar(select(MailLog.id).where(MailLog.kind == "run", MailLog.day == today).limit(1)) is not None
    )


def _log_run(db: Session, today: date, status: str, sent: int, error: str | None) -> None:
    db.add(MailLog(user_id=None, kind="run", day=today, status=status, item_count=sent, error=error))
    db.commit()


def run_digest(db: Session, secret_key: str | None, today: date, org_name: str = "Assayr") -> dict[str, int]:
    """Sends today's summary to everyone with something due; never twice to the same person on the same day."""
    result = {"sent": 0, "failed": 0, "skipped": 0}
    cfg = db.scalar(select(MailSettings))
    if cfg is None or not cfg.enabled or not cfg.host or ran_today(db, today):
        return result
    items = collect(db, today)
    done = set(db.scalars(select(MailLog.user_id).where(MailLog.kind == "digest", MailLog.day == today)))
    people = [
        u
        for u in db.scalars(select(User).where(User.id.in_(list(items)), User.is_active.is_(True)))
        if not u.digest_opt_out and u.id not in done
    ]
    if not people:
        _log_run(db, today, "sent", 0, None)
        return result
    failures: list[str] = []
    try:
        with Connection(cfg, password_of(cfg, secret_key)) as connection:
            for person in sorted(people, key=lambda u: u.email):
                log = MailLog(
                    user_id=person.id,
                    kind="digest",
                    day=today,
                    status="sent",
                    item_count=len(items[person.id]),
                )
                try:
                    with db.begin_nested():  # claims the person for today; a second worker skips them
                        db.add(log)
                        db.flush()
                except IntegrityError:
                    result["skipped"] += 1
                    continue
                db.commit()
                try:
                    connection.send(compose(person, items[person.id], cfg.base_url or "", org_name))
                    result["sent"] += 1
                except MailError as exc:
                    log.status, log.error = "failed", str(exc)
                    db.commit()
                    result["failed"] += 1
                    failures.append(f"{person.email}: {exc}")
    except MailError as exc:
        _log_run(db, today, "failed", result["sent"], str(exc))
        return result
    error = f"{len(failures)} failed: " + "; ".join(failures[:5]) if failures else None
    _log_run(db, today, "partial" if failures else "sent", result["sent"], error)
    return result
