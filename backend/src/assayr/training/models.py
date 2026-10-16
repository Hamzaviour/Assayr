import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Date,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from assayr.db import Base, IdMixin, TimestampMixin, UTCDateTime
from assayr.identity.models import User

COURSE_STATUSES = ("draft", "published", "archived")
QUESTION_KINDS = ("single", "multiple", "true_false")
ASSIGNMENT_STATUSES = ("assigned", "in_progress", "passed", "failed")


class Course(IdMixin, TimestampMixin, Base):
    """A training course: materials to watch or read, optionally followed by an assessment."""

    __tablename__ = "course"

    scope_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("scope.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="draft")
    recurrence_months: Mapped[int | None] = mapped_column(Integer)  # None = one-off; the API defaults to 12
    due_days: Mapped[int] = mapped_column(Integer, default=30)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user_account.id", ondelete="SET NULL")
    )

    materials: Mapped[list["CourseMaterial"]] = relationship(
        back_populates="course", order_by="CourseMaterial.sort_order", cascade="all, delete-orphan"
    )
    rules: Mapped[list["CourseRule"]] = relationship(back_populates="course", cascade="all, delete-orphan")
    assessment: Mapped["Assessment | None"] = relationship(
        back_populates="course", cascade="all, delete-orphan", uselist=False
    )


class CourseMaterial(IdMixin, Base):
    """A Google Drive video/document (shown in Drive's preview player) or a file stored on the server."""

    __tablename__ = "course_material"

    course_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("course.id", ondelete="CASCADE"))
    sort_order: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(10))
    title: Mapped[str] = mapped_column(String(200))
    drive_file_id: Mapped[str | None] = mapped_column(String(100))
    sha256: Mapped[str | None] = mapped_column(String(64))
    filename: Mapped[str | None] = mapped_column(String(255))
    mime: Mapped[str | None] = mapped_column(String(100))
    size: Mapped[int | None] = mapped_column(BigInteger)

    course: Mapped[Course] = relationship(back_populates="materials")


class CourseRule(IdMixin, Base):
    """Who a course is assigned to automatically, so people who join later are picked up."""

    __tablename__ = "course_rule"
    __table_args__ = (UniqueConstraint("course_id", "target", name="uq_course_rule_course_target"),)

    course_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("course.id", ondelete="CASCADE"))
    target: Mapped[str] = mapped_column(String(150))  # "all", "department:<name>", "role:<name>"

    course: Mapped[Course] = relationship(back_populates="rules")


class Assessment(IdMixin, Base):
    __tablename__ = "assessment"

    course_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("course.id", ondelete="CASCADE"), unique=True)
    pass_mark: Mapped[int] = mapped_column(Integer, default=80)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    shuffle: Mapped[bool] = mapped_column(Boolean, default=True)

    course: Mapped[Course] = relationship(back_populates="assessment")
    questions: Mapped[list["Question"]] = relationship(
        back_populates="assessment", order_by="Question.sort_order", cascade="all, delete-orphan"
    )


class Question(IdMixin, Base):
    __tablename__ = "question"

    assessment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("assessment.id", ondelete="CASCADE"))
    sort_order: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(20))
    text: Mapped[str] = mapped_column(Text)

    assessment: Mapped[Assessment] = relationship(back_populates="questions")
    options: Mapped[list["QuestionOption"]] = relationship(
        back_populates="question", order_by="QuestionOption.sort_order", cascade="all, delete-orphan"
    )


class QuestionOption(IdMixin, Base):
    __tablename__ = "question_option"

    question_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("question.id", ondelete="CASCADE"))
    sort_order: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(String(500))
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False)

    question: Mapped[Question] = relationship(back_populates="options")


class Assignment(IdMixin, Base):
    """One person's copy of a course: progress, attempts and the result."""

    __tablename__ = "assignment"

    course_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("course.id", ondelete="CASCADE"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_account.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(20), default="assigned")
    source: Mapped[str] = mapped_column(String(150))
    assigned_at: Mapped[datetime] = mapped_column(UTCDateTime)
    due_at: Mapped[date] = mapped_column(Date)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    extra_attempts: Mapped[int] = mapped_column(Integer, default=0)
    material_progress: Mapped[list[str]] = mapped_column(JSON, default=list)
    renewed: Mapped[bool] = mapped_column(Boolean, default=False)

    course: Mapped[Course] = relationship()
    user: Mapped[User] = relationship(lazy="joined")
    attempts: Mapped[list["Attempt"]] = relationship(
        back_populates="assignment", order_by="Attempt.started_at", cascade="all, delete-orphan"
    )


class Attempt(IdMixin, Base):
    __tablename__ = "attempt"

    assignment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("assignment.id", ondelete="CASCADE"))
    started_at: Mapped[datetime] = mapped_column(UTCDateTime)
    submitted_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    answers: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    score: Mapped[float | None] = mapped_column(Float)
    passed: Mapped[bool | None] = mapped_column(Boolean)

    assignment: Mapped[Assignment] = relationship(back_populates="attempts")
