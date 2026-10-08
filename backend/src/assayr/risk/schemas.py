import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from assayr.catalogue.schemas import OwnerOut
from assayr.risk.methodology import band_for

Approach = Literal["event", "asset"]
Axis = Literal["likelihood", "consequence"]
TreatmentOption = Literal["modify", "retain", "avoid", "share"]


class LevelOut(BaseModel):
    likelihood: int
    consequence: int
    score: int
    band: str
    band_label: str


def level_out(definition: dict | None, likelihood: int | None, consequence: int | None) -> LevelOut | None:
    if definition is None or likelihood is None or consequence is None:
        return None
    band = band_for(definition, likelihood, consequence)
    return LevelOut(
        likelihood=likelihood,
        consequence=consequence,
        score=likelihood * consequence,
        band=band["key"],
        band_label=band["label"],
    )


class NamedRef(BaseModel):
    code: str
    name: str


class AssetRef(BaseModel):
    id: uuid.UUID
    code: str
    name: str


class RiskControlOut(BaseModel):
    code: str
    title: str
    status: str
    axis: str


class ProgressOut(BaseModel):
    done: int
    total: int


class TaskOut(BaseModel):
    id: uuid.UUID
    title: str
    assignee: OwnerOut | None
    due: date | None
    status: str
    done_at: datetime | None


def task_out(task) -> TaskOut:
    return TaskOut(
        id=task.id,
        title=task.title,
        assignee=OwnerOut(id=task.assignee.id, full_name=task.assignee.full_name) if task.assignee else None,
        due=task.due,
        status=task.status,
        done_at=task.done_at,
    )


class AssessmentOut(BaseModel):
    id: uuid.UUID
    likelihood: int | None
    consequence: dict[str, int]
    inherent: LevelOut | None
    suggested: LevelOut | None
    current: LevelOut | None
    current_reason: str | None
    target: LevelOut | None
    rationale: str | None
    finalized_at: datetime | None
    assessed_by: str | None
    methodology_version: int


class AcceptanceOut(BaseModel):
    band: str
    score: int
    authority: str
    statement: str
    accepted_by: str | None
    accepted_at: datetime
    expires_at: datetime


class TreatmentOut(BaseModel):
    option: str | None
    note: str | None
    budget: str | None
    due: date | None


class RiskRowOut(BaseModel):
    id: uuid.UUID
    code: str
    title: str
    category: str | None
    approach: str
    owner: OwnerOut | None
    status: str
    inherent: LevelOut | None
    current: LevelOut | None
    target: LevelOut | None
    treatment_option: str | None
    progress: ProgressOut
    review_due: date | None
    acceptance_expires: datetime | None


class RiskDetailOut(RiskRowOut):
    description: str | None
    template_code: str | None
    threats: list[NamedRef]
    vulnerabilities: list[NamedRef]
    assets: list[AssetRef]
    controls: list[RiskControlOut]
    draft: AssessmentOut | None
    latest: AssessmentOut | None
    history: list[AssessmentOut]
    treatment: TreatmentOut
    actions: list[TaskOut]
    acceptance: AcceptanceOut | None
    required_authority: str | None
    can_accept: bool
    can_edit: bool
    closed_at: datetime | None
    close_reason: str | None


class RiskCreateIn(BaseModel):
    template_code: str | None = Field(None, max_length=20)
    title: str | None = Field(None, min_length=1, max_length=300)
    description: str | None = Field(None, max_length=10000)
    category: str | None = Field(None, max_length=60)
    approach: Approach = "event"
    owner_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def _title_or_template(self):
        if not self.title and not self.template_code:
            raise ValueError("Give a title or choose a template.")
        return self


class RiskUpdateIn(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=300)
    description: str | None = Field(None, max_length=10000)
    category: str | None = Field(None, max_length=60)
    approach: Approach | None = None
    owner_id: uuid.UUID | None = None
    threat_codes: list[str] | None = Field(None, max_length=100)
    vulnerability_codes: list[str] | None = Field(None, max_length=100)
    asset_ids: list[uuid.UUID] | None = Field(None, max_length=200)


class ControlLinkIn(BaseModel):
    code: str = Field(max_length=20)
    axis: Axis = "likelihood"


class ControlLinksIn(BaseModel):
    links: list[ControlLinkIn] = Field(max_length=100)


class AssessmentIn(BaseModel):
    likelihood: int | None = None
    consequence: dict[str, int] | None = None
    current_l: int | None = None
    current_c: int | None = None
    current_reason: str | None = Field(None, max_length=2000)
    target_l: int | None = None
    target_c: int | None = None
    rationale: str | None = Field(None, max_length=5000)


class TreatmentIn(BaseModel):
    option: TreatmentOption
    note: str | None = Field(None, max_length=5000)
    budget: str | None = Field(None, max_length=100)
    due: date | None = None


class ActionIn(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    assignee_id: uuid.UUID | None = None
    due: date | None = None


class AcceptIn(BaseModel):
    statement: str = Field(min_length=1, max_length=2000)


class CloseIn(BaseModel):
    reason: str = Field(min_length=1, max_length=2000)


class SnapshotIn(BaseModel):
    label: str = Field(min_length=1, max_length=200)
