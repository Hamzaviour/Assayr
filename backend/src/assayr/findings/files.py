"""Files that show a corrective action was done, and the findings register as Excel."""

import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile, status
from fastapi.responses import FileResponse
from openpyxl import Workbook
from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from assayr.audit.service import record
from assayr.catalogue.router import FORBIDDEN, resolve_scope
from assayr.db import get_session
from assayr.documents.models import Document
from assayr.evidence.extract import sniff
from assayr.evidence.models import ArtefactVersion
from assayr.exports import add_sheet, xlsx_response
from assayr.findings.models import CorrectiveAction, CorrectiveActionFile, Finding
from assayr.findings.router import _action, _action_out, _open, _today, get_finding
from assayr.findings.schemas import ActionOut
from assayr.findings.service import can_manage, is_overdue
from assayr.identity.deps import actor_for, current_user, require
from assayr.identity.models import User
from assayr.identity.rbac import Grant, Perm
from assayr.risk.models import Risk
from assayr.storage import TooLargeError, safe_filename
from assayr.verification.av import scan_file

router = APIRouter(prefix="/findings", tags=["findings"])
HEAD_BYTES = 8192
GRADE_LABEL = {"major": "Major NC", "minor": "Minor NC", "observation": "Observation", "ofi": "OFI"}
STATUS_LABEL = {
    "open": "Open",
    "action_planned": "Action planned",
    "awaiting_verification": "Awaiting verification",
    "closed": "Closed",
}


def _may_attach(user: User, f: Finding, a: CorrectiveAction) -> bool:
    return can_manage(user, f.scope_id) or a.owner_id == user.id


def _referenced_elsewhere(db: Session, sha256: str) -> bool:
    return bool(
        db.scalar(select(exists().where(CorrectiveActionFile.sha256 == sha256)))
        or db.scalar(select(exists().where(ArtefactVersion.sha256 == sha256)))
        or db.scalar(
            select(exists().where((Document.current_sha256 == sha256) | (Document.approved_sha256 == sha256)))
        )
    )


def _scan(request: Request, db: Session, sha256: str) -> None:
    """Refuses an infected file (and drops it unless something else holds the same content)."""
    settings = request.app.state.settings
    if not settings.clamav_host:
        return
    path = request.app.state.store.path_for(sha256)
    result = scan_file(path, settings.clamav_host, settings.clamav_port)
    if result.status == "clean":
        return
    if result.status == "infected":
        if not _referenced_elsewhere(db, sha256):
            path.unlink(missing_ok=True)
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"The malware scanner flagged this file: {result.signature}.",
        )
    raise HTTPException(
        status.HTTP_503_SERVICE_UNAVAILABLE,
        "The malware scanner could not be reached. Try again in a minute.",
    )


@router.get("/export.xlsx")
def export_register(
    request: Request,
    grant: Grant = Depends(require(Perm.CONTROLS_READ)),
    db: Session = Depends(get_session),
    scope_id: uuid.UUID | None = None,
) -> Response:
    scope = resolve_scope(db, scope_id, grant)
    today = _today(request)
    findings = (
        db.scalars(select(Finding).where(Finding.scope_id == scope.id).order_by(Finding.seq)).unique().all()
    )
    workbook = Workbook()
    rows = []
    actions = []
    for f in findings:
        risk = db.get(Risk, f.risk_id) if f.risk_id else None
        rows.append(
            [
                f.code,
                f.title,
                GRADE_LABEL[f.grade],
                STATUS_LABEL[f.status],
                f.framework,
                f.ref,
                f.owner.full_name if f.owner else None,
                f.due_date,
                "Yes" if is_overdue(f.due_date, f.status == "closed", today) else "No",
                f.raised_at.date(),
                f.closed_at.date() if f.closed_at else None,
                f.root_cause,
                f.correction,
                f.response,
                f"{sum(1 for a in f.actions if a.status == 'done')} of {len(f.actions)} done",
                risk.code if risk else None,
            ]
        )
        for a in f.actions:
            actions.append(
                [
                    f.code,
                    a.seq,
                    a.description,
                    a.owner.full_name if a.owner else None,
                    a.due_date,
                    "Done" if a.status == "done" else "Open",
                    a.done_at.date() if a.done_at else None,
                    a.done_note,
                    ", ".join(x.filename for x in a.files),
                ]
            )
    add_sheet(
        workbook,
        "Findings",
        [
            "Code",
            "Title",
            "Grade",
            "Status",
            "Framework",
            "Control",
            "Owner",
            "Due date",
            "Overdue",
            "Raised",
            "Closed",
            "Root cause",
            "Correction",
            "Response",
            "Corrective actions",
            "Risk",
        ],
        rows,
    )
    add_sheet(
        workbook,
        "Corrective actions",
        ["Finding", "No.", "Action", "Owner", "Due date", "Status", "Done on", "Note", "Files"],
        actions,
    )
    return xlsx_response(workbook, "findings.xlsx")


@router.post("/{finding_id}/actions/{action_id}/files", response_model=ActionOut, status_code=201)
def upload_file(
    finding_id: uuid.UUID,
    action_id: uuid.UUID,
    request: Request,
    file: UploadFile = File(...),
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.CONTROLS_READ)),
    db: Session = Depends(get_session),
) -> ActionOut:
    f = get_finding(db, grant, finding_id)
    _open(f)
    a = _action(f, action_id)
    if not _may_attach(user, f, a):
        raise HTTPException(status.HTTP_403_FORBIDDEN, FORBIDDEN)
    settings = request.app.state.settings
    head = file.file.read(HEAD_BYTES)
    file.file.seek(0)
    try:
        blob = request.app.state.store.put(file.file, settings.max_upload_mb * 1024 * 1024)
    except TooLargeError as exc:
        raise HTTPException(413, f"The file is larger than the {settings.max_upload_mb} MB limit.") from exc
    _scan(request, db, blob.sha256)
    filename = safe_filename(file.filename or "") or "file"
    a.files.append(
        CorrectiveActionFile(
            sha256=blob.sha256,
            filename=filename,
            size=blob.size,
            mime=sniff(head, filename),
            uploaded_by_id=user.id,
        )
    )
    record(
        db,
        actor_for(request, user),
        "finding.file_add",
        "finding",
        f.code,
        diff={"action": a.seq, "filename": filename, "sha256": blob.sha256},
    )
    db.commit()
    db.refresh(f)
    return _action_out(user, f, a, _today(request))


def _file(a: CorrectiveAction, file_id: uuid.UUID) -> CorrectiveActionFile:
    x = next((x for x in a.files if x.id == file_id), None)
    if x is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "File not found.")
    return x


@router.get("/{finding_id}/actions/{action_id}/files/{file_id}")
def download_file(
    finding_id: uuid.UUID,
    action_id: uuid.UUID,
    file_id: uuid.UUID,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.CONTROLS_READ)),
    db: Session = Depends(get_session),
) -> FileResponse:
    f = get_finding(db, grant, finding_id)
    x = _file(_action(f, action_id), file_id)
    path = request.app.state.store.path_for(x.sha256)
    if not path.exists():
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "The stored file is missing. Ask an administrator to check the file store.",
        )
    record(
        db,
        actor_for(request, user),
        "finding.file_download",
        "finding",
        f.code,
        diff={"filename": x.filename},
    )
    db.commit()
    return FileResponse(
        path,
        filename=x.filename,
        media_type="application/octet-stream",
        content_disposition_type="attachment",
        headers={"X-Content-Type-Options": "nosniff"},
    )


@router.delete("/{finding_id}/actions/{action_id}/files/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_file(
    finding_id: uuid.UUID,
    action_id: uuid.UUID,
    file_id: uuid.UUID,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.CONTROLS_READ)),
    db: Session = Depends(get_session),
) -> Response:
    f = get_finding(db, grant, finding_id)
    _open(f)
    a = _action(f, action_id)
    x = _file(a, file_id)
    if a.status == "done":
        raise HTTPException(status.HTTP_409_CONFLICT, "Reopen the corrective action to remove its files.")
    if not (can_manage(user, f.scope_id) or x.uploaded_by_id == user.id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, FORBIDDEN)
    a.files.remove(x)
    record(
        db, actor_for(request, user), "finding.file_delete", "finding", f.code, diff={"filename": x.filename}
    )
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
