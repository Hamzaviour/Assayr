from sqlalchemy import delete, update

from assayr.audit.models import AuditLog
from assayr.audit.service import GENESIS, SYSTEM, record, verify_chain


def test_entries_chain_to_each_other(db):
    first = record(db, SYSTEM, "test.one", "thing", "1")
    second = record(db, SYSTEM, "test.two", "thing", "2", diff={"x": [1, 2]})
    db.commit()
    assert first.prev_hash == GENESIS
    assert second.prev_hash == first.hash
    assert verify_chain(db).ok


def test_empty_log_is_valid(db):
    result = verify_chain(db)
    assert result.ok and result.checked == 0 and result.first_bad_seq is None


def test_verify_detects_an_edited_row(db):
    for n in range(3):
        record(db, SYSTEM, "test.step", "thing", str(n))
    db.commit()
    db.execute(update(AuditLog).where(AuditLog.seq == 2).values(action="test.tampered"))
    db.commit()
    result = verify_chain(db)
    assert not result.ok
    assert result.first_bad_seq == 2


def test_verify_detects_a_deleted_row(db):
    for n in range(3):
        record(db, SYSTEM, "test.step", "thing", str(n))
    db.commit()
    db.execute(delete(AuditLog).where(AuditLog.seq == 2))
    db.commit()
    assert verify_chain(db).first_bad_seq == 3


def test_unicode_and_nested_diffs_survive_a_database_round_trip(db):
    record(
        db, SYSTEM, "test.unicode", "thing", diff={"title": ["Sécurité", "Security"], "n": {"a": [1, None]}}
    )
    db.commit()
    db.expunge_all()
    assert verify_chain(db).ok
