import uuid
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from assayr.assets.models import Asset
from assayr.audit.service import record
from assayr.catalogue.access import EditRights, check_active_user, has_perm, rights_for
from assayr.catalogue.models import Control
from assayr.catalogue.router import FORBIDDEN, _like, resolve_scope
from assayr.db import get_session
from assayr.identity.deps import actor_for, current_user, get_clock, require
from assayr.identity.models import User
from assayr.identity.rbac import Grant, Perm
from assayr.risk.library_router import require_methodology
from assayr.risk.methodology import (
    AUTHORITY_LABEL,
    acceptance_days,
    authority_allows,
    band_for,
    rating_error,
    suggest_current,
)
from assayr.risk.models import (
    Risk,
    RiskAcceptance,
    RiskAssessment,
    RiskControl,
    RiskTemplate,
    Threat,
    Vulnerability,
)
from assayr.risk.schemas import (
    AcceptIn,
    ActionIn,
    AssessmentIn,
    CloseIn,
    ControlLinksIn,
    RiskCreateIn,
    RiskDetailOut,
    RiskRowOut,
    RiskUpdateIn,
    TreatmentIn,
)
from assayr.risk.service import (
    control_effects,
    definition_of,
    draft_assessment,
    held_authority,
    inherent_of,
    latest_assessment,
    next_risk_code,
    open_actions,
    refresh_risk,
    risk_actions,
    risk_detail,
    risk_row,
)
from assayr.tasks.models import Task

router = APIRouter(tags=["risks"])
NOT_FOUND = "Risk not found."
OWNER_ONLY = "Only an ISMS manager can change the owner."


def load_risk(db: Session, grant: Grant, scope_id: uuid.UUID | None, code: str) -> Risk:
    scope = resolve_scope(db, scope_id, grant)
    risk = db.scalar(select(Risk).where(Risk.scope_id == scope.id, Risk.code == code))
    if risk is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND)
    return risk


def require_edit(user: User, risk: Risk) -> EditRights:
    rights = rights_for(user, risk.scope_id, risk.owner_id, Perm.RISKS_WRITE, Perm.RISKS_WRITE_OWN)
    if not rights.any:
        raise HTTPException(status.HTTP_403_FORBIDDEN, FORBIDDEN)
    return rights


def require_open(risk: Risk) -> None:
    if risk.closed_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "This risk is closed.")


@router.get("/risks", response_model=list[RiskRowOut])
def list_risks(
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.RISKS_READ)),
    db: Session = Depends(get_session),
    scope_id: uuid.UUID | None = None,
    status_: str | None = Query(None, alias="status", max_length=30),
    band: str | None = Query(None, max_length=20),
    owner: str | None = Query(None, max_length=40),
    q: str | None = Query(None, max_length=100),
    include_closed: bool = False,
) -> list[RiskRowOut]:
    scope = resolve_scope(db, scope_id, grant)
    stmt = select(Risk).where(Risk.scope_id == scope.id)
    if not include_closed and status_ != "closed":
        stmt = stmt.where(Risk.closed_at.is_(None))
    if status_:
        stmt = stmt.where(Risk.status == status_)
    if owner == "me":
        stmt = stmt.where(Risk.owner_id == user.id)
    elif owner:
        try:
            stmt = stmt.where(Risk.owner_id == uuid.UUID(owner))
        except ValueError as exc:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT, "owner must be 'me' or a user id."
            ) from exc
    if q and q.strip():
        like = _like(q.strip())
        stmt = stmt.where(
            or_(func.lower(Risk.title).like(like, escape="\\"), func.lower(Risk.code).like(like, escape="\\"))
        )
    rows = [risk_row(db, r) for r in db.scalars(stmt.order_by(Risk.seq)).unique()]
    if band:
        rows = [
            r
            for r in rows
            if (r.current or r.inherent) is not None and (r.current or r.inherent).band == band
        ]
    return rows


@router.post("/risks", response_model=RiskDetailOut, status_code=status.HTTP_201_CREATED)
def create_risk(
    body: RiskCreateIn,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.RISKS_READ)),
    db: Session = Depends(get_session),
    scope_id: uuid.UUID | None = None,
) -> RiskDetailOut:
    scope = resolve_scope(db, scope_id, grant)
    if not has_perm(user, scope.id, Perm.RISKS_WRITE):
        raise HTTPException(status.HTTP_403_FORBIDDEN, FORBIDDEN)
    check_active_user(db, body.owner_id)
    version = require_methodology(db)
    template = None
    if body.template_code:
        template = db.scalar(select(RiskTemplate).where(RiskTemplate.code == body.template_code))
        if template is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Risk template not found.")
    now = get_clock(request)()
    seq, code = next_risk_code(db, scope.id)
    risk = Risk(
        scope_id=scope.id,
        code=code,
        seq=seq,
        title=(body.title or template.title).strip(),
        description=body.description
        if body.description is not None
        else (template.scenario if template else None),
        category=body.category or (template.category if template else None),
        approach=body.approach,
        owner_id=body.owner_id,
        template_code=template.code if template else None,
    )
    if template is not None:
        risk.threats = list(db.scalars(select(Threat).where(Threat.code.in_(template.threat_codes))))
        risk.vulnerabilities = list(
            db.scalars(select(Vulnerability).where(Vulnerability.code.in_(template.vulnerability_codes)))
        )
        controls = db.scalars(
            select(Control).where(
                Control.scope_id == scope.id,
                Control.code.in_(template.control_codes),
                Control.applicable.is_(True),
            )
        ).unique()
        risk.control_links = [RiskControl(control=c, axis="likelihood") for c in controls]
    db.add(risk)
    db.flush()
    db.add(
        RiskAssessment(
            risk_id=risk.id,
            methodology_version_id=version.id,
            likelihood=template.likelihood if template else None,
            consequence=dict(template.consequence) if template else None,
            assessed_by_id=user.id,
            created_at=now,
        )
    )
    db.flush()
    refresh_risk(db, risk, now)
    record(
        db,
        actor_for(request, user),
        "risk.create",
        "risk",
        risk.code,
        diff={"title": risk.title, "template": risk.template_code},
    )
    db.commit()
    return risk_detail(db, risk, user)


@router.get("/risks/{code}", response_model=RiskDetailOut)
def get_risk(
    code: str,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.RISKS_READ)),
    db: Session = Depends(get_session),
    scope_id: uuid.UUID | None = None,
) -> RiskDetailOut:
    return risk_detail(db, load_risk(db, grant, scope_id, code), user)


def _resolve_codes(db: Session, model, codes: list[str], label: str) -> list:
    found = list(db.scalars(select(model).where(model.code.in_(codes)).order_by(model.code)))
    missing = sorted(set(codes) - {item.code for item in found})
    if missing:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"Unknown {label}: {missing[0]}.")
    return found


@router.patch("/risks/{code}", response_model=RiskDetailOut)
def update_risk(
    code: str,
    body: RiskUpdateIn,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.RISKS_READ)),
    db: Session = Depends(get_session),
    scope_id: uuid.UUID | None = None,
) -> RiskDetailOut:
    risk = load_risk(db, grant, scope_id, code)
    rights = require_edit(user, risk)
    require_open(risk)
    fields = body.model_fields_set
    diff: dict[str, list] = {}
    if "owner_id" in fields and body.owner_id != risk.owner_id:
        if not rights.all:
            raise HTTPException(status.HTTP_403_FORBIDDEN, OWNER_ONLY)
        check_active_user(db, body.owner_id)
        diff["owner_id"] = [
            str(risk.owner_id) if risk.owner_id else None,
            str(body.owner_id) if body.owner_id else None,
        ]
        risk.owner_id = body.owner_id
    for name in ("title", "description", "category", "approach"):
        if name not in fields:
            continue
        value = getattr(body, name)
        if value is None and name in ("title", "approach"):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"{name.capitalize()} can't be empty.")
        if value != getattr(risk, name):
            diff[name] = [getattr(risk, name), value]
            setattr(risk, name, value)
    for attr, model, label in (
        ("threat_codes", Threat, "threat"),
        ("vulnerability_codes", Vulnerability, "vulnerability"),
    ):
        codes = getattr(body, attr)
        if codes is None:
            continue
        items = _resolve_codes(db, model, codes, label)
        relation = "threats" if model is Threat else "vulnerabilities"
        before = [item.code for item in getattr(risk, relation)]
        if before != [item.code for item in items]:
            diff[relation] = [before, [item.code for item in items]]
            setattr(risk, relation, items)
    if body.asset_ids is not None:
        assets = list(
            db.scalars(
                select(Asset)
                .where(Asset.id.in_(body.asset_ids), Asset.scope_id == risk.scope_id)
                .order_by(Asset.seq)
            ).unique()
        )
        if len(assets) != len(set(body.asset_ids)):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Unknown asset.")
        before = [a.code for a in risk.assets]
        if before != [a.code for a in assets]:
            diff["assets"] = [before, [a.code for a in assets]]
            risk.assets = assets
    if diff:
        record(db, actor_for(request, user), "risk.update", "risk", risk.code, diff=diff)
        db.commit()
    return risk_detail(db, risk, user)


@router.put("/risks/{code}/controls", response_model=RiskDetailOut)
def set_risk_controls(
    code: str,
    body: ControlLinksIn,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.RISKS_READ)),
    db: Session = Depends(get_session),
    scope_id: uuid.UUID | None = None,
) -> RiskDetailOut:
    risk = load_risk(db, grant, scope_id, code)
    require_edit(user, risk)
    require_open(risk)
    codes = [link.code for link in body.links]
    if len(codes) != len(set(codes)):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Each control can be linked once.")
    controls = {
        c.code: c
        for c in db.scalars(
            select(Control).where(Control.scope_id == risk.scope_id, Control.code.in_(codes))
        ).unique()
    }
    for link in body.links:
        control = controls.get(link.code)
        if control is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"Control {link.code} not found.")
        if not control.applicable:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"{control.code} is excluded in the Statement of Applicability. "
                "Include it before linking it to a risk.",
            )
    before = sorted(f"{link.control.code}:{link.axis}" for link in risk.control_links)
    wanted = {controls[link.code].id: (controls[link.code], link.axis) for link in body.links}
    for link in list(risk.control_links):
        if link.control_id in wanted:
            link.axis = wanted.pop(link.control_id)[1]
        else:
            risk.control_links.remove(link)
    for control, axis in wanted.values():
        risk.control_links.append(RiskControl(control=control, axis=axis))
    db.flush()
    after = sorted(f"{link.control.code}:{link.axis}" for link in risk.control_links)
    if before != after:
        record(
            db,
            actor_for(request, user),
            "risk.controls",
            "risk",
            risk.code,
            diff={"controls": [before, after]},
        )
    refresh_risk(db, risk, get_clock(request)())
    db.commit()
    return risk_detail(db, risk, user)


@router.patch("/risks/{code}/assessment", response_model=RiskDetailOut)
def save_assessment(
    code: str,
    body: AssessmentIn,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.RISKS_READ)),
    db: Session = Depends(get_session),
    scope_id: uuid.UUID | None = None,
) -> RiskDetailOut:
    risk = load_risk(db, grant, scope_id, code)
    require_edit(user, risk)
    require_open(risk)
    version = require_methodology(db)
    error = rating_error(
        version.definition,
        likelihood=body.likelihood,
        consequence=body.consequence,
        current=(body.current_l, body.current_c),
        target=(body.target_l, body.target_c),
    )
    if error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, error)
    now = get_clock(request)()
    draft = draft_assessment(db, risk)
    if draft is None:
        draft = RiskAssessment(risk_id=risk.id, methodology_version_id=version.id, created_at=now)
        latest = latest_assessment(db, risk)
        if latest is not None:  # a reassessment starts from the last ratings
            draft.likelihood = latest.likelihood
            draft.consequence = dict(latest.consequence or {})
            draft.rationale = latest.rationale
        db.add(draft)
    fields = body.model_fields_set
    for name in (
        "likelihood",
        "current_l",
        "current_c",
        "current_reason",
        "target_l",
        "target_c",
        "rationale",
    ):
        if name in fields:
            setattr(draft, name, getattr(body, name))
    if "consequence" in fields:
        draft.consequence = {**(draft.consequence or {}), **(body.consequence or {})}
    draft.assessed_by_id = user.id
    db.flush()
    refresh_risk(db, risk, now)
    db.commit()
    return risk_detail(db, risk, user)


def _pair(values: tuple[int | None, int | None], default: tuple[int, int], name: str) -> tuple[int, int]:
    if values == (None, None):
        return default
    if None in values:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"Give both the likelihood and the consequence for the {name} level.",
        )
    return values  # type: ignore[return-value]


@router.post("/risks/{code}/assessment/finalize", response_model=RiskDetailOut)
def finalize_assessment(
    code: str,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.RISKS_READ)),
    db: Session = Depends(get_session),
    scope_id: uuid.UUID | None = None,
) -> RiskDetailOut:
    risk = load_risk(db, grant, scope_id, code)
    require_edit(user, risk)
    require_open(risk)
    draft = draft_assessment(db, risk)
    if draft is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "There's no assessment in progress.")
    definition = definition_of(db, draft)
    inherent = inherent_of(definition, draft)
    if inherent is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Rate the likelihood and every consequence area before finishing.",
        )
    suggested = suggest_current(definition, *inherent, control_effects(risk))
    current = _pair((draft.current_l, draft.current_c), suggested, "current")
    if current != suggested and not (draft.current_reason or "").strip():
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Explain why the current level differs from the suggested one.",
        )
    if current[0] * current[1] > inherent[0] * inherent[1]:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "The current level can't be higher than the inherent level.",
        )
    target = _pair((draft.target_l, draft.target_c), current, "target")
    if target[0] * target[1] > current[0] * current[1]:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "The target can't be worse than the current level."
        )
    now = get_clock(request)()
    draft.suggested = {"likelihood": suggested[0], "consequence": suggested[1]}
    draft.current_l, draft.current_c = current
    draft.target_l, draft.target_c = target
    draft.finalized_at = now
    draft.assessed_by_id = user.id
    band = band_for(definition, *current)
    risk.review_due = now.date() + timedelta(days=band["review_days"])
    db.flush()
    refresh_risk(db, risk, now)
    record(
        db,
        actor_for(request, user),
        "risk.assess",
        "risk",
        risk.code,
        diff={
            "inherent": inherent[0] * inherent[1],
            "current": current[0] * current[1],
            "target": target[0] * target[1],
            "band": band["key"],
        },
    )
    db.commit()
    return risk_detail(db, risk, user)


@router.post("/risks/{code}/treatment", response_model=RiskDetailOut)
def set_treatment(
    code: str,
    body: TreatmentIn,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.RISKS_READ)),
    db: Session = Depends(get_session),
    scope_id: uuid.UUID | None = None,
) -> RiskDetailOut:
    risk = load_risk(db, grant, scope_id, code)
    require_edit(user, risk)
    require_open(risk)
    if latest_assessment(db, risk) is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Finish the assessment before choosing a treatment.")
    note = (body.note or "").strip()
    if body.option == "avoid" and not note:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Record the decision to avoid the risk.")
    if body.option == "share" and not note:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "Record the contract or insurance that shares the risk."
        )
    now = get_clock(request)()
    before = risk.treatment_option
    risk.treatment_option = body.option
    risk.treatment_note = note or None
    risk.treatment_budget = body.budget
    risk.treatment_due = body.due
    if body.option == "avoid":
        risk.closed_at = now
        risk.close_reason = f"Avoided: {note}"
    refresh_risk(db, risk, now)
    record(
        db,
        actor_for(request, user),
        "risk.treatment",
        "risk",
        risk.code,
        diff={"option": [before, body.option]},
    )
    db.commit()
    return risk_detail(db, risk, user)


@router.post("/risks/{code}/actions", response_model=RiskDetailOut, status_code=status.HTTP_201_CREATED)
def add_action(
    code: str,
    body: ActionIn,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.RISKS_READ)),
    db: Session = Depends(get_session),
    scope_id: uuid.UUID | None = None,
) -> RiskDetailOut:
    risk = load_risk(db, grant, scope_id, code)
    require_edit(user, risk)
    require_open(risk)
    if risk.treatment_option != "modify":
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Treatment actions belong to the 'modify' option. Choose it first."
        )
    check_active_user(db, body.assignee_id, "Assignee")
    task = Task(
        scope_id=risk.scope_id,
        entity_type="risk",
        entity_id=str(risk.id),
        title=body.title.strip(),
        assignee_id=body.assignee_id,
        due=body.due,
        created_by_id=user.id,
    )
    db.add(task)
    db.flush()
    refresh_risk(db, risk, get_clock(request)())
    record(
        db,
        actor_for(request, user),
        "task.create",
        "task",
        str(task.id),
        diff={"risk": risk.code, "title": task.title},
    )
    db.commit()
    return risk_detail(db, risk, user)


@router.post("/risks/{code}/accept", response_model=RiskDetailOut)
def accept_risk(
    code: str,
    body: AcceptIn,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.RISKS_READ)),
    db: Session = Depends(get_session),
    scope_id: uuid.UUID | None = None,
) -> RiskDetailOut:
    risk = load_risk(db, grant, scope_id, code)
    require_open(risk)
    latest = latest_assessment(db, risk)
    if latest is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Finish the assessment before accepting the risk.")
    if draft_assessment(db, risk) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Finish the reassessment before accepting the risk.")
    if risk.treatment_option == "modify" and open_actions(risk_actions(db, risk)):
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Finish the treatment actions before accepting the residual risk."
        )
    definition = definition_of(db, latest)
    band = band_for(definition, latest.current_l, latest.current_c)
    held = held_authority(user, risk.scope_id, risk.owner_id == user.id)
    if not authority_allows(held, band["authority"]):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            f"A {band['label'].lower()} risk must be accepted by {AUTHORITY_LABEL[band['authority']]}.",
        )
    now = get_clock(request)()
    if risk.treatment_option is None:
        risk.treatment_option = "retain"
    acceptance = RiskAcceptance(
        risk_id=risk.id,
        assessment_id=latest.id,
        band=band["key"],
        score=latest.current_l * latest.current_c,
        authority=held,
        statement=body.statement.strip(),
        accepted_by_id=user.id,
        accepted_at=now,
        expires_at=now + timedelta(days=acceptance_days(definition, band["key"])),
    )
    db.add(acceptance)
    db.flush()
    refresh_risk(db, risk, now)
    record(
        db,
        actor_for(request, user),
        "risk.accept",
        "risk",
        risk.code,
        diff={
            "band": band["key"],
            "score": acceptance.score,
            "expires_at": acceptance.expires_at.isoformat(),
        },
    )
    db.commit()
    return risk_detail(db, risk, user)


@router.post("/risks/{code}/close", response_model=RiskDetailOut)
def close_risk(
    code: str,
    body: CloseIn,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.RISKS_READ)),
    db: Session = Depends(get_session),
    scope_id: uuid.UUID | None = None,
) -> RiskDetailOut:
    risk = load_risk(db, grant, scope_id, code)
    require_edit(user, risk)
    if risk.closed_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "This risk is already closed.")
    now = get_clock(request)()
    risk.closed_at = now
    risk.close_reason = body.reason.strip()
    refresh_risk(db, risk, now)
    record(db, actor_for(request, user), "risk.close", "risk", risk.code, reason=risk.close_reason)
    db.commit()
    return risk_detail(db, risk, user)
