import uuid
from datetime import date, datetime

from sqlalchemy import Date, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from assayr.db import Base, IdMixin, TimestampMixin, UTCDateTime
from assayr.identity.models import User

TASK_STATUSES = ("todo", "in_progress", "blocked", "done", "cancelled")


class Task(IdMixin, TimestampMixin, Base):
    """A unit of work attached to any record (a risk treatment action in 1b)."""

    __tablename__ = "task"
    __table_args__ = (Index("ix_task_entity", "entity_type", "entity_id"),)

    scope_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("scope.id", ondelete="CASCADE"))
    entity_type: Mapped[str] = mapped_column(String(30))
    entity_id: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(300))
    assignee_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user_account.id", ondelete="SET NULL"))
    due: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default="todo")
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user_account.id", ondelete="SET NULL")
    )
    done_at: Mapped[datetime | None] = mapped_column(UTCDateTime)

    assignee: Mapped[User | None] = relationship(foreign_keys=[assignee_id], lazy="joined")
