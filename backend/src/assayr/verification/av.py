"""ClamAV client (clamd INSTREAM protocol)."""

import socket
import struct
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AvResult:
    status: str  # clean | infected | error
    signature: str | None = None
    message: str | None = None


_CHUNK = 64 * 1024


def scan_file(path: Path, host: str, port: int, timeout: float = 30.0) -> AvResult:
    """Stream the file to clamd with INSTREAM and interpret its one-line reply."""
    try:
        with socket.create_connection((host, port), timeout=timeout) as conn:
            conn.sendall(b"zINSTREAM\0")
            with path.open("rb") as handle:
                while chunk := handle.read(_CHUNK):
                    conn.sendall(struct.pack("!I", len(chunk)) + chunk)
            conn.sendall(struct.pack("!I", 0))
            reply = b""
            while not reply.endswith(b"\0"):
                part = conn.recv(4096)
                if not part:
                    break
                reply += part
    except OSError as exc:
        return AvResult("error", message=str(exc))
    text = reply.rstrip(b"\0").decode(errors="replace").strip()
    if text.endswith(" OK"):
        return AvResult("clean")
    if text.endswith(" FOUND"):
        return AvResult("infected", signature=text.split(":", 1)[-1].rsplit(" FOUND", 1)[0].strip())
    return AvResult("error", message=text or "Empty reply from the malware scanner.")
