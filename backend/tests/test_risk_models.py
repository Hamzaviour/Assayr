from sqlalchemy import func, select

from assayr.assets.models import Asset
from assayr.catalogue.models import Control
from assayr.risk.models import Risk, RiskControl, Threat
from assayr.tasks.models import Task


def test_risk_links_load_and_cascade(db, seeded):
    control = db.scalar(select(Control).where(Control.code == "A.8.13"))
    asset = Asset(scope_id=seeded.id, code="AST-001", seq=1, name="File server", type="server")
    risk = Risk(scope_id=seeded.id, code="R-001", seq=1, title="Ransomware encrypts file servers")
    risk.assets.append(asset)
    risk.threats.append(Threat(code="TX1", name="Test threat", category="Test"))
    risk.control_links.append(RiskControl(control=control, axis="likelihood"))
    db.add(risk)
    db.commit()
    db.expire_all()
    loaded = db.scalar(select(Risk))
    assert loaded.status == "draft" and loaded.approach == "event"
    assert [a.code for a in loaded.assets] == ["AST-001"]
    assert [link.control.code for link in loaded.control_links] == ["A.8.13"]
    db.delete(loaded)
    db.commit()
    assert db.scalar(select(func.count()).select_from(RiskControl)) == 0
    assert db.scalar(select(func.count()).select_from(Asset)) == 1


def test_controls_are_applicable_by_default(db, seeded):
    assert db.scalar(select(Control).limit(1)).applicable is True


def test_tasks_default_to_todo(db, seeded):
    task = Task(scope_id=seeded.id, entity_type="risk", entity_id="x", title="Enable MFA")
    db.add(task)
    db.commit()
    assert task.status == "todo" and task.created_at.utcoffset().total_seconds() == 0
