import io

import pytest

from assayr.storage import BlobStore, TooLargeError, safe_filename


def files_under(path):
    return [p for p in path.rglob("*") if p.is_file()]


def test_put_stores_by_content_hash(tmp_path):
    store = BlobStore(tmp_path)
    blob = store.put(io.BytesIO(b"hello evidence"), max_bytes=1000)
    assert blob.size == 14
    assert store.path_for(blob.sha256).read_bytes() == b"hello evidence"


def test_identical_content_is_stored_once(tmp_path):
    store = BlobStore(tmp_path)
    first = store.put(io.BytesIO(b"same"), max_bytes=100)
    second = store.put(io.BytesIO(b"same"), max_bytes=100)
    assert first == second
    assert len(files_under(tmp_path)) == 1


def test_oversized_upload_leaves_nothing_behind(tmp_path):
    store = BlobStore(tmp_path)
    with pytest.raises(TooLargeError):
        store.put(io.BytesIO(b"x" * 101), max_bytes=100)
    assert files_under(tmp_path) == []


@pytest.mark.parametrize("bad", ["../../etc/passwd", "ABC", "g" * 64, ""])
def test_only_hex_hashes_map_to_paths(tmp_path, bad):
    with pytest.raises(ValueError):
        BlobStore(tmp_path).path_for(bad)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("..\\..\\evil.pdf", "evil.pdf"),
        ("../../x.txt", "x.txt"),
        ("a\x00b\n.pdf", "ab.pdf"),
        ('re<po>rt:"q3"?.xlsx', "reportq3.xlsx"),
        ("", "upload"),
        ("....", "upload"),
    ],
)
def test_safe_filename_strips_paths_and_unsafe_characters(raw, expected):
    assert safe_filename(raw) == expected


def test_safe_filename_shortens_long_names_but_keeps_the_extension():
    name = safe_filename("a" * 400 + ".pdf")
    assert len(name) <= 200 and name.endswith(".pdf")
