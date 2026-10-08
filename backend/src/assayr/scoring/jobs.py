import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from assayr.identity.models import Scope
from assayr.jobs import Job, JobEnv, enqueue, handler
from assayr.scoring.service import recompute_scope


@handler("recompute_scope")
def recompute_scope_job(db: Session, payload: dict, env: JobEnv) -> None:
    recompute_scope(db, uuid.UUID(payload["scope_id"]), env.now(), env.settings)
    db.commit()


def enqueue_recompute_all(db: Session, now: datetime) -> None:
    waiting = {
        job.payload.get("scope_id")
        for job in db.scalars(
            select(Job).where(Job.kind == "recompute_scope", Job.status.in_(["queued", "running"]))
        )
    }
    for scope_id in db.scalars(select(Scope.id)):
        if str(scope_id) not in waiting:
            enqueue(db, "recompute_scope", {"scope_id": str(scope_id)}, now)
