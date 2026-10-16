import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

QuestionKind = Literal["single", "multiple", "true_false"]


class CourseIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(None, max_length=5000)
    recurrence_months: int | None = Field(12, ge=1, le=60)
    due_days: int = Field(30, ge=1, le=365)


class CourseUpdateIn(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = Field(None, max_length=5000)
    recurrence_months: int | None = Field(None, ge=1, le=60)
    due_days: int | None = Field(None, ge=1, le=365)


class DriveMaterialIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    url: str = Field(min_length=1, max_length=500)


class MaterialUpdateIn(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=200)
    sort_order: int | None = Field(None, ge=0, le=10_000)


class OptionIn(BaseModel):
    text: str = Field(min_length=1, max_length=500)
    is_correct: bool = False


class QuestionIn(BaseModel):
    kind: QuestionKind
    text: str = Field(min_length=1, max_length=2000)
    options: list[OptionIn] = Field(min_length=2, max_length=8)

    @model_validator(mode="after")
    def _check(self):
        correct = sum(o.is_correct for o in self.options)
        if self.kind == "true_false":
            if [o.text.strip().lower() for o in self.options] != ["true", "false"]:
                raise ValueError('A true/false question has exactly the options "True" and "False".')
        if self.kind in ("single", "true_false") and correct != 1:
            raise ValueError("Mark exactly one correct answer.")
        if self.kind == "multiple" and correct < 1:
            raise ValueError("Mark at least one correct answer.")
        return self


class AssessmentIn(BaseModel):
    pass_mark: int = Field(80, ge=1, le=100)
    max_attempts: int = Field(3, ge=1, le=20)
    shuffle: bool = True
    questions: list[QuestionIn] = Field(max_length=100)


class OptionOut(BaseModel):
    id: uuid.UUID
    text: str
    is_correct: bool

    model_config = {"from_attributes": True}


class QuestionOut(BaseModel):
    id: uuid.UUID
    kind: str
    text: str
    options: list[OptionOut]

    model_config = {"from_attributes": True}


class AssessmentOut(BaseModel):
    pass_mark: int
    max_attempts: int
    shuffle: bool
    questions: list[QuestionOut]

    model_config = {"from_attributes": True}


class MaterialOut(BaseModel):
    id: uuid.UUID
    sort_order: int
    kind: str
    title: str
    drive_file_id: str | None
    preview_url: str | None
    filename: str | None
    mime: str | None
    size: int | None


class CourseCounts(BaseModel):
    assigned: int = 0
    passed: int = 0
    in_progress: int = 0
    overdue: int = 0
    failed: int = 0


class CourseOut(BaseModel):
    id: uuid.UUID
    title: str
    description: str | None
    status: str
    recurrence_months: int | None
    due_days: int
    created_at: datetime
    material_count: int
    question_count: int
    counts: CourseCounts


class CourseDetailOut(CourseOut):
    materials: list[MaterialOut]
    assessment: AssessmentOut | None
    rules: list[str]
    has_assignments: bool


class AssignIn(BaseModel):
    target: Literal["all"] | None = None
    department: str | None = Field(None, min_length=1, max_length=100)
    role: str | None = Field(None, min_length=1, max_length=40)
    user_ids: list[uuid.UUID] | None = Field(None, max_length=2000)
    due_days: int | None = Field(None, ge=1, le=365)

    @model_validator(mode="after")
    def _one(self):
        if sum(x is not None for x in (self.target, self.department, self.role, self.user_ids)) != 1:
            raise ValueError("Choose everyone, one department, one role or a list of people.")
        return self


class AssignOut(BaseModel):
    created: int


class AssignmentRowOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    full_name: str
    email: str
    department: str | None
    status: str
    overdue: bool
    assigned_at: datetime
    due_at: date
    completed_at: datetime | None
    attempts: int
    attempts_allowed: int | None
    best_score: float | None


class ExtraAttemptsIn(BaseModel):
    extra: int = Field(ge=1, le=10)
    reason: str = Field(min_length=1, max_length=2000)
