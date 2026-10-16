"""Google Drive links and the training file types Assayr accepts."""

import re
from urllib.parse import parse_qs, urlparse

_FILE_ID = re.compile(r"^[A-Za-z0-9_-]{6,100}$")
_PATH = re.compile(r"^/file/d/([^/]+)(?:/.*)?$")

MP4, WEBM, PDF = "video/mp4", "video/webm", "application/pdf"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
PPTX = "application/vnd.openxmlformats-officedocument.presentationml.presentation"


def drive_file_id(url: str) -> str:
    """The file id of a Google Drive share link; anything else is refused."""
    parsed = urlparse(url.strip())
    if parsed.scheme != "https" or parsed.netloc != "drive.google.com":
        raise ValueError("Use a Google Drive share link (https://drive.google.com/file/d/…).")
    match = _PATH.match(parsed.path)
    file_id = (
        match[1] if match else (parse_qs(parsed.query).get("id", [""])[0] if parsed.path == "/open" else "")
    )
    if not _FILE_ID.match(file_id):
        raise ValueError("This Google Drive link does not point to a single file.")
    return file_id


def preview_url(file_id: str) -> str:
    return f"https://drive.google.com/file/d/{file_id}/preview"


def training_mime(head: bytes, filename: str) -> str | None:
    """Videos (mp4, webm), PDF, Word and PowerPoint, decided from the first bytes."""
    name = filename.lower()
    if head.startswith(b"%PDF-"):
        return PDF
    if len(head) >= 12 and head[4:8] == b"ftyp":
        return MP4
    if head.startswith(b"\x1a\x45\xdf\xa3"):
        return WEBM
    if head.startswith(b"PK\x03\x04"):
        if name.endswith(".docx"):
            return DOCX
        if name.endswith(".pptx"):
            return PPTX
    return None
