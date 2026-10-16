import re
import uuid

from fastapi import FastAPI, Request

import assayr.models  # noqa: F401
from assayr import __version__
from assayr.assets.router import router as assets_router
from assayr.audit.router import router as audit_router
from assayr.audits.router import router as audits_router
from assayr.catalogue.router import router as catalogue_router
from assayr.config import Settings, get_settings
from assayr.dashboard.router import router as dashboard_router
from assayr.db import Database, utcnow
from assayr.documents.router import router as documents_router
from assayr.evidence.router import router as evidence_router
from assayr.health import router as health_router
from assayr.identity.auth_router import router as auth_router
from assayr.identity.people_router import router as people_router
from assayr.identity.users_router import router as users_router
from assayr.nia.router import frameworks_router as nia_frameworks_router
from assayr.nia.router import router as nia_router
from assayr.privacy.breaches_router import router as privacy_breaches_router
from assayr.privacy.dpia_router import router as privacy_dpia_router
from assayr.privacy.processors_router import router as privacy_processors_router
from assayr.privacy.requests_router import router as privacy_requests_router
from assayr.privacy.router import router as privacy_router
from assayr.risk.library_router import router as risk_library_router
from assayr.risk.router import router as risk_router
from assayr.scoring.router import router as scoring_router
from assayr.soa.router import router as soa_router
from assayr.storage import BlobStore
from assayr.tasks.router import router as tasks_router
from assayr.training.courses_router import router as training_courses_router
from assayr.training.my_router import router as training_my_router
from assayr.training.report_router import router as training_report_router

_REQUEST_ID_UNSAFE = re.compile(r"[^A-Za-z0-9_-]")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(
        title="Assayr API",
        version=__version__,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        redoc_url=None,
    )
    app.state.settings = settings
    app.state.db = Database(settings.database_url)
    app.state.clock = utcnow
    app.state.store = BlobStore(settings.storage_dir)

    @app.middleware("http")
    async def request_id(request: Request, call_next):
        supplied = _REQUEST_ID_UNSAFE.sub("", request.headers.get("X-Request-Id", ""))[:64]
        request.state.request_id = supplied or uuid.uuid4().hex
        response = await call_next(request)
        response.headers["X-Request-Id"] = request.state.request_id
        return response

    app.include_router(health_router, prefix="/api/v1")
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(users_router, prefix="/api/v1")
    app.include_router(people_router, prefix="/api/v1")
    app.include_router(risk_library_router, prefix="/api/v1")
    app.include_router(assets_router, prefix="/api/v1")
    app.include_router(risk_router, prefix="/api/v1")
    app.include_router(tasks_router, prefix="/api/v1")
    app.include_router(soa_router, prefix="/api/v1")
    app.include_router(audit_router, prefix="/api/v1")
    app.include_router(catalogue_router, prefix="/api/v1")
    app.include_router(evidence_router, prefix="/api/v1")
    app.include_router(scoring_router, prefix="/api/v1")
    app.include_router(dashboard_router, prefix="/api/v1")
    app.include_router(nia_router, prefix="/api/v1")
    app.include_router(nia_frameworks_router, prefix="/api/v1")
    app.include_router(documents_router, prefix="/api/v1")
    app.include_router(audits_router, prefix="/api/v1")
    app.include_router(training_courses_router, prefix="/api/v1")
    app.include_router(training_my_router, prefix="/api/v1")
    app.include_router(training_report_router, prefix="/api/v1")
    app.include_router(privacy_router, prefix="/api/v1")
    app.include_router(privacy_processors_router, prefix="/api/v1")
    app.include_router(privacy_dpia_router, prefix="/api/v1")
    app.include_router(privacy_requests_router, prefix="/api/v1")
    app.include_router(privacy_breaches_router, prefix="/api/v1")
    return app
