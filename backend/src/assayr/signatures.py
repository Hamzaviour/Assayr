"""Offline ClamAV signature updates: copy .cvd/.cld/.cdiff/.cud files into the database folder."""

import os
import shutil
from pathlib import Path

SUFFIXES = {".cvd", ".cld", ".cdiff", ".cud"}


class SignatureError(Exception):
    pass


def update_signatures(source: Path, db_dir: Path) -> list[str]:
    files = [source] if source.is_file() else sorted(p for p in source.iterdir() if p.is_file())
    files = [p for p in files if p.suffix.lower() in SUFFIXES]
    if not files:
        raise SignatureError(f"No ClamAV signature files (.cvd, .cld, .cdiff, .cud) found in {source}.")
    db_dir.mkdir(parents=True, exist_ok=True)
    for f in files:
        tmp = db_dir / f".{f.name}.tmp"
        shutil.copyfile(f, tmp)
        os.replace(tmp, db_dir / f.name)
    return [f.name for f in files]
