import uuid

from sqlalchemy import create_engine, inspect, text

from assayr.migrate import upgrade
from tests.test_migrations import clean, migration_url


def test_0013_keeps_people_and_opts_everyone_in(tmp_path):
    url = migration_url(tmp_path)
    engine = create_engine(url)
    clean(engine)
    upgrade(url, "0012")
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO user_account (id, email, full_name, is_active, failed_logins, must_change_password,"
                " created_at, updated_at) VALUES (:id, 'ana@acme.com', 'Ana', :yes, 0, :no,"
                " CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ),
            {"id": uuid.uuid4().hex, "yes": True, "no": False},
        )
    upgrade(url, "0013")
    with engine.begin() as conn:
        rows = conn.execute(text("SELECT email, digest_opt_out FROM user_account")).all()
    assert [(r[0], bool(r[1])) for r in rows] == [("ana@acme.com", False)]
    tables = set(inspect(engine).get_table_names())
    assert {"finding", "corrective_action", "corrective_action_file", "finding_verification"} <= tables
    assert {"mail_settings", "mail_log"} <= tables
    clean(engine)
    engine.dispose()
