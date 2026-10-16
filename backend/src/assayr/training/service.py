"""Training rules: progress counts, overdue, attempts."""

import calendar
from dataclasses import dataclass
from datetime import date, datetime, timedelta

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


def target_users(db: Session, target: str) -> list:
    """Active users matching "all", "department:<name>" or "role:<name>" (names compared case-insensitively)."""
    from assayr.identity.models import User

    users = [u for u in db.scalars(select(User).where(User.is_active.is_(True))).unique()]
    kind, _, value = target.partition(":")
    if kind == "department":
        return [u for u in users if (u.department or "").strip().lower() == value]
    if kind == "role":
        return [u for u in users if any(a.role == value for a in u.role_assignments)]
    return users


def assign(db: Session, course: Course, users: list, source: str, due_days: int, now) -> int:
    """One assignment per person who has no current one for the course. Returns how many were created."""
    taken = set(
        db.scalars(
            select(Assignment.user_id).where(Assignment.course_id == course.id, Assignment.renewed.is_(False))
        )
    )
    created = 0
    for user in users:
        if user.id in taken:
            continue
        db.add(
            Assignment(
                course_id=course.id,
                user_id=user.id,
                source=source,
                assigned_at=now,
                due_at=now.date() + timedelta(days=due_days),
                material_progress=[],
            )
        )
        taken.add(user.id)
        created += 1
    db.flush()
    return created


def mark(assessment, answers: dict[str, list[str]]) -> tuple[float, list[str]]:
    """Percent score and the ids of questions answered wrongly. A question counts only if the chosen set
    equals the correct set; unknown questions and options that belong to other questions are ignored."""
    wrong: list[str] = []
    for question in assessment.questions:
        valid = {str(o.id) for o in question.options}
        chosen = {a for a in answers.get(str(question.id), []) if a in valid}
        correct = {str(o.id) for o in question.options if o.is_correct}
        if chosen != correct:
            wrong.append(str(question.id))
    total = len(assessment.questions)
    score = round(100 * (total - len(wrong)) / total, 1) if total else 100.0
    return score, wrong


@dataclass
class SweepResult:
    renewed: int = 0
    assigned: int = 0


def add_months(moment: datetime, months: int) -> datetime:
    month = moment.month - 1 + months
    year, month = moment.year + month // 12, month % 12 + 1
    day = min(moment.day, calendar.monthrange(year, month)[1])
    return moment.replace(year=year, month=month, day=day)


def sweep(db: Session, now: datetime) -> SweepResult:
    """Yearly refresh (a passed assignment comes back after the course's recurrence) and new joiners
    (people who now match a course's assignment rules). Safe to run any number of times."""
    result = SweepResult()
    courses = db.scalars(select(Course).where(Course.status == "published")).unique()
    for course in courses:
        if course.recurrence_months:
            due = db.scalars(
                select(Assignment).where(
                    Assignment.course_id == course.id,
                    Assignment.status == "passed",
                    Assignment.renewed.is_(False),
                )
            ).unique()
            renew = [
                a
                for a in due
                if a.completed_at and add_months(a.completed_at, course.recurrence_months) <= now
            ]
            for old in renew:
                old.renewed = True
            db.flush()
            result.renewed += assign(db, course, [a.user for a in renew], "renewal", course.due_days, now)
        for rule in course.rules:
            result.assigned += assign(
                db, course, target_users(db, rule.target), rule.target, course.due_days, now
            )
    return result
