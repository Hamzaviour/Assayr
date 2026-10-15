import io
import tarfile

import pytest

from assayr.backup import BackupError, read_backup, restore_data, version_tuple, write_sums


def linux_style_archive(tmp_path, version="0.2.0", drop=None, tamper=False):
    """Build an archive the way deploy/installer/lib/backup.sh does (./ paths, no license dir)."""
    name = f"assayr-{version}-20261011T190000Z"
    folder = tmp_path / "src" / name
    (folder / "certs").mkdir(parents=True)
    (folder / "certs" / "tls.crt").write_text("CERT")
    (folder / "assayr.env").write_text("POSTGRES_PASSWORD=x\n")
    (folder / "db.dump").write_bytes(b"PGDMP")
    with tarfile.open(folder / "blobs.tar", "w") as blobs:
        data = b"evidence"
        info = tarfile.TarInfo("./ab/cd/abcd" + "0" * 60)
        info.size = len(data)
        blobs.addfile(info, io.BytesIO(data))
    (folder / "manifest.txt").write_text(f"version={version}\ncreated=20261011T190000Z\n")
    write_sums(folder)
    if drop:
        (folder / drop).unlink()
    if tamper:
        (folder / "db.dump").write_bytes(b"changed")
    archive = tmp_path / f"{name}.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        tar.add(folder, arcname=name)
    return archive


class FakeDb:
    def __init__(self):
        self.calls = []

    def recreate_database(self):
        self.calls.append("recreate")

    def restore(self, path):
        self.calls.append(("restore", path.read_bytes()))


def test_reads_linux_archive(tmp_path):
    src = read_backup(linux_style_archive(tmp_path), tmp_path / "work")
    assert (src.version, src.created) == ("0.2.0", "20261011T190000Z")


@pytest.mark.parametrize("drop", ["db.dump", "blobs.tar"])
def test_missing_part(tmp_path, drop):
    with pytest.raises(BackupError, match="is missing"):
        read_backup(linux_style_archive(tmp_path, drop=drop), tmp_path / "w")


def test_tampered_part(tmp_path):
    with pytest.raises(BackupError, match="does not match"):
        read_backup(linux_style_archive(tmp_path, tamper=True), tmp_path / "w")


def test_not_an_archive(tmp_path):
    bad = tmp_path / "x.tar.gz"
    bad.write_bytes(b"nope")
    with pytest.raises(BackupError, match="can't be unpacked"):
        read_backup(bad, tmp_path / "w")


def test_version_tuple():
    assert version_tuple("0.10.0") > version_tuple("0.9.9")


def test_restore_replaces_db_and_blobs(tmp_path):
    src = read_backup(linux_style_archive(tmp_path), tmp_path / "work")
    blobs = tmp_path / "blobs"
    (blobs / "old").mkdir(parents=True)
    (blobs / "old" / "file").write_text("old")
    db = FakeDb()
    restore_data(src, blobs, db)
    assert db.calls == ["recreate", ("restore", b"PGDMP")]
    assert not (blobs / "old").exists()
    assert (blobs / "ab" / "cd" / ("abcd" + "0" * 60)).read_bytes() == b"evidence"
