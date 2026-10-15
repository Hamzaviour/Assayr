"""Backups in the same format as the Linux installer (deploy/installer/lib/backup.sh)."""

import hashlib
import os
import shutil
import tarfile
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

REQUIRED = ("manifest.txt", "db.dump", "blobs.tar")


class BackupError(Exception):
    pass


@dataclass(frozen=True)
class BackupSources:
    blobs_dir: Path
    env_file: Path
    certs_dir: Path
    license_dir: Path | None


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def write_sums(folder: Path) -> None:
    """Write folder/SHA256SUMS in `sha256sum` format: `<hash>  ./<path>`, sorted, every other file."""
    files = sorted(
        "./" + p.relative_to(folder).as_posix()
        for p in folder.rglob("*")
        if p.is_file() and not p.name.startswith("SHA256SUMS")
    )
    lines = "".join(f"{_sha256(folder / f[2:])}  {f}\n" for f in files)
    (folder / "SHA256SUMS.tmp").write_text(lines, encoding="utf-8", newline="\n")
    os.replace(folder / "SHA256SUMS.tmp", folder / "SHA256SUMS")


def verify_sums(folder: Path) -> str | None:
    """Return the first problem with folder/SHA256SUMS, or None when every listed file matches."""
    sums = folder / "SHA256SUMS"
    if not sums.is_file():
        return "SHA256SUMS is missing."
    for line in sums.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        digest, _, path = line.partition("  ")
        rel = path.lstrip("*").removeprefix("./")
        target = folder / rel
        if not target.is_file():
            return f"{rel} is missing."
        if _sha256(target) != digest.strip():
            return f"{rel} does not match its checksum."
    return None


def _tar_dir(source: Path, target: Path) -> None:
    with tarfile.open(target, "w", format=tarfile.PAX_FORMAT) as tar:
        for path in sorted(source.rglob("*")):
            tar.add(path, arcname="./" + path.relative_to(source).as_posix(), recursive=False)


def create_backup(
    dest: Path, version: str, sources: BackupSources, dump: Callable[[Path], None], now: datetime
) -> Path:
    """Write dest/assayr-<version>-<stamp>.tar.gz. The archive appears only once it is complete."""
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    name = f"assayr-{version}-{stamp}"
    dest.mkdir(parents=True, exist_ok=True)
    if (dest / f"{name}.tar.gz").exists():
        name += "-2"
    work = Path(tempfile.mkdtemp(prefix=".backup.", dir=dest))
    try:
        folder = work / name
        folder.mkdir()
        dump(folder / "db.dump")
        _tar_dir(sources.blobs_dir, folder / "blobs.tar")
        shutil.copy2(sources.env_file, folder / "assayr.env")
        shutil.copytree(sources.certs_dir, folder / "certs")
        if sources.license_dir and sources.license_dir.is_dir():
            shutil.copytree(sources.license_dir, folder / "license")
        (folder / "manifest.txt").write_text(
            f"version={version}\ncreated={stamp}\n", encoding="utf-8", newline="\n"
        )
        write_sums(folder)
        partial = work / f"{name}.tar.gz"
        with tarfile.open(partial, "w:gz", format=tarfile.PAX_FORMAT) as tar:
            tar.add(folder, arcname=name)
        final = dest / f"{name}.tar.gz"
        os.replace(partial, final)
        return final
    except BackupError:
        raise
    except Exception as exc:
        raise BackupError(f"The backup failed: {exc}") from exc
    finally:
        shutil.rmtree(work, ignore_errors=True)
