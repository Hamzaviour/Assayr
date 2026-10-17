"""The daily digest job, queued by the worker's hourly sweep once the digest hour has passed."""

from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from assayr.jobs import Job, JobEnv, enqueue, handler
from assayr.mail.digest import ran_today, run_digest
from assayr.mail.models import MailSettings


@handler("mail_digest")
def mail_digest_job(db: Session, payload: dict, env: JobEnv) -> None:
    run_digest(db, env.settings.secret_key, date.fromisoformat(payload["day"]), env.settings.org_name)


def enqueue_mail_digest(db: Session, local_now: datetime, now: datetime) -> bool:
    """Queues today's digest when email is on, the digest hour (server time) has passed and it has not run yet."""
    cfg = db.scalar(select(MailSettings))
    if cfg is None or not cfg.enabled or local_now.hour < cfg.digest_hour:
        return False
    today = local_now.date()
    if ran_today(db, today):
        return False
    waiting = db.scalar(
        select(Job.id).where(Job.kind == "mail_digest", Job.status.in_(["queued", "running"])).limit(1)
    )
    if waiting is not None:
        return False
    enqueue(db, "mail_digest", {"day": today.isoformat()}, now)
    return True
