import uuid
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from assayr.audit.service import record
from assayr.catalogue.access import check_active_user, rights_for
from assayr.catalogue.router import FORBIDDEN
from assayr.db import get_session
from assayr.identity.deps import actor_for, current_user, get_clock, require
from assayr.identity.models import User
from assayr.identity.rbac import Grant, Perm
from assayr.risk.models import Risk
from assayr.risk.schemas import TaskOut, task_out
from assayr.risk.service import refresh_risk
from assayr.tasks.models import Task

router = APIRouter(tags=["tasks"])


class TaskUpdateIn(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=300)
    status: Literal["todo", "in_progress", "blocked", "done", "cancelled"] | None = None
    due: date | None = None
    assignee_id: uuid.UUID | None = None


@router.patch("/tasks/{task_id}", response_model=TaskOut)
def update_task(
    task_id: uuid.UUID,
    body: TaskUpdateIn,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.RISKS_READ)),
    db: Session = Depends(get_session),
) -> TaskOut:
    task = db.get(Task, task_id)
    if task is None or not grant.allows(task.scope_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Task not found.")
    risk = db.get(Risk, uuid.UUID(task.entity_id)) if task.entity_type == "risk" else None
    editor = (
        risk is not None
        and rights_for(user, risk.scope_id, risk.owner_id, Perm.RISKS_WRITE, Perm.RISKS_WRITE_OWN).any
    )
    if not (editor or task.assignee_id == user.id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, FORBIDDEN)
    now = get_clock(request)()
    fields = body.model_fields_set
    diff: dict[str, list] = {}
    if "assignee_id" in fields and body.assignee_id != task.assignee_id:
        check_active_user(db, body.assignee_id, "Assignee")
        diff["assignee_id"] = [
            str(task.assignee_id) if task.assignee_id else None,
            str(body.assignee_id) if body.assignee_id else None,
        ]
        task.assignee_id = body.assignee_id
    for name in ("title", "status", "due"):
        if name not in fields:
            continue
        value = getattr(body, name)
        if value is None and name in ("title", "status"):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"{name.capitalize()} can't be empty.")
        if value != getattr(task, name):
            diff[name] = [
                str(getattr(task, name)) if getattr(task, name) is not None else None,
                str(value) if value is not None else None,
            ]
            setattr(task, name, value)
    if "status" in diff:
        task.done_at = now if task.status == "done" else None
    if diff:
        db.flush()
        if risk is not None:
            refresh_risk(db, risk, now)
        record(db, actor_for(request, user), "task.update", "task", str(task.id), diff=diff)
        db.commit()
    db.refresh(task)
    return task_out(task)
