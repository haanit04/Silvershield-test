import sqlite3
from werkzeug.security import check_password_hash

import database


def test_init_database_creates_expected_tables(monkeypatch, tmp_path):
    db_path = str(tmp_path / "database_test.db")
    monkeypatch.setattr(database, "DB_PATH", db_path)

    database.init_database()

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        tables = {row[0] for row in cursor.fetchall()}

    expected_tables = {
        "users",
        "pre_survey",
        "post_survey",
        "scenario_attempts",
        "performance_summary",
        "module_progress",
        "critical_indicators",
        "phone_roleplay_sessions",
        "phone_roleplay_events",
        "phone_roleplay_results",
        "module_assessment_enrollments",
        "module_assessment_assignments",
        "module_assessment_results",
        "module_assessment_scores",
        "user_consents",
        "survey_question_assignments",
        "survey_responses",
        "guest_sessions",
    }

    assert expected_tables.issubset(tables)


def test_init_database_seeds_default_test_user(monkeypatch, tmp_path):
    db_path = str(tmp_path / "database_test.db")
    monkeypatch.setattr(database, "DB_PATH", db_path)

    database.init_database()

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT username, email, phone, address, password_hash FROM users WHERE username = ?",
            (database.TEST_USER_USERNAME,),
        )
        row = cursor.fetchone()

    assert row is not None
    assert row[0] == database.TEST_USER_USERNAME
    assert row[1] == database.TEST_USER_EMAIL
    assert row[2] == database.TEST_USER_PHONE
    assert row[3] == database.TEST_USER_ADDRESS
    assert check_password_hash(row[4], database.TEST_USER_PASSWORD)
