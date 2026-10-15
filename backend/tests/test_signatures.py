import pytest

from assayr.signatures import SignatureError, update_signatures


def test_copies_signature_files_from_folder(tmp_path):
    src = tmp_path / "usb"
    src.mkdir()
    for name in ("main.cvd", "daily.cld", "bytecode.cvd", "readme.txt"):
        (src / name).write_bytes(b"x")
    db = tmp_path / "db"
    assert sorted(update_signatures(src, db)) == ["bytecode.cvd", "daily.cld", "main.cvd"]
    assert not (db / "readme.txt").exists()


def test_single_file(tmp_path):
    f = tmp_path / "daily.cvd"
    f.write_bytes(b"x")
    assert update_signatures(f, tmp_path / "db") == ["daily.cvd"]


def test_nothing_to_copy(tmp_path):
    with pytest.raises(SignatureError):
        update_signatures(tmp_path, tmp_path / "db")
