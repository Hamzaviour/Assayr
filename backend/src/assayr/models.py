"""Import every model module so Base.metadata is complete (used by create_all and Alembic)."""

from assayr.identity.models import Organization, RoleAssignment, Scope, User, UserSession  # noqa: F401
