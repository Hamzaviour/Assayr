import pytest

from assayr.identity.security import (
    WeakPasswordError,
    hash_password,
    needs_rehash,
    new_token,
    normalize_email,
    token_digest,
    verify_password,
)


def test_hash_and_verify_round_trip():
    hashed = hash_password("correct-horse-battery")
    assert hashed.startswith("$argon2id$")
    assert verify_password(hashed, "correct-horse-battery")
    assert not verify_password(hashed, "wrong-horse-battery")
    assert not needs_rehash(hashed)


def test_short_password_is_rejected_with_a_clear_message():
    with pytest.raises(WeakPasswordError, match="Use at least 12 characters"):
        hash_password("short")


def test_overlong_password_is_rejected():
    with pytest.raises(WeakPasswordError, match="256 characters or fewer"):
        hash_password("x" * 257)


def test_verify_returns_false_for_garbage_hash():
    assert verify_password("not-a-hash", "whatever-password") is False


def test_email_is_trimmed_and_lowercased():
    assert normalize_email("  Sana.Malik@ACME.com ") == "sana.malik@acme.com"


def test_tokens_are_unique_and_digests_stable():
    first, second = new_token(), new_token()
    assert first != second
    assert token_digest(first) == token_digest(first)
    assert len(token_digest(first)) == 64
