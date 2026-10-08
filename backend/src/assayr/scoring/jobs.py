import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from assayr.identity.models import Scope
from assayr.jobs import Job, JobEnv, enqueue, handler
from assayr.risk.service import refresh_scope_risks
from assayr.scoring.service import recompute_scope


@handler("recompute_scope")
def recompute_scope_job(db: Session, payload: dict, env: JobEnv) -> None:
    scope_id = uuid.UUID(payload["scope_id"])
    now = env.now()
    recompute_scope(db, scope_id, now, env.settings)
    refresh_scope_risks(db, scope_id, now)
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
