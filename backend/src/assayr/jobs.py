"""A small job queue in the main database, processed by `assayr worker`."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import JSON, BigInteger, Index, Integer, String, Text, and_, or_, select
from sqlalchemy.orm import Mapped, Session, mapped_column, sessionmaker

from assayr.config import Settings
from assayr.db import Base, UTCDateTime, utcnow
from assayr.storage import BlobStore


class Job(Base):
    __tablename__ = "job"
    __table_args__ = (Index("ix_job_status_run_after", "status", "run_after"),)

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    kind: Mapped[str] = mapped_column(String(40))
    payload: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(10), default="queued")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    run_after: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    locked_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


MAX_ATTEMPTS = 3
STALE_AFTER = timedelta(minutes=10)


@dataclass(frozen=True)
class JobEnv:
    settings: Settings
    store: BlobStore
    now: Callable[[], datetime]


HANDLERS: dict[str, Callable[[Session, dict, JobEnv], None]] = {}


def handler(kind: str):
    def register(func):
        HANDLERS[kind] = func
        return func

    return register


def enqueue(db: Session, kind: str, payload: dict, now: datetime) -> Job:
    job = Job(kind=kind, payload=payload, status="queued", attempts=0, run_after=now, created_at=now)
    db.add(job)
    db.flush()
    return job


def claim_next(db: Session, now: datetime) -> Job | None:
    """Claim the oldest runnable job; on PostgreSQL concurrent workers skip each other's locked rows."""
    stmt = (
        select(Job)
        .where(
            or_(
                and_(Job.status == "queued", Job.run_after <= now),
                and_(Job.status == "running", Job.locked_at < now - STALE_AFTER),
            )
        )
        .order_by(Job.id)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    job = db.scalar(stmt)
    if job is None:
        return None
    job.status = "running"
    job.locked_at = now
    job.attempts += 1
    db.commit()
    return job


def run_one(make_session: sessionmaker, env: JobEnv) -> bool:
    with make_session() as db:
        job = claim_next(db, env.now())
        if job is None:
            return False
        job_id = job.id
        func = HANDLERS.get(job.kind)
        if func is None:
            job.status = "failed"
            job.last_error = f"Unknown job kind: {job.kind}"
            db.commit()
            return True
        try:
            func(db, dict(job.payload), env)
            job = db.get(Job, job_id)
            job.status = "done"
            job.last_error = None
            db.commit()
        except Exception as exc:  # noqa: BLE001 - a failing job must never stop the worker
            db.rollback()
            job = db.get(Job, job_id)
            job.last_error = f"{type(exc).__name__}: {exc}"[:2000]
            if job.attempts >= MAX_ATTEMPTS:
                job.status = "failed"
            else:
                job.status = "queued"
                job.run_after = env.now() + timedelta(seconds=30 * job.attempts)
            db.commit()
        return True


def run_pending(make_session: sessionmaker, env: JobEnv, limit: int = 100) -> int:
    processed = 0
    while processed < limit and run_one(make_session, env):
        processed += 1
    return processed
