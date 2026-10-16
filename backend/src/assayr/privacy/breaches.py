"""Breach notification rules shared by the register and the summary."""

from datetime import datetime

from assayr.privacy.models import Breach


def pending_notifications(b: Breach) -> list[str]:
    """Notifications that are required and not yet made."""
    pending = []
    if b.regulator_notify == "required" and b.regulator_notified_at is None:
        pending.append("regulator")
    if b.people_notify == "required" and b.people_notified_at is None:
        pending.append("people")
    return pending


def notification_overdue(b: Breach, now: datetime) -> bool:
    return bool(pending_notifications(b)) and now > b.notify_deadline
