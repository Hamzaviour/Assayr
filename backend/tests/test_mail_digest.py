from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import select

from assayr.ai.models import AiImpactAssessment, AiSystem
from assayr.catalogue.models import Control, EvidenceSlot
from assayr.documents.models import Document
from assayr.evidence.models import Artefact, ArtefactLink, ArtefactVersion
from assayr.findings.models import CorrectiveAction, Finding
from assayr.mail.crypto import encrypt
from assayr.mail.digest import collect, compose, run_digest
from assayr.mail.models import MailLog, MailSettings
from assayr.privacy.models import Breach, SubjectRequest
from assayr.risk.models import Risk
from assayr.training.models import Assignment, Course
from tests import mail_helpers
from tests.conftest import create_user

TODAY = date(2026, 10, 20)
KEY = "invented-test-key"


@pytest.fixture
def world(db, seeded):
    """One item of every kind, each due for a different person."""
    s = seeded.id
    p = {
        "owner": create_user(db, "omar@acme.com", roles=(("control_owner", None),), full_name="Omar Owner"),
        "doer": create_user(db, "dina@acme.com", roles=(("control_owner", None),), full_name="Dina Doer"),
        "auditor": create_user(
            db, "ali@acme.com", roles=(("internal_auditor", None),), full_name="Ali Auditor"
        ),
        "privacy": create_user(
            db, "pia@acme.com", roles=(("privacy_officer", None),), full_name="Pia Privacy"
        ),
        "staff": create_user(db, "sam@acme.com", roles=(("employee", None),), full_name="Sam Staff"),
        "quiet": create_user(db, "quinn@acme.com", roles=(("viewer", None),), full_name="Quinn Quiet"),
    }
    late = Finding(
        scope_id=s,
        code="F-001",
        seq=1,
        title="Invented late finding",
        grade="major",
        source="internal_audit",
        owner_id=p["owner"].id,
        due_date=TODAY - timedelta(days=2),
        status="action_planned",
        root_cause="x",
        raised_at=datetime(2026, 9, 1, tzinfo=UTC),
    )
    late.actions.append(
        CorrectiveAction(
            seq=1, description="Invented action", owner_id=p["doer"].id, due_date=TODAY + timedelta(days=3)
        )
    )
    waiting = Finding(
        scope_id=s,
        code="F-002",
        seq=2,
        title="Invented waiting finding",
        grade="minor",
        source="internal_audit",
        owner_id=p["owner"].id,
        due_date=TODAY + timedelta(days=60),
        status="awaiting_verification",
        root_cause="x",
        raised_at=datetime(2026, 9, 1, tzinfo=UTC),
    )
    waiting.actions.append(
        CorrectiveAction(seq=1, description="Done", owner_id=p["doer"].id, status="done", done_note="x")
    )
    db.add_all([late, waiting])
    db.add(
        Document(
            scope_id=s,
            doc_type="policy",
            code="POL-001",
            title="Invented policy",
            owner_id=p["owner"].id,
            status="approved",
            review_due=TODAY + timedelta(days=20),
        )
    )
    course = Course(scope_id=s, title="Invented awareness")
    db.add(course)
    db.flush()
    db.add(
        Assignment(
            course_id=course.id,
            user_id=p["staff"].id,
            source="all",
            status="assigned",
            assigned_at=datetime(2026, 10, 1, tzinfo=UTC),
            due_at=TODAY + timedelta(days=5),
        )
    )
    db.add(
        Risk(
            scope_id=s,
            code="R-001",
            seq=1,
            title="Invented risk",
            owner_id=p["owner"].id,
            status="treated",
            review_due=TODAY - timedelta(days=1),
        )
    )
    db.add(
        SubjectRequest(
            scope_id=s,
            code="DSR-001",
            seq=1,
            type="access",
            requester_name="Invented Person",
            received_on=TODAY - timedelta(days=25),
            due_on=TODAY + timedelta(days=5),
            status="open",
        )
    )
    db.add(
        Breach(
            scope_id=s,
            code="BR-001",
            seq=1,
            title="Invented breach",
            discovered_at=datetime(2026, 10, 19, 9, tzinfo=UTC),
            notify_deadline=datetime(2026, 10, 22, 9, tzinfo=UTC),
            status="open",
        )
    )
    system = AiSystem(
        scope_id=s,
        code="AIS-001",
        seq=1,
        name="Invented model",
        source="in_house",
        lifecycle="deployed",
        risk_level=2,
        owner_id=p["owner"].id,
        status="active",
    )
    db.add(system)
    db.flush()
    db.add(
        AiImpactAssessment(ai_system_id=system.id, status="approved", review_due=TODAY + timedelta(days=25))
    )
    control = db.scalar(select(Control).where(Control.scope_id == s, Control.code == "A.5.1"))
    control.owner_id = p["doer"].id
    slot = db.scalar(select(EvidenceSlot).where(EvidenceSlot.control_id == control.id))
    artefact = Artefact(scope_id=s, title="Invented evidence")
    db.add(artefact)
    db.flush()
    version = ArtefactVersion(
        artefact_id=artefact.id, version_no=1, sha256="a" * 64, size=1, filename="e.pdf"
    )
    db.add(version)
    db.flush()
    db.add(
        ArtefactLink(
            version_id=version.id, slot_id=slot.id, state="accepted", expires_on=TODAY + timedelta(days=10)
        )
    )
    db.commit()
    return p


def titles(items):
    return sorted((i.section, i.title) for i in items)


def test_each_person_gets_their_own_items(db, world):
    items = collect(db, TODAY)
    p = world
    assert titles(items[p["owner"].id]) == [
        ("overdue", "Finding F-001: Invented late finding"),
        ("overdue", "Risk R-001 review: Invented risk"),
        ("upcoming", "AI impact assessment review: AIS-001 Invented model"),
        ("upcoming", "Policy POL-001 review: Invented policy"),
    ]
    assert titles(items[p["doer"].id]) == [
        ("upcoming", "Evidence expires for A.5.1: Invented evidence"),
        ("week", "Corrective action F-001 #1: Invented action"),
    ]
    assert titles(items[p["auditor"].id]) == [("week", "Verify finding F-002: Invented waiting finding")]
    assert titles(items[p["staff"].id]) == [("week", "Training: Invented awareness")]
    assert titles(items[p["privacy"].id]) == [
        ("week", "Breach BR-001 notification deadline: Invented breach"),
        ("week", "Data subject request DSR-001 (access) from Invented Person"),
    ]
    assert p["quiet"].id not in items


def test_the_email_groups_items_and_links_to_them(db, world):
    items = collect(db, TODAY)
    mail = compose(world["owner"], items[world["owner"].id], "https://grc.acme.local", "Acme")
    assert mail.to == "omar@acme.com"
    assert mail.subject == "Assayr: 2 overdue, 2 coming up"
    assert mail.text.index("Overdue") < mail.text.index("Coming up")
    finding = db.scalar(select(Finding).where(Finding.code == "F-001"))
    assert f"https://grc.acme.local/findings/{finding.id}" in mail.text
    assert "https://grc.acme.local/risks/R-001" in mail.text and "<a href" in mail.html


def configure(db, enabled=True):
    db.add(
        MailSettings(
            enabled=enabled,
            host="mail.acme.local",
            port=587,
            security="starttls",
            username="assayr@acme.com",
            password_encrypted=encrypt(KEY, "Invented-Secret-1"),
            from_address="assayr@acme.com",
            from_name="Acme GRC",
            base_url="https://grc.acme.local",
            digest_hour=7,
        )
    )
    db.commit()


def test_a_run_sends_once_per_person_per_day(db, world, monkeypatch):
    sent = mail_helpers.install(monkeypatch)
    configure(db)
    result = run_digest(db, KEY, TODAY)
    assert sorted(m["to"] for m in sent) == sorted(
        ["omar@acme.com", "dina@acme.com", "ali@acme.com", "sam@acme.com", "pia@acme.com"]
    )
    assert result == {"sent": 5, "failed": 0, "skipped": 0}
    assert run_digest(db, KEY, TODAY) == {"sent": 0, "failed": 0, "skipped": 0}
    assert len(sent) == 5
    run = db.scalar(select(MailLog).where(MailLog.kind == "run"))
    assert (run.status, run.item_count) == ("sent", 5)


def test_opted_out_and_inactive_people_get_nothing(db, world, monkeypatch):
    sent = mail_helpers.install(monkeypatch)
    configure(db)
    world["owner"].digest_opt_out = True
    world["staff"].is_active = False
    db.commit()
    run_digest(db, KEY, TODAY)
    assert "omar@acme.com" not in {m["to"] for m in sent} and "sam@acme.com" not in {m["to"] for m in sent}


def test_one_refused_recipient_does_not_stop_the_others(db, world, monkeypatch):
    sent = mail_helpers.install(monkeypatch)
    mail_helpers.FakeSMTP.fail_for = {"dina@acme.com"}
    configure(db)
    result = run_digest(db, KEY, TODAY)
    assert result == {"sent": 4, "failed": 1, "skipped": 0} and len(sent) == 4
    failed = db.scalar(select(MailLog).where(MailLog.status == "failed", MailLog.kind == "digest"))
    assert failed.user_id == world["doer"].id and "no such mailbox" in failed.error
    run = db.scalar(select(MailLog).where(MailLog.kind == "run"))
    assert "dina@acme.com" in run.error


def test_a_server_failure_is_recorded_once(db, world, monkeypatch):
    mail_helpers.install(monkeypatch)
    mail_helpers.FakeSMTP.fail_login = True
    configure(db)
    assert run_digest(db, KEY, TODAY)["sent"] == 0
    run = db.scalar(select(MailLog).where(MailLog.kind == "run"))
    assert run.status == "failed" and "bad credentials" in run.error
    assert db.scalar(select(MailLog).where(MailLog.kind == "digest")) is None


def test_nothing_is_sent_while_email_is_off(db, world, monkeypatch):
    sent = mail_helpers.install(monkeypatch)
    configure(db, enabled=False)
    assert run_digest(db, KEY, TODAY) == {"sent": 0, "failed": 0, "skipped": 0}
    assert sent == []


def test_the_worker_queues_the_digest_once_after_the_digest_hour(db, world, monkeypatch):
    from assayr.jobs import Job
    from assayr.mail.jobs import enqueue_mail_digest

    configure(db)
    now = datetime(2026, 10, 20, 4, tzinfo=UTC)
    assert enqueue_mail_digest(db, datetime(2026, 10, 20, 6, 30), now) is False
    assert enqueue_mail_digest(db, datetime(2026, 10, 20, 7, 5), now) is True
    assert enqueue_mail_digest(db, datetime(2026, 10, 20, 9, 0), now) is False
    job = db.scalar(select(Job).where(Job.kind == "mail_digest"))
    assert job.payload == {"day": "2026-10-20"}


def test_the_job_sends_the_digest(db, world, monkeypatch, app):
    from assayr.jobs import JobEnv
    from assayr.mail.jobs import mail_digest_job

    sent = mail_helpers.install(monkeypatch)
    configure(db)
    app.state.settings.secret_key = KEY
    env = JobEnv(settings=app.state.settings, store=None, now=lambda: datetime(2026, 10, 20, 5, tzinfo=UTC))
    mail_digest_job(db, {"day": "2026-10-20"}, env)
    assert len(sent) == 5 and all(m["raw"]["From"] == "Acme GRC <assayr@acme.com>" for m in sent)
