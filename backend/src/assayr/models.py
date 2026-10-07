"""Import every model module so Base.metadata is complete (used by create_all and Alembic)."""

from assayr.audit.models import AuditLog  # noqa: F401
from assayr.catalogue.models import (  # noqa: F401
    Control,
    ControlRequirement,
    EvidenceSlot,
    Framework,
    Requirement,
)
from assayr.identity.models import Organization, RoleAssignment, Scope, User, UserSession  # noqa: F401
