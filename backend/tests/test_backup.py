import datetime as dt
import hashlib
import tarfile

import pytest

from assayr.backup import BackupError, BackupSources, create_backup, verify_sums, write_sums

NOW = dt.datetime(2026, 10, 15, 9, 30, 5, tzinfo=dt.UTC)
TOP = "assayr-0.3.0-20261015T093005Z"


@pytest.fixture
def sources(tmp_path):
    blobs = tmp_path / "data dir" / "blobs"
    (blobs / "ab" / "cd").mkdir(parents=True)
    (blobs / "ab" / "cd" / ("abcd" + "0" * 60)).write_bytes(b"evidence")
    env = tmp_path / "data dir" / "assayr.env"
    env.write_text("ASSAYR_ORG_NAME=Acme\n", encoding="utf-8")
    certs = tmp_path / "data dir" / "certs"
    certs.mkdir()
    (certs / "tls.crt").write_text("CERT")
    (certs / "tls.key").write_text("KEY")
    return BackupSources(blobs_dir=blobs, env_file=env, certs_dir=certs, license_dir=None)


def fake_dump(path):
    path.write_bytes(b"PGDMP fake")


def unpack(archive, target):
    with tarfile.open(archive) as tar:
        tar.extractall(target, filter="data")
    return target / TOP


def test_archive_layout_matches_linux(tmp_path, sources):
    archive = create_backup(tmp_path / "backups", "0.3.0", sources, fake_dump, NOW)
    assert archive.name == f"{TOP}.tar.gz"
    with tarfile.open(archive) as tar:
        names = sorted(tar.getnames())
    parts = ["manifest.txt", "db.dump", "blobs.tar", "assayr.env", "certs", "certs/tls.crt", "certs/tls.key"]
    assert names == sorted([TOP, *(f"{TOP}/{p}" for p in parts), f"{TOP}/SHA256SUMS"])


def test_manifest_and_sums_format(tmp_path, sources):
    folder = unpack(create_backup(tmp_path / "b", "0.3.0", sources, fake_dump, NOW), tmp_path / "x")
    assert (folder / "manifest.txt").read_text() == "version=0.3.0\ncreated=20261015T093005Z\n"
    lines = (folder / "SHA256SUMS").read_text().splitlines()
    paths = [line.split("  ", 1)[1] for line in lines]
    assert paths == sorted(paths)
    assert f"{hashlib.sha256(b'PGDMP fake').hexdigest()}  ./db.dump" in lines
    assert all("  ./" in line for line in lines)
    assert verify_sums(folder) is None


def test_blobs_tar_paths_are_relative(tmp_path, sources):
    folder = unpack(create_backup(tmp_path / "b", "0.3.0", sources, fake_dump, NOW), tmp_path / "x")
    with tarfile.open(folder / "blobs.tar") as blobs:
        names = blobs.getnames()
    assert any(n.endswith("ab/cd/abcd" + "0" * 60) for n in names)
    assert not any(n.startswith("/") or "\\" in n for n in names)


def test_failed_dump_leaves_nothing(tmp_path, sources):
    def broken(path):
        raise BackupError("pg_dump failed")

    with pytest.raises(BackupError):
        create_backup(tmp_path / "b", "0.3.0", sources, broken, NOW)
    assert list((tmp_path / "b").iterdir()) == []


def test_same_second_gets_suffix(tmp_path, sources):
    first = create_backup(tmp_path / "b", "0.3.0", sources, fake_dump, NOW)
    second = create_backup(tmp_path / "b", "0.3.0", sources, fake_dump, NOW)
    assert first != second and second.name.endswith("-2.tar.gz")


def test_verify_detects_tampering(tmp_path):
    (tmp_path / "a.txt").write_text("one")
    write_sums(tmp_path)
    (tmp_path / "a.txt").write_text("two")
    assert verify_sums(tmp_path) == "a.txt does not match its checksum."
