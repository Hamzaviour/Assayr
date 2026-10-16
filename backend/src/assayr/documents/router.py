"""Document register: policies, procedures and guidelines, their files, approval and linked controls."""

import uuid
from datetime import date, timedelta

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from assayr.audit.models import AuditLog
from assayr.audit.service import record
from assayr.catalogue.access import check_active_user, edit_rights, has_perm
from assayr.catalogue.models import Control
from assayr.catalogue.router import FORBIDDEN, _get_control, _like, resolve_scope
from assayr.db import get_session
from assayr.documents.models import Document, DocumentControl
from assayr.documents.schemas import (
    ControlDocumentOut,
    ControlDocumentsOut,
    ControlLinksIn,
    DocumentDetailOut,
    DocumentIn,
    DocumentOut,
    DocumentUpdateIn,
    HistoryOut,
    LinkedControlOut,
    document_out,
)
from assayr.evidence.extract import sniff
from assayr.identity.deps import actor_for, current_user, get_clock, require
from assayr.identity.models import User
from assayr.identity.rbac import Grant, Perm
from assayr.storage import TooLargeError, safe_filename

router = APIRouter(tags=["documents"])
NOT_FOUND = "Document not found."
REVIEW_PERIOD = timedelta(days=365)
HEAD_BYTES = 8192


def _today(request: Request) -> date:
    return get_clock(request)().date()


def _is_manager(user: User, doc: Document) -> bool:
    return has_perm(user, doc.scope_id, Perm.CONTROLS_WRITE)


def _is_owner(user: User, doc: Document) -> bool:
    return doc.owner_id is not None and doc.owner_id == user.id


def _can_edit(user: User, doc: Document) -> bool:
    """ISMS managers edit any document; owners edit their own drafts."""
    return _is_manager(user, doc) or (_is_owner(user, doc) and doc.status == "draft")


def _out(request: Request, user: User, doc: Document) -> DocumentOut:
    return document_out(doc, _today(request), _can_edit(user, doc), _is_manager(user, doc))


def _get(db: Session, grant: Grant, doc_id: uuid.UUID) -> Document:
    doc = db.get(Document, doc_id)
    if doc is None or not grant.allows(doc.scope_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND)
    return doc


def _check_code_free(db: Session, scope_id: uuid.UUID, code: str, doc_id: uuid.UUID | None = None) -> None:
    stmt = select(Document.id).where(Document.scope_id == scope_id, Document.code == code)
    if doc_id is not None:
        stmt = stmt.where(Document.id != doc_id)
    if db.scalar(stmt) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, f"A document with the reference {code} already exists.")


def next_version(label: str) -> str:
    """1.0 -> 1.1, 2.9 -> 2.10; anything else gets ".1" appended."""
    head, dot, last = label.rpartition(".")
    return f"{head}.{int(last) + 1}" if dot and last.isdigit() else f"{label}.1"


@router.get("/documents", response_model=list[DocumentOut])
def list_documents(
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.CONTROLS_READ)),
    db: Session = Depends(get_session),
    scope_id: uuid.UUID | None = None,
    type_: str | None = Query(None, alias="type", max_length=20),
    q: str | None = Query(None, max_length=100),
) -> list[DocumentOut]:
    scope = resolve_scope(db, scope_id, grant)
    stmt = select(Document).where(Document.scope_id == scope.id)
    if type_:
        stmt = stmt.where(Document.doc_type == type_)
    if q and q.strip():
        like = _like(q.strip())
        stmt = stmt.where(
            or_(
                func.lower(Document.title).like(like, escape="\\"),
                func.lower(Document.code).like(like, escape="\\"),
            )
        )
    docs = db.scalars(stmt.order_by(Document.doc_type, Document.code)).unique()
    return [_out(request, user, d) for d in docs]


@router.post("/documents", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
def create_document(
    body: DocumentIn,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.CONTROLS_READ)),
    db: Session = Depends(get_session),
    scope_id: uuid.UUID | None = None,
) -> DocumentOut:
    scope = resolve_scope(db, scope_id, grant)
    if not has_perm(user, scope.id, Perm.DOCUMENTS_CREATE):
        raise HTTPException(status.HTTP_403_FORBIDDEN, FORBIDDEN)
    owner_id = body.owner_id or user.id
    if owner_id != user.id and not has_perm(user, scope.id, Perm.CONTROLS_WRITE):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only an ISMS manager can set another owner.")
    check_active_user(db, owner_id)
    code = body.code.upper()
    _check_code_free(db, scope.id, code)
    doc = Document(
        scope_id=scope.id,
        doc_type=body.doc_type,
        code=code,
        title=body.title,
        description=body.description,
        owner_id=owner_id,
    )
    db.add(doc)
    db.flush()
    record(
        db,
        actor_for(request, user),
        "document.create",
        "document",
        str(doc.id),
        diff={"code": code, "type": doc.doc_type, "title": doc.title},
    )
    db.commit()
    db.refresh(doc)
    return _out(request, user, doc)


@router.get("/documents/{doc_id}", response_model=DocumentDetailOut)
def get_document(
    doc_id: uuid.UUID,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.CONTROLS_READ)),
    db: Session = Depends(get_session),
) -> DocumentDetailOut:
    doc = _get(db, grant, doc_id)
    return _detail(db, request, user, doc)


def _detail(db: Session, request: Request, user: User, doc: Document) -> DocumentDetailOut:
    controls = db.scalars(
        select(Control)
        .join(DocumentControl, DocumentControl.control_id == Control.id)
        .where(DocumentControl.document_id == doc.id)
        .order_by(Control.sort_order)
    )
    history = db.scalars(
        select(AuditLog)
        .where(AuditLog.entity_type == "document", AuditLog.entity_id == str(doc.id))
        .order_by(AuditLog.seq.desc())
        .limit(50)
    )
    return DocumentDetailOut(
        **_out(request, user, doc).model_dump(),
        controls=[LinkedControlOut(code=c.code, title=c.title, status=c.status) for c in controls],
        history=[HistoryOut(at=h.at, actor=h.actor_email, action=h.action) for h in history],
    )


@router.patch("/documents/{doc_id}", response_model=DocumentOut)
def update_document(
    doc_id: uuid.UUID,
    body: DocumentUpdateIn,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.CONTROLS_READ)),
    db: Session = Depends(get_session),
) -> DocumentOut:
    doc = _get(db, grant, doc_id)
    if not _can_edit(user, doc):
        raise HTTPException(status.HTTP_403_FORBIDDEN, FORBIDDEN)
    fields = body.model_fields_set
    manager_only = {"owner_id", "review_due", "status"} & fields
    if manager_only and not _is_manager(user, doc):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Only an ISMS manager can change the owner, review date or status."
        )
    diff: dict[str, list] = {}
    if "owner_id" in fields and body.owner_id != doc.owner_id:
        check_active_user(db, body.owner_id)
        diff["owner_id"] = [
            str(doc.owner_id) if doc.owner_id else None,
            str(body.owner_id) if body.owner_id else None,
        ]
        doc.owner_id = body.owner_id
    if "code" in fields and body.code is not None and body.code.upper() != doc.code:
        code = body.code.upper()
        _check_code_free(db, doc.scope_id, code, doc.id)
        diff["code"] = [doc.code, code]
        doc.code = code
    for name in ("doc_type", "title", "description", "review_due", "status"):
        if name not in fields:
            continue
        value = getattr(body, name)
        if value is None and name in {"doc_type", "title", "status"}:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                f"{name.replace('_', ' ').capitalize()} can't be empty.",
            )
        if value != getattr(doc, name):
            diff[name] = [
                str(getattr(doc, name)) if getattr(doc, name) is not None else None,
                str(value) if value is not None else None,
            ]
            setattr(doc, name, value)
    if diff:
        record(db, actor_for(request, user), "document.update", "document", str(doc.id), diff=diff)
        db.commit()
    db.refresh(doc)
    return _out(request, user, doc)


@router.post("/documents/{doc_id}/approve", response_model=DocumentOut)
def approve_document(
    doc_id: uuid.UUID,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.CONTROLS_READ)),
    db: Session = Depends(get_session),
) -> DocumentOut:
    doc = _get(db, grant, doc_id)
    if not _is_manager(user, doc):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only an ISMS manager can approve documents.")
    if doc.status != "draft":
        raise HTTPException(status.HTTP_409_CONFLICT, "Only a draft can be approved.")
    now = get_clock(request)()
    doc.status = "approved"
    doc.approved_by_id = user.id
    doc.approved_at = now
    doc.review_due = now.date() + REVIEW_PERIOD
    doc.approved_version = doc.version_label
    doc.approved_sha256 = doc.current_sha256
    doc.approved_filename = doc.filename
    record(
        db,
        actor_for(request, user),
        "document.approve",
        "document",
        str(doc.id),
        diff={"version": doc.version_label, "review_due": doc.review_due.isoformat()},
    )
    db.commit()
    db.refresh(doc)
    return _out(request, user, doc)


@router.post("/documents/{doc_id}/file", response_model=DocumentOut)
def upload_document_file(
    doc_id: uuid.UUID,
    request: Request,
    file: UploadFile = File(...),
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.CONTROLS_READ)),
    db: Session = Depends(get_session),
) -> DocumentOut:
    """A new file for an approved document starts the next draft version."""
    doc = _get(db, grant, doc_id)
    if not (_is_manager(user, doc) or _is_owner(user, doc)) or doc.status == "retired":
        raise HTTPException(status.HTTP_403_FORBIDDEN, FORBIDDEN)
    settings = request.app.state.settings
    head = file.file.read(HEAD_BYTES)
    file.file.seek(0)
    try:
        blob = request.app.state.store.put(file.file, settings.max_upload_mb * 1024 * 1024)
    except TooLargeError as exc:
        raise HTTPException(413, f"The file is larger than the {settings.max_upload_mb} MB limit.") from exc
    filename = safe_filename(file.filename or "")
    diff: dict[str, list] = {
        "filename": [doc.filename, filename],
        "sha256": [doc.current_sha256, blob.sha256],
    }
    if doc.status == "approved":
        new_label = next_version(doc.version_label)
        diff["version"] = [doc.version_label, new_label]
        diff["status"] = ["approved", "draft"]
        doc.version_label = new_label
        doc.status = "draft"
        doc.approved_by_id = None
        doc.approved_at = None
    doc.current_sha256 = blob.sha256
    doc.filename = filename
    doc.mime = sniff(head, filename)
    doc.size = blob.size
    record(db, actor_for(request, user), "document.file", "document", str(doc.id), diff=diff)
    db.commit()
    db.refresh(doc)
    return _out(request, user, doc)


@router.get("/documents/{doc_id}/file")
def download_document_file(
    doc_id: uuid.UUID,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.CONTROLS_READ)),
    db: Session = Depends(get_session),
    approved: bool = False,
) -> FileResponse:
    """The current file, or with ?approved=true the file of the last approved version."""
    doc = _get(db, grant, doc_id)
    sha256, filename = (
        (doc.approved_sha256, doc.approved_filename) if approved else (doc.current_sha256, doc.filename)
    )
    if sha256 is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "No approved file yet." if approved else "This document has no file yet.",
        )
    path = request.app.state.store.path_for(sha256)
    if not path.exists():
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "The stored file is missing. Ask an administrator to check the file store.",
        )
    record(
        db,
        actor_for(request, user),
        "document.download",
        "document",
        str(doc.id),
        diff={"filename": filename, "approved": approved},
    )
    db.commit()
    return FileResponse(
        path,
        filename=filename or "document",
        media_type="application/octet-stream",
        content_disposition_type="attachment",
        headers={"X-Content-Type-Options": "nosniff"},
    )


@router.put("/documents/{doc_id}/controls", response_model=DocumentDetailOut)
def set_document_controls(
    doc_id: uuid.UUID,
    body: ControlLinksIn,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.CONTROLS_READ)),
    db: Session = Depends(get_session),
) -> DocumentDetailOut:
    doc = _get(db, grant, doc_id)
    if not (_is_manager(user, doc) or _is_owner(user, doc)):
        raise HTTPException(status.HTTP_403_FORBIDDEN, FORBIDDEN)
    codes = list(dict.fromkeys(body.codes))
    controls = {
        c.code: c
        for c in db.scalars(select(Control).where(Control.scope_id == doc.scope_id, Control.code.in_(codes)))
    }
    unknown = [code for code in codes if code not in controls]
    if unknown:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, f"Unknown control(s): {', '.join(unknown)}."
        )
    before = sorted(
        db.scalars(
            select(Control.code)
            .join(DocumentControl, DocumentControl.control_id == Control.id)
            .where(DocumentControl.document_id == doc.id)
        )
    )
    db.execute(delete(DocumentControl).where(DocumentControl.document_id == doc.id))
    db.add_all(DocumentControl(document_id=doc.id, control_id=controls[code].id) for code in codes)
    db.flush()
    record(
        db,
        actor_for(request, user),
        "document.controls",
        "document",
        str(doc.id),
        diff={"controls": [before, sorted(codes)]},
    )
    db.commit()
    return _detail(db, request, user, doc)


def _control_documents(db: Session, control: Control, today: date) -> ControlDocumentsOut:
    docs = db.scalars(
        select(Document)
        .join(DocumentControl, DocumentControl.document_id == Document.id)
        .where(DocumentControl.control_id == control.id)
        .order_by(Document.code)
    ).unique()
    grouped: dict[str, list[ControlDocumentOut]] = {"policy": [], "procedure": [], "guideline": []}
    for d in docs:
        row = ControlDocumentOut.model_validate(d, from_attributes=True)
        row.review_overdue = d.status == "approved" and d.review_due is not None and d.review_due < today
        grouped[d.doc_type].append(row)
    return ControlDocumentsOut(**grouped)


@router.get("/controls/{code}/documents", response_model=ControlDocumentsOut)
def list_control_documents(
    code: str,
    request: Request,
    grant: Grant = Depends(require(Perm.CONTROLS_READ)),
    db: Session = Depends(get_session),
    scope_id: uuid.UUID | None = None,
) -> ControlDocumentsOut:
    scope = resolve_scope(db, scope_id, grant)
    return _control_documents(db, _get_control(db, scope, code), _today(request))


def _link_target(
    db: Session, user: User, grant: Grant, scope_id: uuid.UUID | None, code: str, doc_id: uuid.UUID
) -> tuple[Control, Document]:
    scope = resolve_scope(db, scope_id, grant)
    control = _get_control(db, scope, code)
    doc = _get(db, grant, doc_id)
    if doc.scope_id != scope.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND)
    if not (
        _is_manager(user, doc) or _is_owner(user, doc) or edit_rights(user, scope.id, control.owner_id).any
    ):
        raise HTTPException(status.HTTP_403_FORBIDDEN, FORBIDDEN)
    return control, doc


@router.post("/controls/{code}/documents/{doc_id}", response_model=ControlDocumentsOut)
def link_control_document(
    code: str,
    doc_id: uuid.UUID,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.CONTROLS_READ)),
    db: Session = Depends(get_session),
    scope_id: uuid.UUID | None = None,
) -> ControlDocumentsOut:
    control, doc = _link_target(db, user, grant, scope_id, code, doc_id)
    if db.get(DocumentControl, (doc.id, control.id)) is None:
        db.add(DocumentControl(document_id=doc.id, control_id=control.id))
        record(
            db,
            actor_for(request, user),
            "document.link",
            "document",
            str(doc.id),
            diff={"control": control.code},
        )
        db.commit()
    return _control_documents(db, control, _today(request))


@router.delete("/controls/{code}/documents/{doc_id}", response_model=ControlDocumentsOut)
def unlink_control_document(
    code: str,
    doc_id: uuid.UUID,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.CONTROLS_READ)),
    db: Session = Depends(get_session),
    scope_id: uuid.UUID | None = None,
) -> ControlDocumentsOut:
    control, doc = _link_target(db, user, grant, scope_id, code, doc_id)
    link = db.get(DocumentControl, (doc.id, control.id))
    if link is not None:
        db.delete(link)
        record(
            db,
            actor_for(request, user),
            "document.unlink",
            "document",
            str(doc.id),
            diff={"control": control.code},
        )
        db.commit()
    return _control_documents(db, control, _today(request))
