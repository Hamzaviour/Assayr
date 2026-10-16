import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from assayr.catalogue.schemas import OwnerOut

Framework = Literal["iso27001", "nia-2.1"]
Result = Literal["pass", "fail", "partial", "na"]
TestType = Literal["DA", "OEA", "Both"]


class AuditIn(BaseModel):
    framework: Framework
    title: str = Field(min_length=1, max_length=200)
    period_start: date | None = None
    period_end: date | None = None
    auditor_id: uuid.UUID | None = None
    scope_note: str | None = Field(None, max_length=5000)


class AuditUpdateIn(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=200)
    period_start: date | None = None
    period_end: date | None = None
    auditor_id: uuid.UUID | None = None
    scope_note: str | None = Field(None, max_length=5000)
    conclusion: str | None = Field(None, max_length=10000)


class AddItemsIn(BaseModel):
    all: bool = False
    domain: str | None = Field(None, max_length=60)
    refs: list[str] | None = Field(None, max_length=500)

    @model_validator(mode="after")
    def _one_choice(self):
        if sum([self.all, self.domain is not None, self.refs is not None]) != 1:
            raise ValueError("Choose all controls, one domain or a list of references.")
        return self


class ItemUpdateIn(BaseModel):
    domain: str | None = Field(None, min_length=1, max_length=200)
    sub_domain: str | None = Field(None, min_length=1, max_length=200)
    assessment_area: str | None = Field(None, max_length=5000)
    test_type: TestType | None = None
    requirement: Literal["M", "A"] | None = None
    result: Result | None = None
    notes: str | None = Field(None, max_length=5000)


class ReopenIn(BaseModel):
    reason: str = Field(min_length=1, max_length=2000)


class ItemOut(BaseModel):
    id: uuid.UUID
    ref: str
    sort_order: int
    domain: str
    sub_domain: str
    assessment_area: str | None
    test_type: str | None
    requirement: str | None
    result: str | None
    notes: str | None

    model_config = {"from_attributes": True}


class AuditOut(BaseModel):
    id: uuid.UUID
    framework: str
    title: str
    period_start: date | None
    period_end: date | None
    auditor: OwnerOut | None
    scope_note: str | None
    conclusion: str | None
    status: str
    completed_at: datetime | None
    completed_by: OwnerOut | None
    created_at: datetime
    counts: dict[str, int]
    can_write: bool
    can_reopen: bool


class AuditDetailOut(AuditOut):
    items: list[ItemOut]


class ImportOut(BaseModel):
    audit: AuditOut
    imported: int
    unknown_refs: list[str]
    skipped_rows: list[str] = []
