"""My training: the signed-in person's own assignments, materials and assessment attempts."""

import random
import uuid
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from assayr.audit.service import record
from assayr.db import get_session
from assayr.identity.deps import actor_for, current_user, get_clock
from assayr.identity.models import User
from assayr.training.courses_router import material_file_response, material_out
from assayr.training.models import Assignment, Attempt
from assayr.training.schemas import MaterialOut
from assayr.training.service import attempts_allowed, is_overdue, mark

router = APIRouter(prefix="/my", tags=["training"])
NOT_FOUND = "Assignment not found."


class MyOptionOut(BaseModel):
    id: uuid.UUID
    text: str


class MyQuestionOut(BaseModel):
    id: uuid.UUID
    kind: str
    text: str
    options: list[MyOptionOut]


class MyAssessmentOut(BaseModel):
    pass_mark: int
    questions: list[MyQuestionOut]


class MyAttemptOut(BaseModel):
    submitted_at: datetime | None
    score: float | None
    passed: bool | None


class MyAssignmentOut(BaseModel):
    id: uuid.UUID
    course_title: str
    course_description: str | None
    status: str
    overdue: bool
    due_at: date
    completed_at: datetime | None
    material_count: int
    materials_done: int
    has_assessment: bool
    attempts_used: int
    attempts_left: int | None
    best_score: float | None


class MyAssignmentDetailOut(MyAssignmentOut):
    materials: list[MaterialOut]
    done: list[str]
    assessment: MyAssessmentOut | None
    assessment_locked: bool
    attempts: list[MyAttemptOut]


class AnswersIn(BaseModel):
    answers: dict[str, list[str]] = Field(max_length=200)


class ResultOut(BaseModel):
    score: float
    passed: bool
    wrong: list[str]
    attempts_left: int


def _used(a: Assignment) -> int:
    return sum(1 for t in a.attempts if t.submitted_at)


def _summary(a: Assignment, today: date) -> MyAssignmentOut:
    allowed = attempts_allowed(a)
    scores = [t.score for t in a.attempts if t.score is not None]
    material_ids = {str(m.id) for m in a.course.materials}
    return MyAssignmentOut(
        id=a.id,
        course_title=a.course.title,
        course_description=a.course.description,
        status=a.status,
        overdue=is_overdue(a, today),
        due_at=a.due_at,
        completed_at=a.completed_at,
        material_count=len(material_ids),
        materials_done=len(material_ids & set(a.material_progress or [])),
        has_assessment=a.course.assessment is not None,
        attempts_used=_used(a),
        attempts_left=max(0, allowed - _used(a)) if allowed is not None else None,
        best_score=max(scores) if scores else None,
    )


def _assessment(a: Assignment) -> MyAssessmentOut | None:
    assessment = a.course.assessment
    if assessment is None:
        return None
    questions = list(assessment.questions)
    if assessment.shuffle:
        random.Random(str(a.id)).shuffle(questions)  # stable order for this person
    return MyAssessmentOut(
        pass_mark=assessment.pass_mark,
        questions=[
            MyQuestionOut(
                id=q.id,
                kind=q.kind,
                text=q.text,
                options=[MyOptionOut(id=o.id, text=o.text) for o in q.options],
            )
            for q in questions
        ],
    )


def _materials_done(a: Assignment) -> bool:
    return {str(m.id) for m in a.course.materials} <= set(a.material_progress or [])


def _detail(a: Assignment, today: date) -> MyAssignmentDetailOut:
    return MyAssignmentDetailOut(
        **_summary(a, today).model_dump(),
        materials=[material_out(m) for m in a.course.materials],
        done=list(a.material_progress or []),
        assessment=_assessment(a),
        assessment_locked=not _materials_done(a),
        attempts=[
            MyAttemptOut(submitted_at=t.submitted_at, score=t.score, passed=t.passed) for t in a.attempts
        ],
    )


def _mine(db: Session, user: User, assignment_id: uuid.UUID) -> Assignment:
    a = db.get(Assignment, assignment_id)
    if a is None or a.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND)
    return a


@router.get("/assignments", response_model=list[MyAssignmentOut])
def my_assignments(
    request: Request, user: User = Depends(current_user), db: Session = Depends(get_session)
) -> list[MyAssignmentOut]:
    today = get_clock(request)().date()
    rows = db.scalars(
        select(Assignment)
        .where(Assignment.user_id == user.id, Assignment.renewed.is_(False))
        .order_by(Assignment.due_at)
    ).unique()
    return [_summary(a, today) for a in rows if a.course.status != "draft"]


@router.get("/assignments/{assignment_id}", response_model=MyAssignmentDetailOut)
def my_assignment(
    assignment_id: uuid.UUID,
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_session),
) -> MyAssignmentDetailOut:
    return _detail(_mine(db, user, assignment_id), get_clock(request)().date())


@router.get("/assignments/{assignment_id}/materials/{material_id}/file")
def my_material_file(
    assignment_id: uuid.UUID,
    material_id: uuid.UUID,
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_session),
) -> FileResponse:
    a = _mine(db, user, assignment_id)
    material = next((m for m in a.course.materials if m.id == material_id), None)
    if material is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Material not found.")
    return material_file_response(request, material)


@router.post(
    "/assignments/{assignment_id}/materials/{material_id}/done", response_model=MyAssignmentDetailOut
)
def material_done(
    assignment_id: uuid.UUID,
    material_id: uuid.UUID,
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_session),
) -> MyAssignmentDetailOut:
    a = _mine(db, user, assignment_id)
    if not any(m.id == material_id for m in a.course.materials):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Material not found.")
    now = get_clock(request)()
    if str(material_id) not in (a.material_progress or []):
        a.material_progress = [*(a.material_progress or []), str(material_id)]
    if a.status == "assigned":
        a.status = "in_progress"
    if a.course.assessment is None and _materials_done(a) and a.status != "passed":
        a.status = "passed"
        a.completed_at = now
        record(
            db,
            actor_for(request, user),
            "training.passed",
            "assignment",
            str(a.id),
            diff={"course": a.course.title},
        )
    db.commit()
    return _detail(a, now.date())


@router.post("/assignments/{assignment_id}/attempts", response_model=ResultOut)
def submit_attempt(
    assignment_id: uuid.UUID,
    body: AnswersIn,
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_session),
) -> ResultOut:
    a = _mine(db, user, assignment_id)
    assessment = a.course.assessment
    if assessment is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "This course has no assessment.")
    if a.status == "passed":
        raise HTTPException(status.HTTP_409_CONFLICT, "You have already passed this course.")
    allowed = attempts_allowed(a) or 0
    if _used(a) >= allowed:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "You have used all your attempts. Ask your ISMS manager for another attempt.",
        )
    if not _materials_done(a):
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Finish all the course materials before the assessment."
        )
    now = get_clock(request)()
    score, wrong = mark(assessment, body.answers)
    passed = score >= assessment.pass_mark
    a.attempts.append(
        Attempt(started_at=now, submitted_at=now, answers=body.answers, score=score, passed=passed)
    )
    left = allowed - _used(a)
    if passed:
        a.status, a.completed_at = "passed", now
    elif left <= 0:
        a.status = "failed"
    else:
        a.status = "in_progress"
    record(
        db,
        actor_for(request, user),
        "training.attempt",
        "assignment",
        str(a.id),
        diff={"course": a.course.title, "score": score, "passed": passed},
    )
    db.commit()
    return ResultOut(score=score, passed=passed, wrong=wrong, attempts_left=max(0, left))
