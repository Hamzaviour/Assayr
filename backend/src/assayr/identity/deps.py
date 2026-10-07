import secrets
from collections.abc import Callable
from datetime import datetime, timedelta

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from assayr.audit.service import Actor
from assayr.db import get_session
from assayr.identity.models import User, UserSession
from assayr.identity.rbac import Grant, Perm, grant_for
from assayr.identity.security import token_digest

SESSION_COOKIE = "assayr_session"
CSRF_COOKIE = "assayr_csrf"
CSRF_HEADER = "X-CSRF-Token"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
_LAST_SEEN_RESOLUTION = timedelta(seconds=60)


def get_clock(request: Request) -> Callable[[], datetime]:
    return request.app.state.clock


def current_user(request: Request, db: Session = Depends(get_session)) -> User:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not signed in.")
    settings = request.app.state.settings
    now = get_clock(request)()
    session = db.get(UserSession, token_digest(token))
    expired = session is not None and (
        now >= session.expires_at
        or now - session.last_seen_at > timedelta(minutes=settings.session_idle_minutes)
    )
    if session is None or expired:
        if session is not None:
            db.delete(session)
            db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Your session has expired. Sign in again.")
    if request.method not in SAFE_METHODS:
        supplied = request.headers.get(CSRF_HEADER, "")
        if not supplied or not secrets.compare_digest(supplied, session.csrf_token):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, "Missing or invalid CSRF token. Reload the page and try again."
            )
    user = db.get(User, session.user_id)
    if user is None or not user.is_active:
        db.delete(session)
        db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Your session has expired. Sign in again.")
    if now - session.last_seen_at > _LAST_SEEN_RESOLUTION:
        session.last_seen_at = now
        db.commit()
    request.state.session_id = session.id
    return user


def require(perm: Perm) -> Callable[..., Grant]:
    def dependency(user: User = Depends(current_user)) -> Grant:
        grant = grant_for(((a.role, a.scope_id) for a in user.role_assignments), perm)
        if not grant.any:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "You don't have permission to do this.")
        return grant

    return dependency


def require_global(perm: Perm) -> Callable[..., Grant]:
    """For data that is not partitioned by scope (users, the audit trail): a scoped grant is not enough."""

    def dependency(user: User = Depends(current_user)) -> Grant:
        grant = grant_for(((a.role, a.scope_id) for a in user.role_assignments), perm)
        if not grant.all_scopes:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "You don't have permission to do this.")
        return grant

    return dependency


def actor_for(request: Request, user: User | None, email: str | None = None) -> Actor:
    return Actor(
        id=user.id if user else None,
        email=user.email if user else email,
        ip=request.client.host if request.client else None,
        request_id=getattr(request.state, "request_id", None),
    )
