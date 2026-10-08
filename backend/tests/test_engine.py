from datetime import timedelta

from sqlalchemy import func, select

from assayr.audit.models import AuditLog
from assayr.catalogue.models import Control
from assayr.jobs import JobEnv
from assayr.scoring.models import StatusTransition
from assayr.verification import engine
from assayr.verification.av import AvResult
from assayr.verification.engine import verify_link
from assayr.verification.rules import run_order
from tests.evidence_helpers import add_link, policy_text
from tests.fixtures import PNG_BYTES, make_pdf


def env_for(app):
    return JobEnv(settings=app.state.settings, store=app.state.store, now=app.state.clock)


def first_slot(db, code):
    control = db.scalar(select(Control).where(Control.code == code))
    return control, control.slots[0]


def upload(db, app, seeded, code, content, *, filename="policy.pdf", mime="application/pdf", artefact=None):
    control, slot = first_slot(db, code)
    link = add_link(
        db,
        app.state.store,
        slot,
        scope_id=seeded.id,
        state="verifying",
        content=content,
        filename=filename,
        mime=mime,
        artefact=artefact,
    )
    db.commit()
    return control, slot, link


def results(run):
    return {r.code: r.status for r in run.results}


def test_approved_policy_is_accepted_and_the_control_moves_on(app, db, seeded, clock):
    today = clock().date()
    control, slot, link = upload(db, app, seeded, "A.5.1", make_pdf(policy_text(today).split("\n")))
    run = verify_link(db, link.id, env_for(app))
    db.refresh(link)
    assert run.verdict == "accept" and link.state == "accepted" and link.confidence == 1.0
    assert len(run.results) == len(run_order(slot.rules))
    assert results(run)["V-RELEVANCE"] == "skipped"
    assert link.evidence_date == today - timedelta(days=30)
    assert link.expires_on == link.evidence_date + timedelta(days=slot.freshness_days)
    transition = db.scalar(select(StatusTransition).where(StatusTransition.control_id == control.id))
    assert (transition.to_status, "policy.pdf" in transition.trigger) == ("in_progress", True)
    assert (
        db.scalar(select(AuditLog).where(AuditLog.action == "evidence.verdict")).diff["verdict"] == "accept"
    )


def test_draft_without_approval_goes_to_review(app, db, seeded, clock):
    today = clock().date()
    _, _, link = upload(db, app, seeded, "A.5.1", make_pdf(policy_text(today, approved=False).split("\n")))
    run = verify_link(db, link.id, env_for(app))
    assert results(run)["V-APPROVAL"] == "fail"
    assert run.verdict == "review" and db.get(type(link), link.id).state == "in_review"


def test_stale_evidence_is_rejected(app, db, seeded, clock):
    old = clock().date() - timedelta(days=200)
    text = f"Acme Financial Services quarterly access review. Approved by Sana Malik on {old.isoformat()}."
    _, _, link = upload(db, app, seeded, "A.5.18", make_pdf([text]))
    run = verify_link(db, link.id, env_for(app))
    assert results(run)["V-FRESH"] == "fail" and run.verdict == "reject"


def test_images_go_to_review_because_nothing_can_be_read(app, db, seeded):
    _, _, link = upload(db, app, seeded, "A.5.1", PNG_BYTES, filename="shot.png", mime="image/png")
    run = verify_link(db, link.id, env_for(app))
    assert results(run)["V-FMT"] == "pass" and results(run)["V-APPROVAL"] == "skipped"
    assert run.verdict == "review"


def test_unreadable_file_is_rejected(app, db, seeded):
    _, _, link = upload(db, app, seeded, "A.5.1", b"%PDF-1.4\nbroken")
    run = verify_link(db, link.id, env_for(app))
    assert results(run)["V-FMT"] == "fail" and run.verdict == "reject"


def test_infected_file_is_rejected(app, db, seeded, clock, monkeypatch):
    app.state.settings = app.state.settings.model_copy(update={"clamav_host": "clamav"})
    monkeypatch.setattr(
        engine, "scan_file", lambda *a, **k: AvResult("infected", signature="Eicar-Signature")
    )
    _, _, link = upload(db, app, seeded, "A.5.1", make_pdf(policy_text(clock().date()).split("\n")))
    run = verify_link(db, link.id, env_for(app))
    assert results(run)["V-AV"] == "fail" and run.verdict == "reject"


def test_only_links_awaiting_verification_are_processed(app, db, seeded, clock):
    _, _, link = upload(db, app, seeded, "A.5.1", make_pdf(policy_text(clock().date()).split("\n")))
    verify_link(db, link.id, env_for(app))
    assert verify_link(db, link.id, env_for(app)) is None


def test_reverification_after_a_crash_completes(app, db, seeded, clock, monkeypatch):
    """A worker that died mid-run leaves a partial run behind; the retry finishes cleanly."""
    _, _, link = upload(db, app, seeded, "A.5.1", make_pdf(policy_text(clock().date()).split("\n")))
    real_decide = engine.decide

    def crash(*args, **kwargs):
        raise RuntimeError("worker killed")

    monkeypatch.setattr(engine, "decide", crash)
    try:
        verify_link(db, link.id, env_for(app))
    except RuntimeError:
        db.rollback()
    monkeypatch.setattr(engine, "decide", real_decide)
    assert db.get(type(link), link.id).state == "verifying"
    run = verify_link(db, link.id, env_for(app))
    assert run.verdict == "accept"


def test_a_newer_accepted_version_supersedes_the_older_one(app, db, seeded, clock):
    today = clock().date()
    _, _, first = upload(db, app, seeded, "A.5.1", make_pdf(policy_text(today).split("\n")))
    verify_link(db, first.id, env_for(app))
    newer = policy_text(today, dated=today - timedelta(days=1)).split("\n")
    _, _, second = upload(db, app, seeded, "A.5.1", make_pdf(newer), artefact=first.version.artefact)
    verify_link(db, second.id, env_for(app))
    db.expire_all()
    assert db.get(type(first), first.id).state == "superseded"
    assert db.get(type(second), second.id).state == "accepted"


def test_verify_job_runs_through_the_queue(app, db, seeded, clock):
    from assayr.jobs import enqueue
    from tests.evidence_helpers import run_jobs

    _, _, link = upload(db, app, seeded, "A.5.1", make_pdf(policy_text(clock().date()).split("\n")))
    enqueue(db, "verify_link", {"link_id": str(link.id)}, now=clock())
    db.commit()
    assert run_jobs(app) == 1
    assert (
        db.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.action == "evidence.verdict"))
        == 1
    )
