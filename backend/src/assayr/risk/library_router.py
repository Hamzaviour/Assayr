from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from assayr.audit.service import record
from assayr.db import get_session
from assayr.identity.deps import actor_for, current_user, require
from assayr.identity.models import User
from assayr.identity.rbac import Perm
from assayr.risk.methodology import active_methodology
from assayr.risk.models import MethodologyVersion, RiskTemplate, Threat, Vulnerability

router = APIRouter(tags=["risk library"])


class MethodologyOut(BaseModel):
    version_no: int
    name: str
    likelihood: list[dict]
    consequence: dict
    bands: list[dict]


class LibraryItemOut(BaseModel):
    code: str
    name: str
    category: str
    description: str | None
    is_custom: bool


class TemplateOut(BaseModel):
    code: str
    title: str
    scenario: str
    category: str
    threat_codes: list[str]
    vulnerability_codes: list[str]
    control_codes: list[str]
    likelihood: int
    consequence: dict[str, int]


class LibraryOut(BaseModel):
    threats: list[LibraryItemOut]
    vulnerabilities: list[LibraryItemOut]
    templates: list[TemplateOut]


class LibraryItemIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    category: str = Field(min_length=1, max_length=60)
    description: str | None = Field(None, max_length=2000)


def require_methodology(db: Session) -> MethodologyVersion:
    version = active_methodology(db)
    if version is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No risk methodology exists yet. Run `assayr seed`.")
    return version


@router.get("/risk-methodology", response_model=MethodologyOut)
def get_methodology(
    _grant=Depends(require(Perm.RISKS_READ)), db: Session = Depends(get_session)
) -> MethodologyOut:
    version = require_methodology(db)
    definition = version.definition
    return MethodologyOut(
        version_no=version.version_no,
        name=version.name,
        likelihood=definition["likelihood"],
        consequence=definition["consequence"],
        bands=definition["bands"],
    )


@router.get("/risk-library", response_model=LibraryOut)
def get_library(_grant=Depends(require(Perm.RISKS_READ)), db: Session = Depends(get_session)) -> LibraryOut:
    return LibraryOut(
        threats=[
            LibraryItemOut.model_validate(t, from_attributes=True)
            for t in db.scalars(select(Threat).order_by(Threat.code))
        ],
        vulnerabilities=[
            LibraryItemOut.model_validate(v, from_attributes=True)
            for v in db.scalars(select(Vulnerability).order_by(Vulnerability.code))
        ],
        templates=[
            TemplateOut.model_validate(t, from_attributes=True)
            for t in db.scalars(select(RiskTemplate).order_by(RiskTemplate.code))
        ],
    )


def _next_code(db: Session, model, prefix: str) -> str:
    numbers = [
        int(code[len(prefix) :])
        for code in db.scalars(select(model.code))
        if code.startswith(prefix) and code[len(prefix) :].isdigit()
    ]
    return f"{prefix}{max(numbers, default=0) + 1:02d}"


def _add(
    db: Session, request: Request, user: User, model, prefix: str, body: LibraryItemIn
) -> LibraryItemOut:
    item = model(
        code=_next_code(db, model, prefix),
        name=body.name.strip(),
        category=body.category.strip(),
        description=body.description,
        is_custom=True,
    )
    db.add(item)
    db.flush()
    record(
        db,
        actor_for(request, user),
        "risk_library.add",
        model.__tablename__,
        item.code,
        diff={"name": item.name},
    )
    db.commit()
    return LibraryItemOut.model_validate(item, from_attributes=True)


@router.post("/risk-library/threats", response_model=LibraryItemOut, status_code=status.HTTP_201_CREATED)
def add_threat(
    body: LibraryItemIn,
    request: Request,
    user: User = Depends(current_user),
    _grant=Depends(require(Perm.RISKS_WRITE)),
    db: Session = Depends(get_session),
) -> LibraryItemOut:
    return _add(db, request, user, Threat, "T", body)


@router.post(
    "/risk-library/vulnerabilities", response_model=LibraryItemOut, status_code=status.HTTP_201_CREATED
)
def add_vulnerability(
    body: LibraryItemIn,
    request: Request,
    user: User = Depends(current_user),
    _grant=Depends(require(Perm.RISKS_WRITE)),
    db: Session = Depends(get_session),
) -> LibraryItemOut:
    return _add(db, request, user, Vulnerability, "V", body)
