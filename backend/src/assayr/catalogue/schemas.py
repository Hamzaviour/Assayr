import uuid
from typing import Literal

from pydantic import BaseModel, Field

from assayr.catalogue.models import Control

ImplementationStatus = Literal["not_started", "planned", "partial", "implemented"]


class OwnerOut(BaseModel):
    id: uuid.UUID
    full_name: str


class ControlSummaryOut(BaseModel):
    id: uuid.UUID
    scope_id: uuid.UUID
    code: str
    title: str
    theme: str | None
    status: str
    implementation_status: str
    owner: OwnerOut | None
    evidence_required: int


class ControlPage(BaseModel):
    items: list[ControlSummaryOut]
    next_cursor: int | None


class SlotOut(BaseModel):
    id: uuid.UUID
    name: str
    evidence_type: str
    required: bool
    freshness_days: int | None
    rules: list[str]


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
        title=control.title,
        theme=control.theme,
        status=control.status,
        implementation_status=control.implementation_status,
        owner=OwnerOut(id=control.owner.id, full_name=control.owner.full_name) if control.owner else None,
        evidence_required=sum(1 for s in control.slots if s.required),
    )


def detail_out(control: Control) -> ControlDetailOut:
    return ControlDetailOut(
        **summary_out(control).model_dump(),
        description=control.description,
        review_frequency=control.review_frequency,
        default_owner_role=control.default_owner_role,
        implementation_text=control.implementation_text,
        slots=[
            SlotOut(
                id=s.id,
                name=s.name,
                evidence_type=s.evidence_type,
                required=s.required,
                freshness_days=s.freshness_days,
                rules=s.rules,
            )
            for s in control.slots
        ],
        requirements=[RequirementRefOut(ref=r.ref, title=r.title) for r in control.requirements],
    )
