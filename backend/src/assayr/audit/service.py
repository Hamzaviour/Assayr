"""Writing and verifying the hash-chained audit trail."""

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from assayr.audit.models import AuditLog
from assayr.db import utcnow

GENESIS = "0" * 64
_ADVISORY_LOCK_KEY = 727274  # serialises chain appends on PostgreSQL


@dataclass(frozen=True)
class Actor:
    id: uuid.UUID | None
    email: str | None
    ip: str | None = None
    request_id: str | None = None


SYSTEM = Actor(id=None, email="system")


@dataclass(frozen=True)
class ChainCheck:
    ok: bool
    checked: int
    first_bad_seq: int | None


def _canonical(entry: AuditLog) -> str:
    payload = {
        "at": entry.at.astimezone(UTC).isoformat(timespec="microseconds"),
        "actor_id": str(entry.actor_id) if entry.actor_id else None,
        "actor_email": entry.actor_email,
        "ip": entry.ip,
        "action": entry.action,
        "entity_type": entry.entity_type,
        "entity_id": entry.entity_id,
        "diff": entry.diff,
        "reason": entry.reason,
        "request_id": entry.request_id,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def compute_hash(prev_hash: str, entry: AuditLog) -> str:
    return hashlib.sha256((prev_hash + _canonical(entry)).encode()).hexdigest()


def record(
    session: Session,
    actor: Actor,
    action: str,
    entity_type: str,
    entity_id: str | None = None,
    diff: dict[str, Any] | None = None,
    reason: str | None = None,
    at: datetime | None = None,
) -> AuditLog:
    """Append one entry. Flushes but does not commit: it joins the caller's transaction."""
    if session.get_bind().dialect.name == "postgresql":
        session.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": _ADVISORY_LOCK_KEY})
    last = session.scalar(select(AuditLog).order_by(AuditLog.seq.desc()).limit(1))
    prev_hash = last.hash if last else GENESIS
    entry = AuditLog(
        at=at or utcnow(),
        actor_id=actor.id,
        actor_email=actor.email,
        ip=actor.ip,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        diff=diff,
        reason=reason,
        request_id=actor.request_id,
        prev_hash=prev_hash,
        hash="",
    )
    entry.hash = compute_hash(prev_hash, entry)
    session.add(entry)
    session.flush()
    return entry


def verify_chain(session: Session) -> ChainCheck:
    prev_hash = GENESIS
    checked = 0
    for entry in session.scalars(select(AuditLog).order_by(AuditLog.seq).execution_options(yield_per=1000)):
        if entry.prev_hash != prev_hash or compute_hash(prev_hash, entry) != entry.hash:
            return ChainCheck(ok=False, checked=checked, first_bad_seq=entry.seq)
        prev_hash = entry.hash
        checked += 1
    return ChainCheck(ok=True, checked=checked, first_bad_seq=None)
