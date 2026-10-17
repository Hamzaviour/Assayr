"""A stand-in for smtplib.SMTP / SMTP_SSL that records what would have been sent."""

import email
import smtplib

SENT: list[dict] = []


class FakeSMTP:
    fail_login = False
    fail_for: set[str] = set()

    def __init__(self, host, port, timeout=None, context=None):
        self.host, self.port, self.timeout = host, port, timeout
        self.tls = False

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def ehlo(self):
        pass

    def starttls(self, context=None):
        self.tls = True

    def login(self, user, password):
        if FakeSMTP.fail_login:
            raise smtplib.SMTPAuthenticationError(535, b"5.7.8 Invented: bad credentials")
        self.user, self.password = user, password

    def quit(self):
        pass

    def send_message(self, message):
        to = message["To"]
        if any(addr in to for addr in FakeSMTP.fail_for):
            raise smtplib.SMTPRecipientsRefused({to: (550, b"Invented: no such mailbox")})
        SENT.append(
            {
                "host": self.host,
                "port": self.port,
                "tls": self.tls,
                "to": to,
                "subject": message["Subject"],
                "from": message["From"],
                "body": message.get_body(("plain",)).get_content(),
                "html": message.get_body(("html",)).get_content() if message.get_body(("html",)) else None,
                "raw": email.message_from_bytes(message.as_bytes()),
            }
        )


def install(monkeypatch):
    SENT.clear()
    FakeSMTP.fail_login = False
    FakeSMTP.fail_for = set()
    monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)
    monkeypatch.setattr(smtplib, "SMTP_SSL", FakeSMTP)
    return SENT
