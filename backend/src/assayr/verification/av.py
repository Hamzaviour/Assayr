"""ClamAV client (clamd INSTREAM protocol)."""

from dataclasses import dataclass


@dataclass(frozen=True)
class AvResult:
    status: str  # clean | infected | error
    signature: str | None = None
    message: str | None = None
