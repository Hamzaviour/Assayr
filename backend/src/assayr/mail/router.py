"""Mail server settings (platform administrators), a test email, and each person's digest opt-out."""

import re
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from assayr.audit.service import record
from assayr.db import get_session
from assayr.identity.deps import actor_for, current_user, get_clock, require_global
from assayr.identity.models import User
from assayr.identity.rbac import Perm
from assayr.mail.crypto import decrypt, encrypt
from assayr.mail.models import MailLog, MailSettings
from assayr.mail.sender import Connection, MailError, Outgoing

router = APIRouter(tags=["mail"])
_ADDRESS = re.compile(r"^[^@\s<>]+@[^@\s<>]+\.[^@\s<>]+$")
NO_KEY = (
    "This server has no ASSAYR_SECRET_KEY, so the password can not be stored safely. "
    "Run the newer installer (it adds one), or add ASSAYR_SECRET_KEY to assayr.env and restart Assayr."
)


class MailSettingsIn(BaseModel):
    enabled: bool = False
    host: str | None = Field(None, max_length=255)
    port: int = Field(587, ge=1, le=65535)
    security: str = Field("starttls", pattern="^(starttls|ssl|none)$")
    username: str | None = Field(None, max_length=255)
    password: str | None = Field(None, max_length=500)  # None keeps the saved one; "" clears it
    from_address: str | None = Field(None, max_length=320)
    from_name: str | None = Field(None, max_length=200)
    base_url: str | None = Field(None, max_length=500)
    digest_hour: int = Field(7, ge=0, le=23)

    @model_validator(mode="after")
    def _check(self):
        for name in ("host", "username", "from_address", "from_name", "base_url"):
            value = getattr(self, name)
            setattr(self, name, value.strip() or None if isinstance(value, str) else value)
        if self.from_address and not _ADDRESS.match(self.from_address):
            raise ValueError("The from address is not an email address.")
        if self.base_url and not re.match(r"^https?://[^\s/]+", self.base_url):
            raise ValueError("The Assayr address must start with https:// (or http://).")
        if self.enabled and not (self.host and self.from_address and self.base_url):
            raise ValueError(
                "To turn email on, fill in the mail server, the from address and the Assayr address."
            )
        self.base_url = self.base_url.rstrip("/") if self.base_url else None
        return self


class LastRun(BaseModel):
    day: date
    status: str
    sent: int
    error: str | None


class MailSettingsOut(BaseModel):
    enabled: bool
    host: str | None
    port: int
    security: str
    username: str | None
    password_set: bool
    from_address: str | None
    from_name: str | None
    base_url: str | None
    digest_hour: int
    key_configured: bool
    last_run: LastRun | None


class DigestIn(BaseModel):
    opt_out: bool


class DigestOut(BaseModel):
    digest_opt_out: bool


def load(db: Session) -> MailSettings:
    """The single settings row, created empty the first time."""
    cfg = db.scalar(select(MailSettings))
    if cfg is None:
        cfg = MailSettings(enabled=False, port=587, security="starttls", digest_hour=7)
        db.add(cfg)
        db.flush()
    return cfg


def password_of(cfg: MailSettings, secret_key: str | None) -> str | None:
    if not cfg.password_encrypted or not secret_key:
        return None
    return decrypt(secret_key, cfg.password_encrypted)


def _out(db: Session, request: Request, cfg: MailSettings) -> MailSettingsOut:
    run = db.scalar(select(MailLog).where(MailLog.kind == "run").order_by(MailLog.created_at.desc()).limit(1))
    return MailSettingsOut(
        enabled=cfg.enabled,
        host=cfg.host,
        port=cfg.port,
        security=cfg.security,
        username=cfg.username,
        password_set=bool(cfg.password_encrypted),
        from_address=cfg.from_address,
        from_name=cfg.from_name,
        base_url=cfg.base_url,
        digest_hour=cfg.digest_hour,
        key_configured=bool(request.app.state.settings.secret_key),
        last_run=LastRun(day=run.day, status=run.status, sent=run.item_count, error=run.error)
        if run
        else None,
    )


@router.get("/settings/mail", response_model=MailSettingsOut)
def get_mail_settings(
    request: Request,
    _: object = Depends(require_global(Perm.SETTINGS_MANAGE)),
    db: Session = Depends(get_session),
) -> MailSettingsOut:
    cfg = load(db)
    db.commit()
    return _out(db, request, cfg)


@router.put("/settings/mail", response_model=MailSettingsOut)
def put_mail_settings(
    body: MailSettingsIn,
    request: Request,
    user: User = Depends(current_user),
    _: object = Depends(require_global(Perm.SETTINGS_MANAGE)),
    db: Session = Depends(get_session),
) -> MailSettingsOut:
    cfg = load(db)
    secret_key = request.app.state.settings.secret_key
    diff: dict[str, list] = {}
    for name in (
        "enabled",
        "host",
        "port",
        "security",
        "username",
        "from_address",
        "from_name",
        "base_url",
        "digest_hour",
    ):
        new, old = getattr(body, name), getattr(cfg, name)
        if new != old:
            diff[name] = [old, new]
            setattr(cfg, name, new)
    if body.password is not None:
        if body.password == "":
            if cfg.password_encrypted:
                diff["password"] = ["set", "cleared"]
            cfg.password_encrypted = None
        else:
            if not secret_key:
                raise HTTPException(status.HTTP_409_CONFLICT, NO_KEY)
            cfg.password_encrypted = encrypt(secret_key, body.password)
            diff["password"] = ["", "changed"]  # never the password itself
    cfg.updated_by_id = user.id
    cfg.updated_at = get_clock(request)()
    if diff:
        record(db, actor_for(request, user), "settings.mail", "mail_settings", str(cfg.id), diff=diff)
    db.commit()
    return _out(db, request, cfg)


@router.post("/settings/mail/test")
def send_test(
    request: Request,
    user: User = Depends(current_user),
    _: object = Depends(require_global(Perm.SETTINGS_MANAGE)),
    db: Session = Depends(get_session),
) -> dict[str, str]:
    """Sends a short email to the administrator's own address and reports the mail server's answer."""
    cfg = load(db)
    if not (cfg.host and cfg.from_address):
        raise HTTPException(status.HTTP_409_CONFLICT, "Save the mail server and the from address first.")
    mail = Outgoing(
        to=user.email,
        subject="Assayr: test email",
        text=(
            f"Hello {user.full_name},\n\nThis is a test email from Assayr. "
            "Email reminders will reach people through this mail server.\n"
        ),
    )
    try:
        with Connection(cfg, password_of(cfg, request.app.state.settings.secret_key)) as connection:
            connection.send(mail)
    except MailError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc
    record(
        db,
        actor_for(request, user),
        "settings.mail_test",
        "mail_settings",
        str(cfg.id),
        diff={"to": user.email},
    )
    db.commit()
    return {"sent_to": user.email}


@router.patch("/me/digest", response_model=DigestOut)
def set_digest(
    body: DigestIn,
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_session),
) -> DigestOut:
    """Each person chooses for themselves whether to receive the daily summary."""
    if user.digest_opt_out != body.opt_out:
        user.digest_opt_out = body.opt_out
        record(
            db,
            actor_for(request, user),
            "user.digest",
            "user",
            str(user.id),
            diff={"digest_opt_out": [not body.opt_out, body.opt_out]},
        )
        db.commit()
    return DigestOut(digest_opt_out=user.digest_opt_out)
