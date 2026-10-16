"""Training rules: progress counts, overdue, attempts."""

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from assayr.training.models import Assignment, Course
from assayr.training.schemas import CourseCounts


def is_overdue(assignment: Assignment, today: date) -> bool:
    return assignment.status not in ("passed", "failed") and assignment.due_at < today


def attempts_allowed(assignment: Assignment) -> int | None:
    assessment = assignment.course.assessment
    return assessment.max_attempts + assignment.extra_attempts if assessment else None


def course_assignments(db: Session, course: Course) -> list[Assignment]:
    return list(db.scalars(select(Assignment).where(Assignment.course_id == course.id)).unique())


def current_assignments(assignments: list[Assignment]) -> list[Assignment]:
    """The latest assignment per person (earlier, renewed ones are history)."""
    latest: dict = {}
    for a in sorted(assignments, key=lambda a: a.assigned_at):
        latest[a.user_id] = a
    return list(latest.values())


def counts(assignments: list[Assignment], today: date) -> CourseCounts:
    current = current_assignments(assignments)
    return CourseCounts(
        assigned=len(current),
        passed=sum(1 for a in current if a.status == "passed"),
        in_progress=sum(1 for a in current if a.status == "in_progress"),
        overdue=sum(1 for a in current if is_overdue(a, today)),
        failed=sum(1 for a in current if a.status == "failed"),
    )
