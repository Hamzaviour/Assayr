"""Shortcuts for building evidence in tests without going through the API."""

import io
import uuid
from datetime import timedelta

from assayr.evidence.models import Artefact, ArtefactLink, ArtefactVersion


def add_link(
    db,
    store,
    slot,
    *,
    scope_id,
    state="accepted",
    evidence_date=None,
    content=None,
    filename="evidence.pdf",
    mime="application/pdf",
    uploaded_by=None,
    artefact=None,
):
    data = content if content is not None else f"evidence {uuid.uuid4()}".encode()
    blob = store.put(io.BytesIO(data), max_bytes=50_000_000)
    if artefact is None:
        artefact = Artefact(scope_id=scope_id, title=filename, uploaded_by_id=uploaded_by)
        db.add(artefact)
    version = ArtefactVersion(
        version_no=len(artefact.versions) + 1,
        sha256=blob.sha256,
        size=blob.size,
        filename=filename,
        mime=mime,
        uploaded_by_id=uploaded_by,
    )
    artefact.versions.append(version)
    db.flush()
    expires = (
        evidence_date + timedelta(days=slot.freshness_days) if evidence_date and slot.freshness_days else None
    )
    link = ArtefactLink(
        version_id=version.id,
        slot_id=slot.id,
        state=state,
        evidence_date=evidence_date,
        expires_on=expires,
        confidence=0.95 if state == "accepted" else None,
    )
    db.add(link)
    db.flush()
    return link


def run_jobs(app) -> int:
    from assayr.jobs import JobEnv, run_pending

    env = JobEnv(settings=app.state.settings, store=app.state.store, now=app.state.clock)
    return run_pending(app.state.db.sessionmaker, env)
