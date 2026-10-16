from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from assayr.audit.service import record
from assayr.db import get_session
from assayr.identity.deps import CSRF_COOKIE, SESSION_COOKIE, actor_for, current_user, get_clock
from assayr.identity.models import User, UserSession
from assayr.identity.schemas import LoginIn, PasswordChangeIn, UserOut
from assayr.identity.security import (
    WeakPasswordError,
    dummy_hash,
    hash_password,
    needs_rehash,
    new_token,
    normalize_email,
    token_digest,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])

GENERIC_FAILURE = "Email or password is incorrect, or the account is temporarily locked."


@router.post("/login", response_model=UserOut)
def login(body: LoginIn, request: Request, response: Response, db: Session = Depends(get_session)) -> UserOut:
    settings = request.app.state.settings
    now = get_clock(request)()
    email = normalize_email(body.email)
    user = db.scalar(select(User).where(User.email == email))

    def fail(reason: str) -> HTTPException:
        record(
            db,
            actor_for(request, user, email),
            "auth.login_failed",
            "user",
            str(user.id) if user else None,
            diff={"reason": reason},
        )
        db.commit()
        return HTTPException(status.HTTP_401_UNAUTHORIZED, GENERIC_FAILURE)

    if user is None:
        verify_password(dummy_hash(), body.password)
        raise fail("unknown_user")
    if user.locked_until and user.locked_until > now:
        verify_password(dummy_hash(), body.password)
        raise fail("locked")
    if not user.is_active or not user.password_hash or not verify_password(user.password_hash, body.password):
        # Increment in the database, not from the loaded value, so parallel attempts are all counted.
        failures = db.execute(
            update(User)
            .where(User.id == user.id)
            .values(failed_logins=User.failed_logins + 1)
            .returning(User.failed_logins)
        ).scalar_one()
        if failures >= settings.login_max_failures:
            db.execute(
                update(User)
                .where(User.id == user.id)
                .values(locked_until=now + timedelta(minutes=settings.login_lockout_minutes), failed_logins=0)
            )
        raise fail("inactive" if not user.is_active else "bad_password")

    user.failed_logins = 0
    user.locked_until = None
    user.last_login_at = now
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(body.password)
    token, csrf = new_token(), new_token()
    absolute = timedelta(hours=settings.session_absolute_hours)
    db.add(
        UserSession(
            id=token_digest(token),
            user_id=user.id,
            csrf_token=csrf,
            created_at=now,
            last_seen_at=now,
            expires_at=now + absolute,
            ip=request.client.host if request.client else None,
        )
    )
    record(db, actor_for(request, user), "auth.login", "user", str(user.id))
    db.commit()
    max_age = int(absolute.total_seconds())
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=max_age,
        httponly=True,
        secure=settings.secure_cookies,
        samesite="strict",
        path="/",
    )
    response.set_cookie(
        CSRF_COOKIE,
        csrf,
        max_age=max_age,
        httponly=False,
        secure=settings.secure_cookies,
        samesite="strict",
        path="/",
    )
    return UserOut.from_user(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request, user: User = Depends(current_user), db: Session = Depends(get_session)
) -> Response:
    session = db.get(UserSession, request.state.session_id)
    if session is not None:
        db.delete(session)
    record(db, actor_for(request, user), "auth.logout", "user", str(user.id))
    db.commit()
    secure = request.app.state.settings.secure_cookies
    resp = Response(status_code=status.HTTP_204_NO_CONTENT)
    resp.delete_cookie(SESSION_COOKIE, path="/", secure=secure, httponly=True, samesite="strict")
    resp.delete_cookie(CSRF_COOKIE, path="/", secure=secure, samesite="strict")
    return resp


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)) -> UserOut:
    return UserOut.from_user(user)


@router.post("/password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    body: PasswordChangeIn,
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_session),
) -> Response:
    """Change your own password; clears a temporary password and keeps this session signed in."""
    if not user.password_hash or not verify_password(user.password_hash, body.current_password):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Your current password is not correct.")
    if body.new_password == body.current_password:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "Choose a password different from the current one."
        )
    try:
        user.password_hash = hash_password(body.new_password)
    except WeakPasswordError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    was_temporary = user.must_change_password
    user.must_change_password = False
    db.execute(
        delete(UserSession).where(UserSession.user_id == user.id, UserSession.id != request.state.session_id)
    )
    record(
        db,
        actor_for(request, user),
        "auth.password_change",
        "user",
        str(user.id),
        diff={"temporary": [was_temporary, False]},
    )
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
