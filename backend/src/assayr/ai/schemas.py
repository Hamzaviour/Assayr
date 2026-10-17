import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from assayr.catalogue.schemas import OwnerOut

Source = Literal["in_house", "third_party", "open_source"]
Lifecycle = Literal["planned", "development", "validation", "deployed", "retired"]
SystemStatus = Literal["active", "retired"]
Area = Literal[
    "intended_use",
    "affected",
    "individual_impacts",
    "societal_impacts",
    "fairness",
    "transparency",
    "oversight",
    "safety",
    "data_quality",
]


def _not_blank(value: str | None) -> str | None:
    if value is not None and not value.strip():
        raise ValueError("can not be empty")
    return value.strip() if value is not None else None


class AiSystemIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    purpose: str | None = Field(None, max_length=5000)
    owner_id: uuid.UUID | None = None
    source: Source
    provider: str | None = Field(None, max_length=200)
    model_type: str | None = Field(None, max_length=100)
    lifecycle: Lifecycle
    risk_level: int = Field(ge=1, le=5)
    uses_personal_data: bool = False
    pii_categories: list[str] = Field(default_factory=list, max_length=20)
    asset_ids: list[uuid.UUID] = Field(default_factory=list, max_length=100)
    human_oversight: str | None = Field(None, max_length=5000)

    _name = field_validator("name")(_not_blank)


class AiSystemUpdateIn(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    purpose: str | None = Field(None, max_length=5000)
    owner_id: uuid.UUID | None = None
    source: Source | None = None
    provider: str | None = Field(None, max_length=200)
    model_type: str | None = Field(None, max_length=100)
    lifecycle: Lifecycle | None = None
    risk_level: int | None = Field(None, ge=1, le=5)
    uses_personal_data: bool | None = None
    pii_categories: list[str] | None = Field(None, max_length=20)
    asset_ids: list[uuid.UUID] | None = Field(None, max_length=100)
    human_oversight: str | None = Field(None, max_length=5000)
    status: SystemStatus | None = None

    _name = field_validator("name")(_not_blank)


class AiSystemOut(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    purpose: str | None
    owner: OwnerOut | None
    source: str
    provider: str | None
    model_type: str | None
    lifecycle: str
    risk_level: int
    risk_label: str
    uses_personal_data: bool
    pii_categories: list[str]
    asset_ids: list[str]
    human_oversight: str | None
    status: str
    assessment_status: str | None
    created_at: datetime
    can_edit: bool


class AssessmentIn(BaseModel):
    intended_use: str | None = Field(None, max_length=10000)
    affected: str | None = Field(None, max_length=10000)
    individual_impacts: str | None = Field(None, max_length=10000)
    societal_impacts: str | None = Field(None, max_length=10000)
    fairness: str | None = Field(None, max_length=10000)
    transparency: str | None = Field(None, max_length=10000)
    oversight: str | None = Field(None, max_length=10000)
    safety: str | None = Field(None, max_length=10000)
    data_quality: str | None = Field(None, max_length=10000)
    conclusion: str | None = Field(None, max_length=10000)


class ImpactIn(BaseModel):
    area: Area
    description: str = Field(min_length=1, max_length=500)
    likelihood: int = Field(ge=1, le=5)
    impact: int = Field(ge=1, le=5)
    mitigation: str | None = Field(None, max_length=5000)
    owner_id: uuid.UUID | None = None

    _description = field_validator("description")(_not_blank)


class ImpactUpdateIn(BaseModel):
    area: Area | None = None
    description: str | None = Field(None, min_length=1, max_length=500)
    likelihood: int | None = Field(None, ge=1, le=5)
    impact: int | None = Field(None, ge=1, le=5)
    mitigation: str | None = Field(None, max_length=5000)
    owner_id: uuid.UUID | None = None

    _description = field_validator("description")(_not_blank)


class ImpactOut(BaseModel):
    id: uuid.UUID
    area: str
    description: str
    likelihood: int
    impact: int
    score: int
    level: int
    mitigation: str | None
    owner: OwnerOut | None
    risk_id: uuid.UUID | None
    risk_code: str | None


class AssessmentOut(AssessmentIn):
    id: uuid.UUID
    status: str
    approved_by: OwnerOut | None
    approved_at: datetime | None
    review_due: date | None
    impacts: list[ImpactOut]
    missing: list[str]
    can_edit: bool
