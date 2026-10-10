"""Frozen copies of the risk register and what changed between two of them (clause 8.2 records)."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from assayr.risk.models import Risk
from assayr.risk.service import risk_row

COMPARED_LEVELS = ("current", "target")
COMPARED_FIELDS = ("status", "treatment")


def snapshot_rows(db: Session, scope_id: uuid.UUID) -> list[dict]:
    rows = []
    for risk in db.scalars(
        select(Risk).where(Risk.scope_id == scope_id, Risk.closed_at.is_(None)).order_by(Risk.seq)
    ).unique():
        row = risk_row(db, risk)
        if row.current is None:
            continue
        rows.append(
            {
                "code": row.code,
                "title": row.title,
                "owner": row.owner.full_name if row.owner else None,
                "status": row.status,
                "treatment": row.treatment_option,
                "inherent": row.inherent.model_dump() if row.inherent else None,
                "current": row.current.model_dump(),
                "target": row.target.model_dump() if row.target else None,
            }
        )
    return rows


def level_text(level: dict | None) -> str | None:
    return f"{level['band_label']} ({level['score']})" if level else None


def compare_rows(base: list[dict], head: list[dict]) -> dict:
    before = {row["code"]: row for row in base}
    after = {row["code"]: row for row in head}
    changed = []
    for code, row in after.items():
        old = before.get(code)
        if old is None:
            continue
        changes = []
        for field in COMPARED_LEVELS:
            was, now = level_text(old[field]), level_text(row[field])
            if was != now:
                changes.append({"field": field, "before": was, "after": now})
        for field in COMPARED_FIELDS:
            if old[field] != row[field]:
                changes.append({"field": field, "before": old[field], "after": row[field]})
        if changes:
            changed.append({"code": code, "title": row["title"], "changes": changes})
    return {
        "added": [code for code in after if code not in before],
        "removed": [code for code in before if code not in after],
        "changed": changed,
    }
