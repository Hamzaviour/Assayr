"""Import every model module so Base.metadata is complete (used by create_all and Alembic)."""

from assayr.assets.models import Asset  # noqa: F401
from assayr.audit.models import AuditLog  # noqa: F401
from assayr.audits.models import Audit, AuditItem  # noqa: F401
from assayr.catalogue.models import (  # noqa: F401
    Control,
    ControlRequirement,
    EvidenceSlot,
    Framework,
    Requirement,
)
from assayr.documents.models import Document, DocumentControl  # noqa: F401
from assayr.evidence.models import (  # noqa: F401
    Artefact,
    ArtefactLink,
    ArtefactVersion,
    RuleResult,
    VerificationRun,
)
from assayr.identity.models import Organization, RoleAssignment, Scope, User, UserSession  # noqa: F401
from assayr.jobs import Job  # noqa: F401
from assayr.privacy.models import (  # noqa: F401, E402
    ActivityProcessor,
    Dpia,
    DpiaRisk,
    ProcessingActivity,
    ProcessingAsset,
    Processor,
    SubjectRequest,
)
from assayr.risk.models import (  # noqa: F401
    MethodologyVersion,
    Risk,
    RiskAcceptance,
    RiskAssessment,
    RiskControl,
    RiskSnapshot,
    RiskTemplate,
    Threat,
    Vulnerability,
)
from assayr.scoring.models import Attestation, ScoreSnapshot, StatusTransition  # noqa: F401
from assayr.soa.models import SoaVersion  # noqa: F401
from assayr.tasks.models import Task  # noqa: F401
from assayr.training.models import (  # noqa: F401, E402
    Assessment,
    Assignment,
    Attempt,
    Course,
    CourseMaterial,
    CourseRule,
    Question,
    QuestionOption,
)
