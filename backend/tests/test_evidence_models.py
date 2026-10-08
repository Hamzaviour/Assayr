from sqlalchemy import func, select

from assayr.catalogue.models import EvidenceSlot
from assayr.evidence.models import Artefact, ArtefactLink, ArtefactVersion


def test_deleting_an_artefact_removes_versions_and_links(db, seeded):
    slot = db.scalar(select(EvidenceSlot).limit(1))
    artefact = Artefact(scope_id=seeded.id, title="Policy")
    version = ArtefactVersion(
        version_no=1, sha256="a" * 64, size=10, filename="p.pdf", mime="application/pdf"
    )
    artefact.versions.append(version)
    db.add(artefact)
    db.flush()
    db.add(ArtefactLink(version_id=version.id, slot_id=slot.id))
    db.commit()
    db.delete(artefact)
    db.commit()
    assert db.scalar(select(func.count()).select_from(ArtefactLink)) == 0
    assert db.scalar(select(func.count()).select_from(ArtefactVersion)) == 0


def test_new_link_starts_verifying(db, seeded):
    slot = db.scalar(select(EvidenceSlot).limit(1))
    artefact = Artefact(scope_id=seeded.id, title="Policy")
    artefact.versions.append(
        ArtefactVersion(version_no=1, sha256="b" * 64, size=1, filename="p.pdf", mime=None)
    )
    db.add(artefact)
    db.flush()
    link = ArtefactLink(version_id=artefact.versions[0].id, slot_id=slot.id)
    db.add(link)
    db.commit()
    assert link.state == "verifying"
    assert link.created_at.utcoffset().total_seconds() == 0
