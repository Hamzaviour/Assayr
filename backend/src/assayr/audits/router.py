"""Internal audits: create, choose controls, record results, complete and reopen."""

import re
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from assayr.audit.service import record
from assayr.audits.models import Audit, AuditItem
from assayr.audits.schemas import (
    AddItemsIn,
    AuditDetailOut,
    AuditIn,
    AuditOut,
    AuditUpdateIn,
    ImportOut,
    ItemOut,
    ItemUpdateIn,
    ReopenIn,
    period_problem,
)
from assayr.audits.service import add_items, catalogue_rows, counts, normalise_ref, results_for
from assayr.audits.tracker import export_tracker, read_tracker
from assayr.audits.workbook import WorkbookError, export_workbook, read_workbook
from assayr.catalogue.access import check_active_user, has_perm
from assayr.catalogue.frameworks import load_soc2
from assayr.catalogue.models import Control
from assayr.catalogue.router import FORBIDDEN, resolve_scope
from assayr.catalogue.schemas import OwnerOut
from assayr.catalogue.soc2 import ActivityError, criterion_of, refresh_criterion, upsert_activity
from assayr.db import get_session
from assayr.exports import xlsx_response
from assayr.identity.deps import actor_for, current_user, get_clock, require
from assayr.identity.models import User
from assayr.identity.rbac import Grant, Perm

router = APIRouter(tags=["audits"])
NOT_FOUND = "Audit not found."
LOCKED = "This audit is completed. Reopen it to make changes."


def _person(user: User | None) -> OwnerOut | None:
    return OwnerOut(id=user.id, full_name=user.full_name) if user else None


def audit_out(user: User, audit: Audit) -> AuditOut:
    return AuditOut(
        id=audit.id,
        framework=audit.framework,
        title=audit.title,
        period_start=audit.period_start,
        period_end=audit.period_end,
        auditor=_person(audit.auditor),
        scope_note=audit.scope_note,
        conclusion=audit.conclusion,
        status=audit.status,
        completed_at=audit.completed_at,
        completed_by=_person(audit.completed_by),
        created_at=audit.created_at,
        counts=counts(audit),
        can_write=has_perm(user, audit.scope_id, Perm.AUDITS_WRITE),
        can_reopen=audit.status == "completed" and has_perm(user, audit.scope_id, Perm.CONTROLS_WRITE),
    )


def _detail(user: User, audit: Audit) -> AuditDetailOut:
    return AuditDetailOut(
        **audit_out(user, audit).model_dump(),
        items=[ItemOut.model_validate(i) for i in audit.items],
    )


def get_audit_or_404(db: Session, grant: Grant, audit_id: uuid.UUID) -> Audit:
    audit = db.get(Audit, audit_id)
    if audit is None or not grant.allows(audit.scope_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND)
    return audit


def _writable(user: User, audit: Audit) -> None:
    if not has_perm(user, audit.scope_id, Perm.AUDITS_WRITE):
        raise HTTPException(status.HTTP_403_FORBIDDEN, FORBIDDEN)
    if audit.status == "completed":
        raise HTTPException(status.HTTP_409_CONFLICT, LOCKED)


@router.get("/audits", response_model=list[AuditOut])
def list_audits(
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.CONTROLS_READ)),
    db: Session = Depends(get_session),
    scope_id: uuid.UUID | None = None,
) -> list[AuditOut]:
    scope = resolve_scope(db, scope_id, grant)
    audits = db.scalars(
        select(Audit).where(Audit.scope_id == scope.id).order_by(Audit.created_at.desc())
    ).unique()
    return [audit_out(user, a) for a in audits]


@router.post("/audits", response_model=AuditOut, status_code=status.HTTP_201_CREATED)
def create_audit(
    body: AuditIn,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.CONTROLS_READ)),
    db: Session = Depends(get_session),
    scope_id: uuid.UUID | None = None,
) -> AuditOut:
    scope = resolve_scope(db, scope_id, grant)
    if not has_perm(user, scope.id, Perm.AUDITS_WRITE):
        raise HTTPException(status.HTTP_403_FORBIDDEN, FORBIDDEN)
    auditor_id = body.auditor_id or user.id
    check_active_user(db, auditor_id, "Auditor")
    audit = Audit(scope_id=scope.id, **body.model_dump(exclude={"auditor_id"}), auditor_id=auditor_id)
    db.add(audit)
    db.flush()
    record(
        db,
        actor_for(request, user),
        "audit.create",
        "audit",
        str(audit.id),
        diff={"framework": audit.framework, "title": audit.title},
    )
    db.commit()
    db.refresh(audit)
    return audit_out(user, audit)


@router.get("/audits/{audit_id}", response_model=AuditDetailOut)
def get_audit(
    audit_id: uuid.UUID,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.CONTROLS_READ)),
    db: Session = Depends(get_session),
) -> AuditDetailOut:
    return _detail(user, get_audit_or_404(db, grant, audit_id))


@router.patch("/audits/{audit_id}", response_model=AuditOut)
def update_audit(
    audit_id: uuid.UUID,
    body: AuditUpdateIn,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.CONTROLS_READ)),
    db: Session = Depends(get_session),
) -> AuditOut:
    audit = get_audit_or_404(db, grant, audit_id)
    _writable(user, audit)
    fields = body.model_fields_set
    if "title" in fields and body.title is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "The title can not be empty.")
    if "auditor_id" in fields:
        check_active_user(db, body.auditor_id, "Auditor")
    start = body.period_start if "period_start" in fields else audit.period_start
    end = body.period_end if "period_end" in fields else audit.period_end
    problem = period_problem(audit.framework, start, end)
    if problem:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, problem)
    diff: dict[str, list] = {}
    for name in ("title", "period_start", "period_end", "auditor_id", "scope_note", "conclusion"):
        old, new = getattr(audit, name), getattr(body, name)
        if name in fields and new != old:
            diff[name] = [None if old is None else str(old), None if new is None else str(new)]
            setattr(audit, name, new)
    if diff:
        record(db, actor_for(request, user), "audit.update", "audit", str(audit.id), diff=diff)
        db.commit()
    db.refresh(audit)
    return audit_out(user, audit)


@router.post("/audits/{audit_id}/items", response_model=AuditOut)
def add_audit_items(
    audit_id: uuid.UUID,
    body: AddItemsIn,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.CONTROLS_READ)),
    db: Session = Depends(get_session),
) -> AuditOut:
    audit = get_audit_or_404(db, grant, audit_id)
    _writable(user, audit)
    rows = catalogue_rows(db, audit.scope_id, audit.framework)
    if body.domain is not None:
        wanted = body.domain.strip().lower()
        rows = [r for r in rows if wanted in (r.domain_code.lower(), r.domain.lower())]
        if not rows:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT, f"No controls in the domain {body.domain}."
            )
    elif body.refs is not None:
        by_ref = {r.ref: r for r in rows}
        refs = list(dict.fromkeys(normalise_ref(r) for r in body.refs if r.strip()))
        unknown = [r for r in refs if r not in by_ref]
        if unknown:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT, f"Not in this framework: {', '.join(unknown)}."
            )
        rows = [by_ref[r] for r in refs]
    added = add_items(db, audit, rows)
    if added:
        record(
            db, actor_for(request, user), "audit.items", "audit", str(audit.id), diff={"added": [None, added]}
        )
    db.commit()
    db.refresh(audit)
    return audit_out(user, audit)


ITEM_FIELDS = (
    "domain",
    "sub_domain",
    "assessment_area",
    "test_type",
    "requirement",
    "result",
    "notes",
    "population",
    "sample_size",
    "samples_tested",
    "exception_note",
)
RESULT_HELP = {
    "soc2": "Use one of: no exceptions, exception, not tested.",
    "other": "Use one of: pass, partial, fail, not applicable.",
}


def _check_item(audit: Audit, item: AuditItem, body: ItemUpdateIn) -> None:
    """The result must belong to the audit's framework; an exception needs a note; samples fit the sample size."""
    fields = body.model_fields_set

    def after(name):
        return getattr(body, name) if name in fields else getattr(item, name)

    result = after("result")
    if "result" in fields and result is not None and result not in results_for(audit.framework):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            RESULT_HELP["soc2" if audit.framework == "soc2" else "other"],
        )
    if result == "exception" and not (after("exception_note") or "").strip():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Describe the exception.")
    size, tested = after("sample_size"), after("samples_tested")
    if size is not None and tested is not None and tested > size:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "Samples tested can not be more than the sample size."
        )


def _item(audit: Audit, item_id: uuid.UUID) -> AuditItem:
    found = next((i for i in audit.items if i.id == item_id), None)
    if found is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "This control is not in the audit.")
    return found


@router.patch("/audits/{audit_id}/items/{item_id}", response_model=ItemOut)
def update_audit_item(
    audit_id: uuid.UUID,
    item_id: uuid.UUID,
    body: ItemUpdateIn,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.CONTROLS_READ)),
    db: Session = Depends(get_session),
) -> ItemOut:
    audit = get_audit_or_404(db, grant, audit_id)
    _writable(user, audit)
    item = _item(audit, item_id)
    fields = body.model_fields_set
    for required in ("domain", "sub_domain"):
        if required in fields and getattr(body, required) is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Domain names can not be empty.")
    _check_item(audit, item, body)
    diff: dict[str, list] = {}
    for name in ITEM_FIELDS:
        if name in fields and getattr(body, name) != getattr(item, name):
            diff[name] = [getattr(item, name), getattr(body, name)]
            setattr(item, name, getattr(body, name))
    if diff:
        if item.result and audit.status == "draft":
            audit.status = "in_progress"
        record(
            db,
            actor_for(request, user),
            "audit.result",
            "audit",
            str(audit.id),
            diff={"ref": item.ref, **diff},
        )
        db.commit()
        db.refresh(item)
    return ItemOut.model_validate(item)


@router.delete("/audits/{audit_id}/items/{item_id}", response_model=AuditOut)
def remove_audit_item(
    audit_id: uuid.UUID,
    item_id: uuid.UUID,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.CONTROLS_READ)),
    db: Session = Depends(get_session),
) -> AuditOut:
    audit = get_audit_or_404(db, grant, audit_id)
    _writable(user, audit)
    item = _item(audit, item_id)
    audit.items.remove(item)
    record(
        db,
        actor_for(request, user),
        "audit.items",
        "audit",
        str(audit.id),
        diff={"removed": [item.ref, None]},
    )
    db.commit()
    db.refresh(audit)
    return audit_out(user, audit)


@router.post("/audits/{audit_id}/complete", response_model=AuditOut)
def complete_audit(
    audit_id: uuid.UUID,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.CONTROLS_READ)),
    db: Session = Depends(get_session),
) -> AuditOut:
    audit = get_audit_or_404(db, grant, audit_id)
    _writable(user, audit)
    if not audit.items:
        raise HTTPException(status.HTTP_409_CONFLICT, "Add controls before completing this audit.")
    if audit.framework == "soc2" and not (audit.period_start and audit.period_end):
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Set the observation period before completing this audit."
        )
    untested = sum(1 for i in audit.items if not i.result)
    if untested:
        noun = "control still has" if untested == 1 else "controls still have"
        raise HTTPException(status.HTTP_409_CONFLICT, f"{untested} {noun} no result.")
    audit.status = "completed"
    audit.completed_at = get_clock(request)()
    audit.completed_by_id = user.id
    record(db, actor_for(request, user), "audit.complete", "audit", str(audit.id), diff=counts(audit))
    db.commit()
    db.refresh(audit)
    return audit_out(user, audit)


@router.post("/audits/{audit_id}/reopen", response_model=AuditOut)
def reopen_audit(
    audit_id: uuid.UUID,
    body: ReopenIn,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.CONTROLS_READ)),
    db: Session = Depends(get_session),
) -> AuditOut:
    audit = get_audit_or_404(db, grant, audit_id)
    if not has_perm(user, audit.scope_id, Perm.CONTROLS_WRITE):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only an ISMS manager can reopen a completed audit.")
    if audit.status != "completed":
        raise HTTPException(status.HTTP_409_CONFLICT, "Only a completed audit can be reopened.")
    audit.status = "in_progress"
    audit.completed_at = None
    audit.completed_by_id = None
    record(
        db,
        actor_for(request, user),
        "audit.reopen",
        "audit",
        str(audit.id),
        diff={"status": ["completed", "in_progress"]},
        reason=body.reason,
    )
    db.commit()
    db.refresh(audit)
    return audit_out(user, audit)


MAX_IMPORT_BYTES = 5 * 1024 * 1024


@router.get("/audits/{audit_id}/export.xlsx")
def export_audit(
    audit_id: uuid.UUID,
    grant: Grant = Depends(require(Perm.CONTROLS_READ)),
    db: Session = Depends(get_session),
) -> Response:
    audit = get_audit_or_404(db, grant, audit_id)
    name = re.sub(r"[^A-Za-z0-9._ -]", "", audit.title).strip() or "internal-audit"
    if audit.framework == "soc2":
        refs = [i.ref for i in audit.items]
        controls = {
            c.code: c
            for c in db.scalars(
                select(Control).where(Control.scope_id == audit.scope_id, Control.code.in_(refs))
            ).unique()
        }
        return xlsx_response(export_tracker(audit, controls), f"{name}.xlsx")
    return xlsx_response(export_workbook(audit), f"{name}.xlsx")


@router.post("/audits/import", response_model=ImportOut, status_code=status.HTTP_201_CREATED)
def import_audit(
    request: Request,
    framework: Literal["iso27001", "nia-2.1", "iso42001", "soc2"] = Form(...),
    file: UploadFile = File(...),
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.CONTROLS_READ)),
    db: Session = Depends(get_session),
    scope_id: uuid.UUID | None = None,
) -> ImportOut:
    """Creates a new audit from an existing internal audit workbook."""
    scope = resolve_scope(db, scope_id, grant)
    if not has_perm(user, scope.id, Perm.AUDITS_WRITE):
        raise HTTPException(status.HTTP_403_FORBIDDEN, FORBIDDEN)
    data = file.file.read(MAX_IMPORT_BYTES + 1)
    if len(data) > MAX_IMPORT_BYTES:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "The workbook is larger than 5 MB.")
    if framework == "soc2":
        return _import_tracker(db, request, user, scope.id, data, file.filename)
    try:
        rows, skipped = read_workbook(data)
    except WorkbookError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    catalogue = {r.ref: r for r in catalogue_rows(db, scope.id, framework)}
    if rows and not any(normalise_ref(row.ref) in catalogue for row in rows):
        label = {"nia-2.1": "NIA v2.1", "iso42001": "ISO/IEC 42001"}.get(framework, "ISO/IEC 27001")
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"None of the {len(rows)} controls in this workbook are in {label}. Check the framework you chose.",
        )
    title = (file.filename or "workbook").rsplit(".", 1)[0][:150]
    audit = Audit(scope_id=scope.id, framework=framework, title=f"Imported: {title}", auditor_id=user.id)
    db.add(audit)
    unknown: list[str] = []
    seen: set[str] = set()
    for row in rows:
        ref = normalise_ref(row.ref)
        known = catalogue.get(ref)
        if known is None:
            if ref not in unknown:
                unknown.append(ref)
            continue
        if ref in seen:
            continue
        seen.add(ref)
        audit.items.append(
            AuditItem(
                ref=ref,
                sort_order=len(seen),
                domain=(row.domain or known.domain)[:200],
                sub_domain=(row.sub_domain or row.domain or known.domain)[:200],
                assessment_area=row.assessment_area,
                test_type=row.test_type,
                requirement=row.requirement or known.requirement,
                result=row.result,
            )
        )
    if any(i.result for i in audit.items):
        audit.status = "in_progress"
    db.flush()
    record(
        db,
        actor_for(request, user),
        "audit.import",
        "audit",
        str(audit.id),
        diff={"imported": [None, len(seen)], "unknown": [None, len(unknown)]},
    )
    db.commit()
    db.refresh(audit)
    return ImportOut(
        audit=audit_out(user, audit), imported=len(seen), unknown_refs=unknown, skipped_rows=skipped
    )


def _import_tracker(
    db: Session, request: Request, user: User, scope_id: uuid.UUID, data: bytes, filename: str | None
) -> ImportOut:
    """A SOC 2 tracker: creates or refreshes the control activities, then a draft audit with their results."""
    try:
        rows, skipped = read_tracker(data)
    except WorkbookError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    criteria = set(
        db.scalars(
            select(Control.code).where(
                Control.scope_id == scope_id, Control.framework == "soc2", Control.code.not_like("%.%.%")
            )
        )
    )
    known = [r for r in rows if criterion_of(r.code) in criteria]
    unknown = [r.code for r in rows if criterion_of(r.code) not in criteria]
    if not known:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "None of the rows in this workbook are SOC 2 control numbers (like CC6.1.2).",
        )
    series = {s["ref"]: s["title"] for s in load_soc2()["series"]}
    title = (filename or "tracker").rsplit(".", 1)[0][:150]
    audit = Audit(scope_id=scope_id, framework="soc2", title=f"Imported: {title}", auditor_id=user.id)
    db.add(audit)
    now = get_clock(request)()
    for order, row in enumerate(known, start=1):
        try:
            upsert_activity(db, scope_id, row.code, row.description, row.test_procedure)
        except ActivityError as exc:
            skipped.append(str(exc))
            continue
        audit.items.append(
            AuditItem(
                ref=row.code,
                sort_order=order,
                domain=series.get(row.code.split(".")[0], row.code.split(".")[0]),
                sub_domain=criterion_of(row.code),
                assessment_area=row.test_procedure or None,
                result=row.result,
                exception_note=row.note,
            )
        )
    db.flush()
    for criterion in {criterion_of(r.code) for r in known}:
        refresh_criterion(db, scope_id, criterion, now)
    if any(i.result for i in audit.items):
        audit.status = "in_progress"
    record(
        db,
        actor_for(request, user),
        "audit.import",
        "audit",
        str(audit.id),
        diff={"imported": [None, len(audit.items)], "unknown": [None, len(unknown)]},
    )
    db.commit()
    db.refresh(audit)
    return ImportOut(
        audit=audit_out(user, audit), imported=len(audit.items), unknown_refs=unknown, skipped_rows=skipped
    )
