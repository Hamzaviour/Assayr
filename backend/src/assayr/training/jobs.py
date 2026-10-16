"""The training sweep job: yearly refresh and new joiners."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from assayr.jobs import Job, JobEnv, enqueue, handler
from assayr.training.service import sweep


@handler("training_sweep")
def training_sweep_job(db: Session, payload: dict, env: JobEnv) -> None:
    sweep(db, env.now())
    db.commit()


def enqueue_training_sweep(db: Session, now: datetime) -> None:
    waiting = db.scalar(
        select(Job.id).where(Job.kind == "training_sweep", Job.status.in_(["queued", "running"])).limit(1)
    )
    if waiting is None:
        enqueue(db, "training_sweep", {}, now)
