import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from assayr.catalogue.schemas import OwnerOut

Grade = Literal["major", "minor", "observation", "ofi"]


class FindingIn(BaseModel):
    """Raise a finding from an audit row; every other field falls back to the defaults for its result."""

    audit_item_id: uuid.UUID
    title: str | None = Field(None, min_length=1, max_length=300)
    description: str | None = Field(None, max_length=10000)
    grade: Grade | None = None
    owner_id: uuid.UUID | None = None
    due_date: date | None = None
    root_cause: str | None = Field(None, max_length=10000)


class FindingUpdateIn(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=300)
    description: str | None = Field(None, max_length=10000)
    grade: Grade | None = None
    owner_id: uuid.UUID | None = None
    due_date: date | None = None
    root_cause: str | None = Field(None, max_length=10000)
    correction: str | None = Field(None, max_length=10000)
    response: str | None = Field(None, max_length=10000)


class ActionIn(BaseModel):
    description: str = Field(min_length=1, max_length=5000)
    owner_id: uuid.UUID | None = None
    due_date: date | None = None


class ActionUpdateIn(BaseModel):
    description: str | None = Field(None, min_length=1, max_length=5000)
    owner_id: uuid.UUID | None = None
    due_date: date | None = None
    status: Literal["open", "done"] | None = None
    done_note: str | None = Field(None, max_length=5000)


class VerifyIn(BaseModel):
    effective: bool
    note: str = Field(min_length=1, max_length=5000)


class CloseIn(BaseModel):
    response: str = Field(min_length=1, max_length=10000)


class ReasonIn(BaseModel):
    reason: str = Field(min_length=1, max_length=2000)


class RaiseIn(BaseModel):
    """Raise findings for several rows of one audit: chosen rows, or every eligible row."""

    item_ids: list[uuid.UUID] | None = Field(None, max_length=1000)
    all: bool = False


class Link(BaseModel):
    id: uuid.UUID
    title: str


class RiskLink(BaseModel):
    id: uuid.UUID
    code: str


class FileOut(BaseModel):
    id: uuid.UUID
    filename: str
    size: int
    uploaded_by: OwnerOut | None
    uploaded_at: datetime


class ActionOut(BaseModel):
    id: uuid.UUID
    seq: int
    description: str
    owner: OwnerOut | None
    due_date: date | None
    status: str
    overdue: bool
    done_at: datetime | None
    done_note: str | None
    files: list[FileOut]
    can_edit: bool
    can_complete: bool


class VerificationOut(BaseModel):
    verifier: OwnerOut | None
    effective: bool
    note: str
    verified_at: datetime


class FindingOut(BaseModel):
    id: uuid.UUID
    code: str
    title: str
    grade: str
    status: str
    source: str
    framework: str | None
    ref: str | None
    owner: OwnerOut | None
    due_date: date | None
    overdue: bool
    audit: Link | None
    audit_item_id: uuid.UUID | None
    actions_open: int
    actions_total: int
    risk: RiskLink | None
    raised_at: datetime
    closed_at: datetime | None


class FindingDetailOut(FindingOut):
    description: str | None
    root_cause: str | None
    correction: str | None
    response: str | None
    raised_by: OwnerOut | None
    actions: list[ActionOut]
    verifications: list[VerificationOut]
    can_edit: bool
    can_edit_capa: bool
    can_add_action: bool
    can_verify: bool
    can_close: bool
    can_reopen: bool
    can_raise_risk: bool


class SummaryOut(BaseModel):
    open: int
    overdue: int
    by_grade: dict[str, int]
    by_status: dict[str, int]


class RaiseOut(BaseModel):
    created: list[FindingOut]
    existing: int
