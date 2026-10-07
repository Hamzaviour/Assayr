import re
import uuid

from fastapi import FastAPI, Request

import assayr.models  # noqa: F401
from assayr import __version__
from assayr.config import Settings, get_settings
from assayr.db import Database, utcnow
from assayr.health import router as health_router

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

    @app.middleware("http")
    async def request_id(request: Request, call_next):
        supplied = _REQUEST_ID_UNSAFE.sub("", request.headers.get("X-Request-Id", ""))[:64]
        request.state.request_id = supplied or uuid.uuid4().hex
        response = await call_next(request)
        response.headers["X-Request-Id"] = request.state.request_id
        return response

    app.include_router(health_router, prefix="/api/v1")
    return app
