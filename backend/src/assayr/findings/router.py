"""Findings: raise from audit rows, plan corrective actions, verify effectiveness, close and reopen."""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from assayr.audit.service import record
from assayr.audits.models import Audit, AuditItem
from assayr.catalogue.access import check_active_user, has_perm
from assayr.catalogue.router import FORBIDDEN, resolve_scope
from assayr.catalogue.schemas import OwnerOut
from assayr.db import get_session
from assayr.findings.models import GRADES, STATUSES, CorrectiveAction, Finding, FindingVerification
from assayr.findings.schemas import (
    ActionIn,
    ActionOut,
    ActionUpdateIn,
    CloseIn,
    FileOut,
    FindingDetailOut,
    FindingIn,
    FindingOut,
    FindingUpdateIn,
    Link,
    RaiseIn,
    RaiseOut,
    ReasonIn,
    RiskLink,
    SummaryOut,
    VerificationOut,
    VerifyIn,
)
from assayr.findings.service import (
    NOT_RAISABLE,
    RAISABLE,
    can_edit_capa,
    can_manage,
    is_overdue,
    raise_from_item,
    refresh_status,
    summarize,
    verify_problem,
)
from assayr.identity.deps import actor_for, current_user, get_clock, require
from assayr.identity.models import User
from assayr.identity.rbac import Grant, Perm
from assayr.risk.models import Risk
from assayr.risk.service import next_risk_code

router = APIRouter(prefix="/findings", tags=["findings"])
audits_router = APIRouter(prefix="/audits", tags=["findings"])
NOT_FOUND = "Finding not found."
CLOSED = "This finding is closed. Reopen it to make changes."
CAPA_FIELDS = {"root_cause", "correction", "response"}


def _person(u: User | None) -> OwnerOut | None:
    return OwnerOut(id=u.id, full_name=u.full_name) if u else None


def _today(request: Request) -> date:
    return get_clock(request)().date()


def finding_out(db: Session, f: Finding, today: date) -> FindingOut:
    audit = db.get(Audit, f.audit_id) if f.audit_id else None
    risk = db.get(Risk, f.risk_id) if f.risk_id else None
    return FindingOut(
        id=f.id,
        code=f.code,
        title=f.title,
        grade=f.grade,
        status=f.status,
        source=f.source,
        framework=f.framework,
        ref=f.ref,
        owner=_person(f.owner),
        due_date=f.due_date,
        overdue=is_overdue(f.due_date, f.status == "closed", today),
        audit=Link(id=audit.id, title=audit.title) if audit else None,
        audit_item_id=f.audit_item_id,
        actions_open=sum(1 for a in f.actions if a.status == "open"),
        actions_total=len(f.actions),
        risk=RiskLink(id=risk.id, code=risk.code) if risk else None,
        raised_at=f.raised_at,
        closed_at=f.closed_at,
    )


def _action_out(user: User, f: Finding, a: CorrectiveAction, today: date) -> ActionOut:
    open_finding = f.status != "closed"
    return ActionOut(
        id=a.id,
        seq=a.seq,
        description=a.description,
        owner=_person(a.owner),
        due_date=a.due_date,
        status=a.status,
        overdue=is_overdue(a.due_date, a.status == "done", today),
        done_at=a.done_at,
        done_note=a.done_note,
        files=[
            FileOut(
                id=x.id,
                filename=x.filename,
                size=x.size,
                uploaded_by=_person(x.uploaded_by),
                uploaded_at=x.uploaded_at,
            )
            for x in a.files
        ],
        can_edit=can_edit_capa(user, f),
        can_complete=open_finding and (can_manage(user, f.scope_id) or a.owner_id == user.id),
    )


def detail_out(db: Session, user: User, f: Finding, today: date) -> FindingDetailOut:
    manage = can_manage(user, f.scope_id)
    is_open = f.status != "closed"
    return FindingDetailOut(
        **finding_out(db, f, today).model_dump(),
        description=f.description,
        root_cause=f.root_cause,
        correction=f.correction,
        response=f.response,
        raised_by=_person(f.raised_by),
        actions=[_action_out(user, f, a, today) for a in f.actions],
        verifications=[
            VerificationOut(
                verifier=_person(v.verifier), effective=v.effective, note=v.note, verified_at=v.verified_at
            )
            for v in f.verifications
        ],
        can_edit=manage and is_open,
        can_edit_capa=can_edit_capa(user, f),
        can_add_action=can_edit_capa(user, f),
        can_verify=verify_problem(user, f) is None,
        can_close=is_open and not f.is_nonconformity and (manage or f.owner_id == user.id),
        can_reopen=not is_open and has_perm(user, f.scope_id, Perm.CONTROLS_WRITE),
        can_raise_risk=manage and f.risk_id is None,
    )


def get_finding(db: Session, grant: Grant, finding_id: uuid.UUID) -> Finding:
    f = db.get(Finding, finding_id)
    if f is None or not grant.allows(f.scope_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND)
    return f


def _action(f: Finding, action_id: uuid.UUID) -> CorrectiveAction:
    a = next((a for a in f.actions if a.id == action_id), None)
    if a is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Corrective action not found.")
    return a


def _open(f: Finding) -> None:
    if f.status == "closed":
        raise HTTPException(status.HTTP_409_CONFLICT, CLOSED)


def _done(db: Session, request: Request, user: User, f: Finding, action: str, **extra) -> FindingDetailOut:
    record(db, actor_for(request, user), action, "finding", f.code, **extra)
    db.commit()
    db.refresh(f)
    return detail_out(db, user, f, _today(request))


@router.get("", response_model=list[FindingOut])
def list_findings(
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.CONTROLS_READ)),
    db: Session = Depends(get_session),
    scope_id: uuid.UUID | None = None,
    status_: str | None = Query(None, alias="status"),
    grade: str | None = None,
    owner: str | None = None,
    overdue: bool = False,
    audit_id: uuid.UUID | None = None,
    framework: str | None = None,
) -> list[FindingOut]:
    scope = resolve_scope(db, scope_id, grant)
    stmt = select(Finding).where(Finding.scope_id == scope.id).order_by(Finding.seq)
    if status_ in STATUSES:
        stmt = stmt.where(Finding.status == status_)
    if grade in GRADES:
        stmt = stmt.where(Finding.grade == grade)
    if owner == "me":
        stmt = stmt.where(Finding.owner_id == user.id)
    elif owner == "none":
        stmt = stmt.where(Finding.owner_id.is_(None))
    elif owner:
        try:
            stmt = stmt.where(Finding.owner_id == uuid.UUID(owner))
        except ValueError:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Unknown owner filter.") from None
    if audit_id:
        stmt = stmt.where(Finding.audit_id == audit_id)
    if framework:
        stmt = stmt.where(Finding.framework == framework)
    today = _today(request)
    rows = [finding_out(db, f, today) for f in db.scalars(stmt).unique()]
    return [r for r in rows if r.overdue] if overdue else rows


@router.get("/summary", response_model=SummaryOut)
def summary(
    request: Request,
    grant: Grant = Depends(require(Perm.CONTROLS_READ)),
    db: Session = Depends(get_session),
    scope_id: uuid.UUID | None = None,
) -> SummaryOut:
    scope = resolve_scope(db, scope_id, grant)
    return SummaryOut(**summarize(db, scope.id, _today(request)))


@router.post("", response_model=FindingDetailOut, status_code=status.HTTP_201_CREATED)
def create_finding(
    body: FindingIn,
    request: Request,
    response: Response,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.CONTROLS_READ)),
    db: Session = Depends(get_session),
) -> FindingDetailOut:
    item = db.get(AuditItem, body.audit_item_id)
    if item is None or not grant.allows(item.audit.scope_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Audit row not found.")
    audit = item.audit
    if not can_manage(user, audit.scope_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, FORBIDDEN)
    check_active_user(db, body.owner_id)
    overrides = body.model_dump(exclude={"audit_item_id"}, exclude_unset=True)
    try:
        f, created = raise_from_item(db, audit, item, user, get_clock(request)(), **overrides)
    except ValueError:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, NOT_RAISABLE) from None
    if not created:
        response.status_code = status.HTTP_200_OK
        return detail_out(db, user, f, _today(request))
    return _done(
        db, request, user, f, "finding.raise", diff={"ref": f.ref, "grade": f.grade, "audit": audit.title}
    )


@router.get("/{finding_id}", response_model=FindingDetailOut)
def get_one(
    finding_id: uuid.UUID,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.CONTROLS_READ)),
    db: Session = Depends(get_session),
) -> FindingDetailOut:
    return detail_out(db, user, get_finding(db, grant, finding_id), _today(request))


@router.patch("/{finding_id}", response_model=FindingDetailOut)
def update_finding(
    finding_id: uuid.UUID,
    body: FindingUpdateIn,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.CONTROLS_READ)),
    db: Session = Depends(get_session),
) -> FindingDetailOut:
    f = get_finding(db, grant, finding_id)
    _open(f)
    fields = body.model_fields_set
    manage = can_manage(user, f.scope_id)
    if not manage and not (f.owner_id == user.id and fields <= CAPA_FIELDS):
        raise HTTPException(status.HTTP_403_FORBIDDEN, FORBIDDEN)
    for required in ("title", "grade"):
        if required in fields and getattr(body, required) is None:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT, f"{required.capitalize()} can not be empty."
            )
    if "owner_id" in fields:
        check_active_user(db, body.owner_id)
    diff: dict[str, list] = {}
    for name in fields:
        new = getattr(body, name)
        if isinstance(new, str):
            new = new.strip() or None
        old = getattr(f, name)
        if new != old:
            diff[name] = [None if old is None else str(old), None if new is None else str(new)]
            setattr(f, name, new)
    if not diff:
        return detail_out(db, user, f, _today(request))
    refresh_status(f)
    return _done(db, request, user, f, "finding.update", diff=diff)


@router.post("/{finding_id}/actions", response_model=ActionOut, status_code=status.HTTP_201_CREATED)
def add_action(
    finding_id: uuid.UUID,
    body: ActionIn,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.CONTROLS_READ)),
    db: Session = Depends(get_session),
) -> ActionOut:
    f = get_finding(db, grant, finding_id)
    _open(f)
    if not can_edit_capa(user, f):
        raise HTTPException(status.HTTP_403_FORBIDDEN, FORBIDDEN)
    check_active_user(db, body.owner_id)
    a = CorrectiveAction(
        seq=max((x.seq for x in f.actions), default=0) + 1,
        description=body.description.strip(),
        owner_id=body.owner_id,
        due_date=body.due_date,
        status="open",
    )
    f.actions.append(a)
    db.flush()
    refresh_status(f)
    record(db, actor_for(request, user), "finding.action_add", "finding", f.code, diff={"action": a.seq})
    db.commit()
    db.refresh(f)
    return _action_out(user, f, a, _today(request))


@router.patch("/{finding_id}/actions/{action_id}", response_model=ActionOut)
def update_action(
    finding_id: uuid.UUID,
    action_id: uuid.UUID,
    body: ActionUpdateIn,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.CONTROLS_READ)),
    db: Session = Depends(get_session),
) -> ActionOut:
    f = get_finding(db, grant, finding_id)
    _open(f)
    a = _action(f, action_id)
    fields = body.model_fields_set
    plan_fields = {"description", "owner_id", "due_date"}
    if fields & plan_fields and not can_edit_capa(user, f):
        raise HTTPException(status.HTTP_403_FORBIDDEN, FORBIDDEN)
    if fields - plan_fields and not (can_manage(user, f.scope_id) or a.owner_id == user.id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, FORBIDDEN)
    if "owner_id" in fields:
        check_active_user(db, body.owner_id)
    if "description" in fields and body.description is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Description can not be empty.")
    note = a.done_note
    if "done_note" in fields:
        note = (body.done_note or "").strip() or None
    if body.status == "done" and a.status != "done" and not note and not a.files:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "Add a note or a file showing what was done."
        )
    for name in fields & plan_fields:
        value = getattr(body, name)
        setattr(a, name, value.strip() if isinstance(value, str) else value)
    a.done_note = note
    if "status" in fields and body.status and body.status != a.status:
        a.status = body.status
        a.done_at = get_clock(request)() if body.status == "done" else None
    db.flush()
    refresh_status(f)
    record(
        db,
        actor_for(request, user),
        "finding.action_update",
        "finding",
        f.code,
        diff={"action": a.seq, "fields": sorted(fields)},
    )
    db.commit()
    db.refresh(f)
    return _action_out(user, f, a, _today(request))


@router.delete("/{finding_id}/actions/{action_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_action(
    finding_id: uuid.UUID,
    action_id: uuid.UUID,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.CONTROLS_READ)),
    db: Session = Depends(get_session),
) -> Response:
    f = get_finding(db, grant, finding_id)
    _open(f)
    a = _action(f, action_id)
    if not can_edit_capa(user, f):
        raise HTTPException(status.HTTP_403_FORBIDDEN, FORBIDDEN)
    if a.status == "done":
        raise HTTPException(status.HTTP_409_CONFLICT, "A completed corrective action can not be deleted.")
    f.actions.remove(a)
    db.flush()
    refresh_status(f)
    record(db, actor_for(request, user), "finding.action_delete", "finding", f.code, diff={"action": a.seq})
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{finding_id}/verify", response_model=FindingDetailOut)
def verify(
    finding_id: uuid.UUID,
    body: VerifyIn,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.CONTROLS_READ)),
    db: Session = Depends(get_session),
) -> FindingDetailOut:
    f = get_finding(db, grant, finding_id)
    _open(f)
    problem = verify_problem(user, f)
    if problem:
        raise HTTPException(*problem)
    note = body.note.strip()
    if not note:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Describe what you checked.")
    now = get_clock(request)()
    f.verifications.append(
        FindingVerification(verifier_id=user.id, effective=body.effective, note=note, verified_at=now)
    )
    if body.effective:
        f.status = "closed"
        f.closed_at = now
    else:
        f.status = "action_planned"
    db.flush()
    refresh_status(f)
    return _done(db, request, user, f, "finding.verify", diff={"effective": body.effective}, reason=note)


@router.post("/{finding_id}/close", response_model=FindingDetailOut)
def close(
    finding_id: uuid.UUID,
    body: CloseIn,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.CONTROLS_READ)),
    db: Session = Depends(get_session),
) -> FindingDetailOut:
    f = get_finding(db, grant, finding_id)
    _open(f)
    if f.is_nonconformity:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Major and minor nonconformities close through verification."
        )
    if not (can_manage(user, f.scope_id) or f.owner_id == user.id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, FORBIDDEN)
    response = body.response.strip()
    if not response:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "Say what was done, or why no action is taken."
        )
    f.response = response
    f.status = "closed"
    f.closed_at = get_clock(request)()
    return _done(db, request, user, f, "finding.close", reason=response)


@router.post("/{finding_id}/reopen", response_model=FindingDetailOut)
def reopen(
    finding_id: uuid.UUID,
    body: ReasonIn,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.CONTROLS_READ)),
    db: Session = Depends(get_session),
) -> FindingDetailOut:
    f = get_finding(db, grant, finding_id)
    if not has_perm(user, f.scope_id, Perm.CONTROLS_WRITE):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only an ISMS manager can reopen a closed finding.")
    if f.status != "closed":
        raise HTTPException(status.HTTP_409_CONFLICT, "Only a closed finding can be reopened.")
    reason = body.reason.strip()
    if not reason:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Give a reason for reopening.")
    f.closed_at = None
    f.status = "action_planned" if f.is_nonconformity else "open"
    # A reopened nonconformity needs new or reopened work before it can be verified again.
    if f.is_nonconformity:
        f.verifications.append(
            FindingVerification(
                verifier_id=user.id,
                effective=False,
                note=f"Reopened: {reason}",
                verified_at=get_clock(request)(),
            )
        )
        db.flush()
        refresh_status(f)
    return _done(db, request, user, f, "finding.reopen", reason=reason)


@router.post("/{finding_id}/raise-risk", response_model=FindingDetailOut)
def raise_risk(
    finding_id: uuid.UUID,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.CONTROLS_READ)),
    db: Session = Depends(get_session),
) -> FindingDetailOut:
    """Adds the finding to the risk register once; raising it again returns the same register risk."""
    f = get_finding(db, grant, finding_id)
    if not can_manage(user, f.scope_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, FORBIDDEN)
    if f.risk_id and db.get(Risk, f.risk_id) is not None:
        return detail_out(db, user, f, _today(request))
    seq, code = next_risk_code(db, f.scope_id)
    risk = Risk(
        scope_id=f.scope_id,
        code=code,
        seq=seq,
        title=f"Finding {f.code}: {f.title}"[:300],
        description=f"Raised from audit finding {f.code}.\n{f.description or ''}".strip(),
        category="Audit finding",
        owner_id=f.owner_id,
    )
    db.add(risk)
    db.flush()
    f.risk_id = risk.id
    return _done(db, request, user, f, "finding.raise_risk", diff={"risk": risk.code})


@audits_router.post("/{audit_id}/findings", response_model=RaiseOut)
def raise_for_audit(
    audit_id: uuid.UUID,
    body: RaiseIn,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.CONTROLS_READ)),
    db: Session = Depends(get_session),
) -> RaiseOut:
    """Raises findings for the chosen rows, or every fail / partial / exception row; rows already raised are kept."""
    audit = db.get(Audit, audit_id)
    if audit is None or not grant.allows(audit.scope_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Audit not found.")
    if not can_manage(user, audit.scope_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, FORBIDDEN)
    if body.all == (body.item_ids is not None):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "Choose rows, or all rows with a failed result."
        )
    if body.all:
        items = [i for i in audit.items if i.result in RAISABLE]
    else:
        by_id = {i.id: i for i in audit.items}
        wanted = list(dict.fromkeys(body.item_ids or []))
        if any(i not in by_id for i in wanted):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Some rows are not in this audit.")
        items = [by_id[i] for i in wanted]
        if any(i.result not in RAISABLE for i in items):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, NOT_RAISABLE)
    now = get_clock(request)()
    created, existing = [], 0
    for item in items:
        f, new = raise_from_item(db, audit, item, user, now)
        if new:
            created.append(f)
        else:
            existing += 1
    if created:
        record(
            db,
            actor_for(request, user),
            "finding.raise_bulk",
            "audit",
            str(audit.id),
            diff={"findings": [f.code for f in created]},
        )
        db.commit()
    today = _today(request)
    return RaiseOut(created=[finding_out(db, f, today) for f in created], existing=existing)
