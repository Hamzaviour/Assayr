"""Training completion for managers: summary numbers and the Excel evidence report."""

import uuid
from collections import defaultdict

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from openpyxl import Workbook
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from assayr.catalogue.router import resolve_scope
from assayr.db import get_session
from assayr.exports import add_sheet, xlsx_response
from assayr.identity.deps import get_clock, require
from assayr.identity.rbac import Grant, Perm
from assayr.training.models import Assignment, Course
from assayr.training.service import counts, current_assignments, is_overdue

router = APIRouter(prefix="/training", tags=["training"])
STATUS_LABEL = {
    "assigned": "Not started",
    "in_progress": "In progress",
    "passed": "Passed",
    "failed": "Failed",
}


class CourseSummary(BaseModel):
    id: uuid.UUID
    title: str
    status: str
    assigned: int
    passed: int
    in_progress: int
    overdue: int
    failed: int
    pass_rate: float | None


class DepartmentSummary(BaseModel):
    department: str
    assigned: int
    passed: int
    completion: float | None


class TrainingSummary(BaseModel):
    courses: list[CourseSummary]
    departments: list[DepartmentSummary]


def published_current(db: Session, scope_id: uuid.UUID) -> list[Assignment]:
    """Current assignments of published courses in a scope (renewed ones are history)."""
    rows = db.scalars(
        select(Assignment)
        .join(Course, Assignment.course_id == Course.id)
        .where(Course.scope_id == scope_id, Course.status == "published")
    ).unique()
    by_course: dict = defaultdict(list)
    for a in rows:
        by_course[a.course_id].append(a)
    return [a for group in by_course.values() for a in current_assignments(group)]


def training_card(db: Session, scope_id: uuid.UUID, today) -> dict:
    current = published_current(db, scope_id)
    return {
        "assigned": len(current),
        "passed": sum(1 for a in current if a.status == "passed"),
        "overdue": sum(1 for a in current if is_overdue(a, today)),
    }


@router.get("/summary", response_model=TrainingSummary)
def training_summary(
    request: Request,
    grant: Grant = Depends(require(Perm.TRAINING_MANAGE)),
    db: Session = Depends(get_session),
    scope_id: uuid.UUID | None = None,
) -> TrainingSummary:
    scope = resolve_scope(db, scope_id, grant)
    today = get_clock(request)().date()
    courses = []
    for course in db.scalars(
        select(Course).where(Course.scope_id == scope.id, Course.status != "draft")
    ).unique():
        assignments = list(db.scalars(select(Assignment).where(Assignment.course_id == course.id)).unique())
        c = counts(assignments, today)
        courses.append(
            CourseSummary(
                id=course.id,
                title=course.title,
                status=course.status,
                **c.model_dump(),
                pass_rate=round(100 * c.passed / c.assigned, 1) if c.assigned else None,
            )
        )
    departments: dict[str, list[Assignment]] = defaultdict(list)
    for a in published_current(db, scope.id):
        departments[a.user.department or "No department"].append(a)
    return TrainingSummary(
        courses=sorted(courses, key=lambda c: c.title.lower()),
        departments=[
            DepartmentSummary(
                department=name,
                assigned=len(rows),
                passed=sum(1 for a in rows if a.status == "passed"),
                completion=round(100 * sum(1 for a in rows if a.status == "passed") / len(rows), 1),
            )
            for name, rows in sorted(departments.items())
        ],
    )


@router.get("/report.xlsx")
def training_report(
    grant: Grant = Depends(require(Perm.TRAINING_MANAGE)),
    db: Session = Depends(get_session),
    scope_id: uuid.UUID | None = None,
) -> Response:
    """Every assignment, including earlier years' — evidence for ISO 27001 A.6.3 and NIA awareness controls."""
    scope = resolve_scope(db, scope_id, grant)
    rows = db.scalars(
        select(Assignment)
        .join(Course, Assignment.course_id == Course.id)
        .where(Course.scope_id == scope.id)
        .order_by(Course.title, Assignment.assigned_at)
    ).unique()
    workbook = Workbook()
    header = [
        "Name",
        "Email",
        "Department",
        "Course",
        "Assigned",
        "Due",
        "Status",
        "Attempts",
        "Score",
        "Completed",
    ]
    body = []
    for a in rows:
        scores = [t.score for t in a.attempts if t.score is not None]
        body.append(
            [
                a.user.full_name,
                a.user.email,
                a.user.department,
                a.course.title,
                a.assigned_at.date(),
                a.due_at,
                STATUS_LABEL.get(a.status, a.status),
                sum(1 for t in a.attempts if t.submitted_at),
                max(scores) if scores else None,
                a.completed_at.date() if a.completed_at else None,
            ]
        )
    add_sheet(workbook, "Training completion", header, body)
    return xlsx_response(workbook, "training-completion.xlsx")
