from datetime import timedelta

from sqlalchemy import select

from assayr.db import utcnow
from assayr.jobs import HANDLERS, Job, enqueue
from assayr.scoring.jobs import enqueue_recompute_all
from tests.evidence_helpers import run_jobs


def test_queued_job_runs_once(app, db, monkeypatch):
    seen = []
    monkeypatch.setitem(HANDLERS, "test.echo", lambda session, payload, env: seen.append(payload["n"]))
    enqueue(db, "test.echo", {"n": 1}, now=utcnow())
    db.commit()
    assert run_jobs(app) == 1
    assert seen == [1]
    assert db.scalar(select(Job.status)) == "done"
    assert run_jobs(app) == 0


def test_failing_job_retries_then_fails(app, db, clock, monkeypatch):
    def boom(session, payload, env):
        raise RuntimeError("disk full")

    monkeypatch.setitem(HANDLERS, "test.boom", boom)
    enqueue(db, "test.boom", {}, now=clock())
    db.commit()
    for attempt in (1, 2, 3):
        assert run_jobs(app) == 1
        db.expire_all()
        job = db.scalar(select(Job))
        assert job.attempts == attempt
        clock.advance(minutes=5)
    assert job.status == "failed" and "disk full" in job.last_error
    assert run_jobs(app) == 0


def test_unknown_kind_fails_immediately(app, db):
    enqueue(db, "test.nope", {}, now=utcnow())
    db.commit()
    run_jobs(app)
    job = db.scalar(select(Job))
    assert (job.status, job.last_error) == ("failed", "Unknown job kind: test.nope")


def test_stale_running_job_is_reclaimed(app, db, clock, monkeypatch):
    seen = []
    monkeypatch.setitem(HANDLERS, "test.echo", lambda session, payload, env: seen.append(1))
    job = enqueue(db, "test.echo", {}, now=clock())
    job.status, job.locked_at, job.attempts = "running", clock() - timedelta(minutes=11), 1
    db.commit()
    assert run_jobs(app) == 1 and seen == [1]


def test_recompute_all_enqueues_each_scope_once(app, db, seeded):
    enqueue_recompute_all(db, utcnow())
    enqueue_recompute_all(db, utcnow())
    db.commit()
    assert [j.kind for j in db.scalars(select(Job))] == ["recompute_scope"]
    assert run_jobs(app) == 1


def test_stale_job_out_of_attempts_is_failed_not_rerun(app, db, clock, monkeypatch):
    """A job that keeps killing the worker must not be retried forever."""
    seen = []
    monkeypatch.setitem(HANDLERS, "test.echo", lambda session, payload, env: seen.append(1))
    job = enqueue(db, "test.echo", {}, now=clock())
    job.status, job.locked_at, job.attempts = "running", clock() - timedelta(minutes=11), 3
    db.commit()
    assert run_jobs(app) == 1
    db.expire_all()
    job = db.scalar(select(Job))
    assert seen == [] and job.status == "failed"
    assert job.last_error == "The worker stopped while running this job."


def test_failure_handler_runs_once_when_a_job_finally_fails(app, db, clock, monkeypatch):
    from assayr.jobs import FAILURE_HANDLERS

    def boom(session, payload, env):
        raise RuntimeError("disk full")

    failures = []
    monkeypatch.setitem(HANDLERS, "test.boom", boom)
    monkeypatch.setitem(
        FAILURE_HANDLERS, "test.boom", lambda session, payload, env, error: failures.append(error)
    )
    enqueue(db, "test.boom", {"n": 1}, now=clock())
    db.commit()
    for _ in range(3):
        run_jobs(app)
        clock.advance(minutes=5)
    assert failures == ["RuntimeError: disk full"]
