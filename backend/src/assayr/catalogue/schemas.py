import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from assayr.catalogue.frameworks import display_ref
from assayr.catalogue.models import Control
from assayr.scoring.models import Attestation
from assayr.scoring.service import SlotView

ImplementationStatus = Literal["not_started", "planned", "partial", "implemented"]


class OwnerOut(BaseModel):
    id: uuid.UUID
    full_name: str


class ControlSummaryOut(BaseModel):
    id: uuid.UUID
    scope_id: uuid.UUID
    code: str
    ref: str
    framework: str
    title: str
    theme: str | None
    status: str
    implementation_status: str
    owner: OwnerOut | None
    evidence_required: int
    score: float | None


class ControlPage(BaseModel):
    items: list[ControlSummaryOut]
    next_cursor: int | None


class SlotArtefactOut(BaseModel):
    link_id: uuid.UUID
    version_id: uuid.UUID
    filename: str
    state: str
    confidence: float | None
    evidence_date: date | None
    expires_on: date | None


class AttestationOut(BaseModel):
    attested_at: datetime
    valid_until: datetime
    by: str | None
    statement: str


class SlotOut(BaseModel):
    id: uuid.UUID
    name: str
    evidence_type: str
    required: bool
    freshness_days: int | None
    rules: list[str]
    state: str = "missing"
    artefact: SlotArtefactOut | None = None


class RequirementRefOut(BaseModel):
    ref: str
    title: str


class ControlDetailOut(ControlSummaryOut):
    description: str | None
    review_frequency: str | None
    default_owner_role: str | None
    implementation_text: str | None
    slots: list[SlotOut]
    requirements: list[RequirementRefOut]
    attestation: AttestationOut | None = None
    test_procedure: str | None = None
    assayr_check: dict | None = None


class RelatedEvidenceOut(BaseModel):
    version_id: uuid.UUID
    filename: str
    state: str
    linked: bool


class RelatedOut(BaseModel):
    code: str
    ref: str
    framework: str
    title: str
    status: str
    evidence: list[RelatedEvidenceOut]


class ReuseEvidenceIn(BaseModel):
    version_id: uuid.UUID


class ControlStatsOut(BaseModel):
    scope_id: uuid.UUID
    total: int
    by_status: dict[str, int]
    by_theme: dict[str, int]


class FrameworkOut(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    version: str
    requirement_count: int


class ControlUpdateIn(BaseModel):
    owner_id: uuid.UUID | None = None
    implementation_status: ImplementationStatus | None = None
    implementation_text: str | None = Field(default=None, max_length=20000)


def summary_out(control: Control) -> ControlSummaryOut:
    return ControlSummaryOut(
        id=control.id,
        scope_id=control.scope_id,
        code=control.code,
        ref=display_ref(control.code),
        framework=control.framework,
        title=control.title,
        theme=control.theme,
        status=control.status,
        implementation_status=control.implementation_status,
        owner=OwnerOut(id=control.owner.id, full_name=control.owner.full_name) if control.owner else None,
        evidence_required=sum(1 for s in control.slots if s.required),
        score=control.score,
    )


def detail_out(
    control: Control,
    views: list[SlotView] | None = None,
    attestation: Attestation | None = None,
    attested_by: str | None = None,
) -> ControlDetailOut:
    by_slot = {v.slot_id: v for v in (views or [])}

    def slot_out(s) -> SlotOut:
        view = by_slot.get(s.id)
        link = view.link if view else None
        return SlotOut(
            id=s.id,
            name=s.name,
            evidence_type=s.evidence_type,
            required=s.required,
            freshness_days=s.freshness_days,
            rules=s.rules,
            state=view.state if view else "missing",
            artefact=SlotArtefactOut(
                link_id=link.id,
                version_id=link.version_id,
                filename=link.version.filename,
                state=link.state,
                confidence=link.confidence,
                evidence_date=link.evidence_date,
                expires_on=link.expires_on,
            )
            if link
            else None,
        )

    return ControlDetailOut(
        **summary_out(control).model_dump(),
        description=control.description,
        review_frequency=control.review_frequency,
        default_owner_role=control.default_owner_role,
        implementation_text=control.implementation_text,
        test_procedure=control.test_procedure,
        slots=[slot_out(s) for s in control.slots],
        requirements=[RequirementRefOut(ref=r.ref, title=r.title) for r in control.requirements],
        attestation=AttestationOut(
            attested_at=attestation.attested_at,
            valid_until=attestation.valid_until,
            by=attested_by,
            statement=attestation.statement,
        )
        if attestation
        else None,
    )
