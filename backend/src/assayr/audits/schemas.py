import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from assayr.catalogue.schemas import OwnerOut

Framework = Literal["iso27001", "nia-2.1", "iso42001", "soc2"]
Result = Literal["pass", "fail", "partial", "na", "no_exception", "exception", "not_tested"]
PERIOD_ORDER = "The period ends before it starts."
PERIOD_NEEDED = "A SOC 2 Type 2 audit needs an observation period (from and to)."


def period_problem(framework: str, start: date | None, end: date | None) -> str | None:
    if start and end and end < start:
        return PERIOD_ORDER
    if framework == "soc2" and (start is None or end is None):
        return PERIOD_NEEDED
    return None


TestType = Literal["DA", "OEA", "Both"]


class AuditIn(BaseModel):
    framework: Framework
    title: str = Field(min_length=1, max_length=200)
    period_start: date | None = None
    period_end: date | None = None
    auditor_id: uuid.UUID | None = None
    scope_note: str | None = Field(None, max_length=5000)

    @model_validator(mode="after")
    def _period(self):
        problem = period_problem(self.framework, self.period_start, self.period_end)
        if problem:
            raise ValueError(problem)
        return self


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
    population: str | None = Field(None, max_length=2000)
    sample_size: int | None = Field(None, ge=0, le=100000)
    samples_tested: int | None = Field(None, ge=0, le=100000)
    exception_note: str | None = Field(None, max_length=5000)


class ReopenIn(BaseModel):
    reason: str = Field(min_length=1, max_length=2000)


class FindingChip(BaseModel):
    id: uuid.UUID
    code: str
    status: str


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
    population: str | None = None
    sample_size: int | None = None
    samples_tested: int | None = None
    exception_note: str | None = None
    finding: FindingChip | None = None
    result_changed: bool = False

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
