import uuid

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
from assayr.risk.models import Risk, RiskAssessment, RiskControl, RiskTemplate, Threat, Vulnerability
from assayr.risk.schemas import ControlLinksIn, RiskCreateIn, RiskDetailOut, RiskRowOut, RiskUpdateIn
from assayr.risk.service import next_risk_code, refresh_risk, risk_detail, risk_row

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
