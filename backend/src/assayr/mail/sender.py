"""Sending email through the organisation's own mail server."""

import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formataddr

from assayr.mail.models import MailSettings

TIMEOUT_SECONDS = 30


class MailError(Exception):
    """The mail server refused or could not be reached; the message is safe to show an administrator."""


@dataclass(frozen=True)
class Outgoing:
    to: str
    subject: str
    text: str
    html: str | None = None


def build(cfg: MailSettings, mail: Outgoing) -> EmailMessage:
    message = EmailMessage()
    message["From"] = formataddr((cfg.from_name or "", cfg.from_address or ""))
    message["To"] = mail.to
    message["Subject"] = mail.subject
    message.set_content(mail.text)
    if mail.html:
        message.add_alternative(mail.html, subtype="html")
    return message


def _describe(exc: Exception) -> str:
    if isinstance(exc, smtplib.SMTPResponseException):
        detail = (
            exc.smtp_error.decode("utf-8", "replace") if isinstance(exc.smtp_error, bytes) else exc.smtp_error
        )
        return f"The mail server answered {exc.smtp_code}: {detail}"
    if isinstance(exc, smtplib.SMTPRecipientsRefused):
        return f"The mail server refused the recipient: {exc.recipients}"
    return f"Could not send through the mail server: {exc}"


class Connection:
    """One SMTP session for many messages (the digest), opened with the saved settings."""

    def __init__(self, cfg: MailSettings, password: str | None) -> None:
        self.cfg, self.password, self.smtp = cfg, password, None

    def __enter__(self) -> "Connection":
        cfg = self.cfg
        context = ssl.create_default_context()
        try:
            if cfg.security == "ssl":
                self.smtp = smtplib.SMTP_SSL(cfg.host, cfg.port, timeout=TIMEOUT_SECONDS, context=context)
            else:
                self.smtp = smtplib.SMTP(cfg.host, cfg.port, timeout=TIMEOUT_SECONDS)
                if cfg.security == "starttls":
                    self.smtp.ehlo()
                    self.smtp.starttls(context=context)
            self.smtp.ehlo()
            if cfg.username:
                self.smtp.login(cfg.username, self.password or "")
        except (smtplib.SMTPException, OSError) as exc:
            self.close()
            raise MailError(_describe(exc)) from exc
        return self

    def send(self, mail: Outgoing) -> None:
        try:
            self.smtp.send_message(build(self.cfg, mail))
        except (smtplib.SMTPException, OSError) as exc:
            raise MailError(_describe(exc)) from exc

    def close(self) -> None:
        if self.smtp is not None:
            try:
                self.smtp.quit()
            except (smtplib.SMTPException, OSError, AttributeError):
                pass
            self.smtp = None

    def __exit__(self, *exc) -> None:
        self.close()
