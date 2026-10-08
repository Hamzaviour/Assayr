"""Content-addressed evidence file storage on local disk: <root>/<aa>/<bb>/<sha256>."""

import hashlib
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

CHUNK_SIZE = 1024 * 1024
_HEX = frozenset("0123456789abcdef")
_UNSAFE_NAME_CHARS = re.compile(r'[\x00-\x1f\x7f<>:"|?*]')


class TooLargeError(Exception):
    pass


@dataclass(frozen=True)
class StoredBlob:
    sha256: str
    size: int


class BlobStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def path_for(self, sha256: str) -> Path:
        if len(sha256) != 64 or not set(sha256) <= _HEX:
            raise ValueError("Invalid content hash.")
        return self.root / sha256[:2] / sha256[2:4] / sha256

    def put(self, stream: BinaryIO, max_bytes: int) -> StoredBlob:
        """Stream to a temp file while hashing; move into place only if within the size limit."""
        self.root.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256()
        size = 0
        fd, tmp_name = tempfile.mkstemp(dir=self.root, prefix=".upload-")
        try:
            with os.fdopen(fd, "wb") as tmp:
                while chunk := stream.read(CHUNK_SIZE):
                    size += len(chunk)
                    if size > max_bytes:
                        raise TooLargeError(f"File exceeds {max_bytes} bytes.")
                    digest.update(chunk)
                    tmp.write(chunk)
            sha256 = digest.hexdigest()
            target = self.path_for(sha256)
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                os.remove(tmp_name)
            else:
                os.replace(tmp_name, target)
            return StoredBlob(sha256=sha256, size=size)
        except BaseException:
            if os.path.exists(tmp_name):
                os.remove(tmp_name)
            raise


def safe_filename(name: str) -> str:
    """Keep only the final path component, without control or reserved characters."""
    base = re.split(r"[\\/]", name)[-1]
    base = _UNSAFE_NAME_CHARS.sub("", base).strip().strip(".")
    if len(base) > 200:
        stem, dot, ext = base.rpartition(".")
        base = f"{stem[:190]}.{ext[-9:]}" if dot and stem else base[:200]
    return base or "upload"
