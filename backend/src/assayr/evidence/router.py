import uuid
from datetime import date

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from assayr.audit.service import record
from assayr.catalogue.access import edit_rights
from assayr.catalogue.models import Control, EvidenceSlot
from assayr.catalogue.router import FORBIDDEN, _get_control, resolve_scope
from assayr.db import get_session
from assayr.evidence.extract import sniff
from assayr.evidence.models import Artefact, ArtefactLink, ArtefactVersion, RuleResult, VerificationRun
from assayr.evidence.schemas import DecisionIn, LinkOut, ReviewItemOut, latest_run, link_out, review_item
from assayr.identity.deps import actor_for, current_user, get_clock, require
from assayr.identity.models import User
from assayr.identity.rbac import Grant, Perm
from assayr.jobs import enqueue
from assayr.scoring.service import recompute_control
from assayr.storage import TooLargeError, safe_filename
from assayr.verification.engine import set_expiry, supersede_older

router = APIRouter(tags=["evidence"])
NOT_FOUND = "Evidence not found."
SAFETY_RULES = ("V-FMT", "V-AV")


def failed_safety_check(db: Session, version_id: uuid.UUID) -> bool:
    """True when any check of this file found it unreadable as evidence or flagged it as malware (quarantine)."""
    count = db.scalar(
        select(func.count())
        .select_from(RuleResult)
        .join(VerificationRun, RuleResult.run_id == VerificationRun.id)
        .join(ArtefactLink, VerificationRun.link_id == ArtefactLink.id)
        .where(
            ArtefactLink.version_id == version_id,
            RuleResult.code.in_(SAFETY_RULES),
            RuleResult.status == "fail",
        )
    )
    return bool(count)


HEAD_BYTES = 8192


@router.post("/controls/{code}/slots/{slot_id}/artefacts", response_model=LinkOut, status_code=202)
def upload_evidence(
    code: str,
    slot_id: uuid.UUID,
    request: Request,
    file: UploadFile = File(...),
    title: str | None = Form(None, max_length=300),
    evidence_date: date | None = Form(None),
    artefact_id: uuid.UUID | None = Form(None),
    scope_id: uuid.UUID | None = None,
    user: User = Depends(current_user),
    read_grant: Grant = Depends(require(Perm.CONTROLS_READ)),
    db: Session = Depends(get_session),
) -> LinkOut:
    settings = request.app.state.settings
    store = request.app.state.store
    now = get_clock(request)()
    scope = resolve_scope(db, scope_id, read_grant)
    control = _get_control(db, scope, code)
    if not edit_rights(user, scope.id, control.owner_id).any:
        raise HTTPException(status.HTTP_403_FORBIDDEN, FORBIDDEN)
    slot = db.get(EvidenceSlot, slot_id)
    if slot is None or slot.control_id != control.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Evidence slot not found.")
    if evidence_date and evidence_date > now.date():
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "The evidence date can't be in the future."
        )
    if artefact_id is not None:
        artefact = db.get(Artefact, artefact_id)
        if artefact is None or artefact.scope_id != scope.id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Artefact not found.")
    head = file.file.read(HEAD_BYTES)
    file.file.seek(0)
    try:
        blob = store.put(file.file, settings.max_upload_mb * 1024 * 1024)
    except TooLargeError as exc:
        raise HTTPException(413, f"The file is larger than the {settings.max_upload_mb} MB limit.") from exc
    filename = safe_filename(file.filename or "")
    if artefact_id is None:
        artefact = Artefact(scope_id=scope.id, title=(title or filename)[:300], uploaded_by_id=user.id)
        db.add(artefact)
    version = ArtefactVersion(
        version_no=max((v.version_no for v in artefact.versions), default=0) + 1,
        sha256=blob.sha256,
        size=blob.size,
        filename=filename,
        mime=sniff(head, filename),
        evidence_date=evidence_date,
        uploaded_by_id=user.id,
        created_at=now,
    )
    artefact.versions.append(version)
    db.flush()
    link = ArtefactLink(version_id=version.id, slot_id=slot.id, state="verifying", created_at=now)
    db.add(link)
    db.flush()
    enqueue(db, "verify_link", {"link_id": str(link.id)}, now)
    record(
        db,
        actor_for(request, user),
        "evidence.upload",
        "artefact_link",
        str(link.id),
        diff={
            "control": control.code,
            "slot": slot.name,
            "filename": filename,
            "sha256": blob.sha256,
            "size": blob.size,
        },
    )
    recompute_control(db, control, now, settings, trigger=f"Evidence uploaded: {filename}")
    db.commit()
    db.refresh(link)
    return link_out(db, link)


@router.get("/artefact-links/{link_id}", response_model=LinkOut)
def get_link(
    link_id: uuid.UUID,
    grant: Grant = Depends(require(Perm.CONTROLS_READ)),
    db: Session = Depends(get_session),
) -> LinkOut:
    link = db.get(ArtefactLink, link_id)
    if link is None or not grant.allows(link.slot.control.scope_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND)
    return link_out(db, link)


@router.get("/artefact-versions/{version_id}/download")
def download_version(
    version_id: uuid.UUID,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.CONTROLS_READ)),
    db: Session = Depends(get_session),
) -> FileResponse:
    version = db.get(ArtefactVersion, version_id)
    if version is None or not grant.allows(version.artefact.scope_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND)
    if failed_safety_check(db, version.id):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "This file failed the file-type or malware check, so it can't be downloaded.",
        )
    path = request.app.state.store.path_for(version.sha256)
    if not path.exists():
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "The stored file is missing. Ask an administrator to check the evidence store.",
        )
    record(
        db,
        actor_for(request, user),
        "evidence.download",
        "artefact_version",
        str(version.id),
        diff={"filename": version.filename},
    )
    db.commit()
    return FileResponse(
        path,
        filename=version.filename,
        media_type="application/octet-stream",
        content_disposition_type="attachment",
        headers={"X-Content-Type-Options": "nosniff"},
    )


@router.get("/review-queue", response_model=list[ReviewItemOut])
def review_queue(
    grant: Grant = Depends(require(Perm.EVIDENCE_REVIEW)),
    db: Session = Depends(get_session),
    scope_id: uuid.UUID | None = None,
) -> list[ReviewItemOut]:
    scope = resolve_scope(db, scope_id, grant)
    links = db.scalars(
        select(ArtefactLink)
        .join(EvidenceSlot, ArtefactLink.slot_id == EvidenceSlot.id)
        .join(Control, EvidenceSlot.control_id == Control.id)
        .where(Control.scope_id == scope.id, ArtefactLink.state == "in_review")
        .order_by(ArtefactLink.created_at)
    ).unique()
    return [review_item(db, link) for link in links]


_DECISION_FROM = {"accept": {"in_review", "rejected"}, "reject": {"in_review"}}


@router.post("/artefact-links/{link_id}/decision", response_model=LinkOut)
def decide_link(
    link_id: uuid.UUID,
    body: DecisionIn,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.EVIDENCE_REVIEW)),
    db: Session = Depends(get_session),
) -> LinkOut:
    link = db.get(ArtefactLink, link_id)
    if link is None or not grant.allows(link.slot.control.scope_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND)
    if link.version.uploaded_by_id == user.id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "You can't review evidence you uploaded. Ask another reviewer."
        )
    if link.state not in _DECISION_FROM[body.decision]:
        raise HTTPException(status.HTTP_409_CONFLICT, "This evidence already has a final decision.")
    if body.decision == "accept" and failed_safety_check(db, link.version_id):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "This file failed the file-type or malware check and can't be accepted. Ask for a new upload.",
        )
    reason = (body.reason or "").strip()
    run = latest_run(db, link)
    flagged = run is not None and any(r.status in ("fail", "warn") for r in run.results)
    unchecked = run is None or run.confidence is None
    if body.decision == "reject" and not reason:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "Give a reason so the uploader knows what to fix."
        )
    if body.decision == "accept" and not reason:
        if flagged or link.state == "rejected":
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "Some checks failed or raised warnings. Give a reason for accepting anyway.",
            )
        if unchecked:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "None of the content checks could run on this file. Say what you checked.",
            )
    now = get_clock(request)()
    before = link.state
    link.state = "accepted" if body.decision == "accept" else "rejected"
    link.decided_by_id = user.id
    link.decided_at = now
    link.decision_reason = reason or None
    set_expiry(link)
    if link.state == "accepted":
        supersede_older(db, link)
    record(
        db,
        actor_for(request, user),
        "evidence.decision",
        "artefact_link",
        str(link.id),
        diff={"state": [before, link.state]},
        reason=reason or None,
    )
    verb = "accepted" if link.state == "accepted" else "rejected"
    recompute_control(
        db,
        link.slot.control,
        now,
        request.app.state.settings,
        trigger=f"Reviewer {verb} {link.version.filename}",
    )
    db.commit()
    return link_out(db, link)
