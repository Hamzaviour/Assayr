import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import Response
from openpyxl import Workbook
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from assayr.audit.service import record
from assayr.catalogue.access import has_perm
from assayr.catalogue.models import Control
from assayr.catalogue.router import FORBIDDEN, resolve_scope
from assayr.db import get_session
from assayr.exports import add_sheet, xlsx_response
from assayr.identity.deps import actor_for, current_user, get_clock, require
from assayr.identity.models import User
from assayr.identity.rbac import Grant, Perm
from assayr.scoring.service import recompute_control
from assayr.soa.models import SoaVersion
from assayr.soa.schemas import SoaItemOut, SoaItemsIn, SoaOut
from assayr.soa.service import active_risk_links, soa_view

router = APIRouter(tags=["statement of applicability"])


@router.get("/soa", response_model=SoaOut)
def get_soa(
    request: Request,
    grant: Grant = Depends(require(Perm.SOA_READ)),
    db: Session = Depends(get_session),
    scope_id: uuid.UUID | None = None,
) -> SoaOut:
    scope = resolve_scope(db, scope_id, grant)
    return soa_view(db, scope.id, request.app.state.settings, get_clock(request)().date())


@router.patch("/soa/items", response_model=SoaOut)
def update_soa_items(
    body: SoaItemsIn,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.SOA_READ)),
    db: Session = Depends(get_session),
    scope_id: uuid.UUID | None = None,
) -> SoaOut:
    scope = resolve_scope(db, scope_id, grant)
    if not has_perm(user, scope.id, Perm.SOA_WRITE):
        raise HTTPException(status.HTTP_403_FORBIDDEN, FORBIDDEN)
    codes = list(dict.fromkeys(body.codes))
    controls = {
        c.code: c
        for c in db.scalars(
            select(Control).where(Control.scope_id == scope.id, Control.code.in_(codes))
        ).unique()
    }
    for code in codes:
        if code not in controls:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"Control {code} not found.")
    fields = body.model_fields_set
    if "applicable" in fields and body.applicable is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Applicable can't be empty.")
    if body.applicable is False:
        links = active_risk_links(db, scope.id)
        for code in codes:
            reason = (
                body.exclusion_reason if "exclusion_reason" in fields else controls[code].exclusion_reason
            )
            if not (reason or "").strip():
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_CONTENT, "Give a reason for excluding a control."
                )
            risks = links.get(controls[code].id)
            if risks:
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    f"{code} mitigates {', '.join(risks)}. Unlink it from those risks or change their treatment first.",
                )
    settings = request.app.state.settings
    now = get_clock(request)()
    for code in codes:
        control = controls[code]
        diff: dict[str, list] = {}
        if "applicable" in fields and body.applicable != control.applicable:
            diff["applicable"] = [control.applicable, body.applicable]
            control.applicable = body.applicable
        if "sources" in fields:
            new_sources = sorted(set(body.sources or []))
            if new_sources != sorted(control.soa_sources or []):
                diff["sources"] = [sorted(control.soa_sources or []), new_sources]
                control.soa_sources = new_sources
        for name, attr in (("justification", "soa_justification"), ("exclusion_reason", "exclusion_reason")):
            if name in fields:
                value = (getattr(body, name) or "").strip() or None
                if value != getattr(control, attr):
                    diff[name] = [getattr(control, attr), value]
                    setattr(control, attr, value)
        if not diff:
            continue
        record(db, actor_for(request, user), "soa.update", "control", code, diff=diff)
        if "applicable" in diff:
            trigger = (
                "Included in the Statement of Applicability"
                if control.applicable
                else "Excluded in the Statement of Applicability"
            )
            recompute_control(db, control, now, settings, trigger=trigger)
    db.commit()
    return soa_view(db, scope.id, settings, now.date())


class SoaVersionSummaryOut(BaseModel):
    version_no: int
    status: str
    prepared_by: str | None
    prepared_at: datetime
    decided_by: str | None
    decided_at: datetime | None
    decision_note: str | None
    applicable: int
    excluded: int


class SoaVersionOut(SoaVersionSummaryOut):
    entries: list[SoaItemOut]


class ReturnIn(BaseModel):
    reason: str = Field(min_length=1, max_length=2000)


def _name(db: Session, user_id: uuid.UUID | None) -> str | None:
    person = db.get(User, user_id) if user_id else None
    return person.full_name if person else None


def _summary(db: Session, version: SoaVersion) -> SoaVersionSummaryOut:
    applicable = sum(1 for e in version.entries if e["applicable"])
    return SoaVersionSummaryOut(
        version_no=version.version_no,
        status=version.status,
        prepared_by=_name(db, version.prepared_by_id),
        prepared_at=version.prepared_at,
        decided_by=_name(db, version.decided_by_id),
        decided_at=version.decided_at,
        decision_note=version.decision_note,
        applicable=applicable,
        excluded=len(version.entries) - applicable,
    )


def _full(db: Session, version: SoaVersion) -> SoaVersionOut:
    return SoaVersionOut(**_summary(db, version).model_dump(), entries=version.entries)


def _load_version(db: Session, scope_id: uuid.UUID, version_no: int) -> SoaVersion:
    version = db.scalar(
        select(SoaVersion).where(SoaVersion.scope_id == scope_id, SoaVersion.version_no == version_no)
    )
    if version is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "SoA version not found.")
    return version


def _plural(count: int, word: str) -> str:
    return f"{count} {word}{'' if count == 1 else 's'}"


@router.get("/soa/versions", response_model=list[SoaVersionSummaryOut])
def list_versions(
    grant: Grant = Depends(require(Perm.SOA_READ)),
    db: Session = Depends(get_session),
    scope_id: uuid.UUID | None = None,
) -> list[SoaVersionSummaryOut]:
    scope = resolve_scope(db, scope_id, grant)
    versions = db.scalars(
        select(SoaVersion).where(SoaVersion.scope_id == scope.id).order_by(SoaVersion.version_no.desc())
    )
    return [_summary(db, v) for v in versions]


@router.post("/soa/versions", response_model=SoaVersionOut, status_code=status.HTTP_201_CREATED)
def submit_version(
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.SOA_READ)),
    db: Session = Depends(get_session),
    scope_id: uuid.UUID | None = None,
) -> SoaVersionOut:
    scope = resolve_scope(db, scope_id, grant)
    if not has_perm(user, scope.id, Perm.SOA_WRITE):
        raise HTTPException(status.HTTP_403_FORBIDDEN, FORBIDDEN)
    pending = db.scalar(
        select(SoaVersion).where(SoaVersion.scope_id == scope.id, SoaVersion.status == "pending")
    )
    if pending is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"Version {pending.version_no} is already waiting for approval."
        )
    now = get_clock(request)()
    view = soa_view(db, scope.id, request.app.state.settings, now.date())
    if not view.checks.ok:
        problems = []
        if view.checks.orphans:
            problems.append(
                f"{_plural(len(view.checks.orphans), 'applicable control')} without a justification"
            )
        if view.checks.excluded_mitigating:
            problems.append(
                f"{_plural(len(view.checks.excluded_mitigating), 'excluded control')} that mitigate a risk"
            )
        if view.checks.untreated_risks:
            problems.append(
                f"{_plural(len(view.checks.untreated_risks), 'risk')} above appetite without a treatment"
            )
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"Fix the traceability issues before submitting: {'; '.join(problems)}."
        )
    number = (
        db.scalar(select(func.max(SoaVersion.version_no)).where(SoaVersion.scope_id == scope.id)) or 0
    ) + 1
    version = SoaVersion(
        scope_id=scope.id,
        version_no=number,
        status="pending",
        entries=[item.model_dump(mode="json") for item in view.items],
        prepared_by_id=user.id,
        prepared_at=now,
    )
    db.add(version)
    db.flush()
    record(
        db,
        actor_for(request, user),
        "soa.submit",
        "soa_version",
        str(number),
        diff={"controls": len(view.items)},
    )
    db.commit()
    return _full(db, version)


@router.get("/soa/versions/{version_no}", response_model=SoaVersionOut)
def get_version(
    version_no: int,
    grant: Grant = Depends(require(Perm.SOA_READ)),
    db: Session = Depends(get_session),
    scope_id: uuid.UUID | None = None,
) -> SoaVersionOut:
    scope = resolve_scope(db, scope_id, grant)
    return _full(db, _load_version(db, scope.id, version_no))


def _decide(
    db: Session, request: Request, user: User, version: SoaVersion, outcome: str, note: str | None
) -> None:
    verb = "approved" if outcome == "approved" else "returned"
    if version.status != "pending":
        raise HTTPException(status.HTTP_409_CONFLICT, f"Only a version waiting for approval can be {verb}.")
    if outcome == "approved" and version.prepared_by_id == user.id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "You prepared this version, so someone else must approve it."
        )
    version.status = outcome
    version.decided_by_id = user.id
    version.decided_at = get_clock(request)()
    version.decision_note = note
    action = "soa.approve" if outcome == "approved" else "soa.return"
    record(db, actor_for(request, user), action, "soa_version", str(version.version_no), reason=note)
    db.commit()


@router.post("/soa/versions/{version_no}/approve", response_model=SoaVersionOut)
def approve_version(
    version_no: int,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.SOA_APPROVE)),
    db: Session = Depends(get_session),
    scope_id: uuid.UUID | None = None,
) -> SoaVersionOut:
    scope = resolve_scope(db, scope_id, grant)
    version = _load_version(db, scope.id, version_no)
    _decide(db, request, user, version, "approved", None)
    return _full(db, version)


@router.post("/soa/versions/{version_no}/return", response_model=SoaVersionOut)
def return_version(
    version_no: int,
    body: ReturnIn,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.SOA_APPROVE)),
    db: Session = Depends(get_session),
    scope_id: uuid.UUID | None = None,
) -> SoaVersionOut:
    scope = resolve_scope(db, scope_id, grant)
    version = _load_version(db, scope.id, version_no)
    _decide(db, request, user, version, "returned", body.reason.strip())
    return _full(db, version)


SOA_HEADER = [
    "Control",
    "Title",
    "Theme",
    "Applicable",
    "Justification sources",
    "Justification",
    "Exclusion reason",
    "Implementation",
    "Status",
    "Evidence verified",
    "Owner",
]


def _soa_rows(entries: list[dict]) -> list[list]:
    return [
        [
            e["code"],
            e["title"],
            e["theme"],
            "Yes" if e["applicable"] else "No",
            "; ".join(s["label"] for s in e["sources"]),
            e["justification"],
            e["exclusion_reason"],
            e["implementation_status"].replace("_", " "),
            e["status"].replace("_", " "),
            f"{e['evidence_verified']} of {e['evidence_required']}",
            e["owner"],
        ]
        for e in entries
    ]


@router.get("/soa/versions/{version_no}/export.xlsx")
def export_version(
    version_no: int,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.SOA_READ)),
    db: Session = Depends(get_session),
    scope_id: uuid.UUID | None = None,
) -> Response:
    scope = resolve_scope(db, scope_id, grant)
    version = _load_version(db, scope.id, version_no)
    summary = _summary(db, version)
    workbook = Workbook()
    add_sheet(workbook, f"SoA v{version.version_no}", SOA_HEADER, _soa_rows(version.entries))
    add_sheet(
        workbook,
        "Approval",
        ["Field", "Value"],
        [
            ["Version", summary.version_no],
            ["Status", summary.status.capitalize()],
            ["Prepared by", summary.prepared_by],
            ["Prepared at", summary.prepared_at.isoformat()],
            ["Decided by", summary.decided_by],
            ["Decided at", summary.decided_at.isoformat() if summary.decided_at else None],
            ["Decision note", summary.decision_note],
        ],
    )
    record(db, actor_for(request, user), "soa.export", "soa_version", str(version.version_no))
    db.commit()
    return xlsx_response(workbook, f"statement-of-applicability-v{version.version_no}.xlsx")


@router.get("/soa/export.xlsx")
def export_working(
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.SOA_READ)),
    db: Session = Depends(get_session),
    scope_id: uuid.UUID | None = None,
) -> Response:
    scope = resolve_scope(db, scope_id, grant)
    view = soa_view(db, scope.id, request.app.state.settings, get_clock(request)().date())
    workbook = Workbook()
    add_sheet(workbook, "SoA (working)", SOA_HEADER, _soa_rows([i.model_dump() for i in view.items]))
    record(db, actor_for(request, user), "soa.export", "soa_version", "working")
    db.commit()
    return xlsx_response(workbook, "statement-of-applicability-working.xlsx")
