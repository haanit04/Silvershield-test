import secrets
import sqlite3
from werkzeug.security import generate_password_hash

DB_PATH = 'silvershieldDatabase.db'
TEST_USER_USERNAME = 'testuser'
TEST_USER_PASSWORD = 'SilverShieldTest!1'
TEST_USER_EMAIL = 'testuser@silvershield.local'
TEST_USER_PHONE = '5551234567'
TEST_USER_ADDRESS = 'Test Address'


def _column_names(cursor, table_name):
    cursor.execute(f"PRAGMA table_info({table_name})")
    return [row[1] for row in cursor.fetchall()]


def _table_exists(cursor, table_name):
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,)
    )
    return cursor.fetchone() is not None


def _migrate_scenario_attempts(cursor):
    if not _table_exists(cursor, 'scenario_attempts'):
        cursor.execute('''CREATE TABLE IF NOT EXISTS scenario_attempts (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        username TEXT NOT NULL,
                        scenario_type TEXT NOT NULL,
                        scenario_platform TEXT NOT NULL,
                        start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        end_time TIMESTAMP,
                        duration_seconds INTEGER,
                        user_choice TEXT NOT NULL,
                        correct_answer TEXT NOT NULL,
                        is_correct BOOLEAN NOT NULL,
                        difficulty_level INTEGER NOT NULL,
                        ai_feedback TEXT,
                        message TEXT,
                        FOREIGN KEY(username) REFERENCES users(username))
        ''')
        return

    scenario_attempt_cols = _column_names(cursor, 'scenario_attempts')
    needs_rebuild = (
        'attempt_number' in scenario_attempt_cols or
        'critical_indicators_identified' in scenario_attempt_cols
    )

    if needs_rebuild:
        cursor.execute('PRAGMA foreign_keys=OFF')
        cursor.execute('''CREATE TABLE IF NOT EXISTS scenario_attempts_new (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        username TEXT NOT NULL,
                        scenario_type TEXT NOT NULL,
                        scenario_platform TEXT NOT NULL,
                        start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        end_time TIMESTAMP,
                        duration_seconds INTEGER,
                        user_choice TEXT NOT NULL,
                        correct_answer TEXT NOT NULL,
                        is_correct BOOLEAN NOT NULL,
                        difficulty_level INTEGER NOT NULL,
                        ai_feedback TEXT,
                        message TEXT,
                        FOREIGN KEY(username) REFERENCES users(username))
        ''')

        message_select = 'message' if 'message' in scenario_attempt_cols else 'NULL AS message'

        cursor.execute(f'''INSERT INTO scenario_attempts_new (
                        id, username, scenario_type, scenario_platform,
                        start_time, end_time, duration_seconds,
                        user_choice, correct_answer, is_correct,
                        difficulty_level, ai_feedback, message)
                        SELECT id, username, scenario_type, scenario_platform,
                        start_time, end_time, duration_seconds,
                        user_choice, correct_answer, is_correct,
                        difficulty_level, ai_feedback, {message_select}
                        FROM scenario_attempts
        ''')

        cursor.execute('DROP TABLE scenario_attempts')
        cursor.execute('ALTER TABLE scenario_attempts_new RENAME TO scenario_attempts')
        cursor.execute('PRAGMA foreign_keys=ON')
        scenario_attempt_cols = _column_names(cursor, 'scenario_attempts')

    if 'message' not in scenario_attempt_cols:
        cursor.execute('ALTER TABLE scenario_attempts ADD COLUMN message TEXT')


def _ensure_test_user(cursor):
    password_hash = generate_password_hash(TEST_USER_PASSWORD)
    cursor.execute('SELECT 1 FROM users WHERE username = ?', (TEST_USER_USERNAME,))
    exists = cursor.fetchone() is not None

    if exists:
        cursor.execute(
            '''UPDATE users
               SET email = ?, phone = ?, address = ?, password_hash = ?
               WHERE username = ?''',
            (TEST_USER_EMAIL, TEST_USER_PHONE, TEST_USER_ADDRESS, password_hash, TEST_USER_USERNAME)
        )
        return

    cursor.execute(
        '''INSERT INTO users (username, email, phone, address, password_hash)
           VALUES (?, ?, ?, ?, ?)''',
        (TEST_USER_USERNAME, TEST_USER_EMAIL, TEST_USER_PHONE, TEST_USER_ADDRESS, password_hash)
    )


def init_database():
    connect = sqlite3.connect(DB_PATH)
    cursor = connect.cursor()

    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    phone TEXT UNIQUE NOT NULL,
                    address TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    difficulty_email_desktop INTEGER DEFAULT 1,
                    difficulty_internet_desktop INTEGER DEFAULT 1,
                    difficulty_email_mobile INTEGER DEFAULT 1,
                    difficulty_sms_mobile INTEGER DEFAULT 1,
                    difficulty_call_mobile INTEGER DEFAULT 1,
                    difficulty_web_mobile INTEGER DEFAULT 1)
    ''')

    _ensure_test_user(cursor)

    _migrate_scenario_attempts(cursor)

    cursor.execute('''CREATE TABLE IF NOT EXISTS pre_survey (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    age TEXT,
                    device TEXT,
                    confidence INTEGER,
                    response_json TEXT,
                    completed_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(username) REFERENCES users(username))
    ''')

    pre_survey_cols = _column_names(cursor, 'pre_survey')
    if 'response_json' not in pre_survey_cols:
        cursor.execute('ALTER TABLE pre_survey ADD COLUMN response_json TEXT')

    cursor.execute('''CREATE TABLE IF NOT EXISTS post_survey (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL,
                    confidence_rating INTEGER,
                    perceived_usefulness INTEGER,
                    behavior_change TEXT,
                    recommendation_likelihood INTEGER,
                    learning_rating INTEGER,
                    response_json TEXT,
                    completed_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(username) REFERENCES users(username))
    ''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS system_usability_survey (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    sus_q1 INTEGER,
                    sus_q2 INTEGER,
                    sus_q3 INTEGER,
                    sus_q4 INTEGER,
                    sus_q5 INTEGER,
                    sus_q6 INTEGER,
                    sus_q7 INTEGER,
                    sus_q8 INTEGER,
                    sus_q9 INTEGER,
                    sus_q10 INTEGER,
                    sus_score REAL,
                    completed_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(username) REFERENCES users(username))
    ''')

    usability_cols = _column_names(cursor, 'system_usability_survey')
    usability_column_defs = {
        'sus_q1': 'INTEGER',
        'sus_q2': 'INTEGER',
        'sus_q3': 'INTEGER',
        'sus_q4': 'INTEGER',
        'sus_q5': 'INTEGER',
        'sus_q6': 'INTEGER',
        'sus_q7': 'INTEGER',
        'sus_q8': 'INTEGER',
        'sus_q9': 'INTEGER',
        'sus_q10': 'INTEGER',
        'sus_score': 'REAL',
    }

    for col_name, col_type in usability_column_defs.items():
        if col_name not in usability_cols:
            cursor.execute(f'ALTER TABLE system_usability_survey ADD COLUMN {col_name} {col_type}')

    cursor.execute('''CREATE TABLE IF NOT EXISTS performance_summary (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL,
                    scenario_type TEXT NOT NULL,
                    total_attempts INTEGER NOT NULL DEFAULT 0,
                    correct_attempts INTEGER NOT NULL DEFAULT 0,
                    success_rate REAL NOT NULL DEFAULT 0,
                    average_duration_seconds REAL NOT NULL DEFAULT 0,
                    total_indicators_identified INTEGER NOT NULL DEFAULT 0,
                    UNIQUE(username, scenario_type),
                    FOREIGN KEY(username) REFERENCES users(username))
    ''')

    performance_cols = _column_names(cursor, 'performance_summary')
    if 'total_indicators_identified' not in performance_cols:
        cursor.execute(
            'ALTER TABLE performance_summary ADD COLUMN total_indicators_identified INTEGER NOT NULL DEFAULT 0'
        )

    cursor.execute('''CREATE TABLE IF NOT EXISTS module_progress (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL,
                    module_name TEXT NOT NULL,
                    scenarios_completed INTEGER NOT NULL DEFAULT 0,
                    total_scenarios INTEGER NOT NULL DEFAULT 5,
                    last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(username, module_name),
                    FOREIGN KEY(username) REFERENCES users(username))
    ''')
    cursor.execute('''UPDATE module_progress
                    SET total_scenarios = 5
                    WHERE total_scenarios IS NULL OR total_scenarios <> 5
    ''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS critical_indicators (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL,
                    scenario_attempt_id INTEGER NOT NULL,
                    scenario_type TEXT NOT NULL,
                    indicator_name TEXT NOT NULL,
                    identified BOOLEAN NOT NULL DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(username) REFERENCES users(username),
                    FOREIGN KEY(scenario_attempt_id) REFERENCES scenario_attempts(id))
    ''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS phone_roleplay_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL,
                    scenario_type TEXT NOT NULL,
                    difficulty_level INTEGER DEFAULT 1,
                    started_at TEXT NOT NULL,
                    ended_at TEXT,
                    total_time_seconds REAL,
                    final_outcome TEXT,
                    score INTEGER DEFAULT 0,
                    completed INTEGER DEFAULT 0)
    ''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS phone_roleplay_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER NOT NULL,
                    event_type TEXT NOT NULL,
                    event_value TEXT,
                    timestamp TEXT NOT NULL,
                    time_offset_seconds REAL,
                    FOREIGN KEY(session_id) REFERENCES phone_roleplay_sessions(id))
    ''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS phone_roleplay_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER NOT NULL,
                    attempt_count INTEGER DEFAULT 0,
                    critical_indicators_found INTEGER DEFAULT 0,
                    critical_indicators_total INTEGER DEFAULT 0,
                    used_hint INTEGER DEFAULT 0,
                    behavior_pattern TEXT,
                    feedback_shown TEXT,
                    FOREIGN KEY(session_id) REFERENCES phone_roleplay_sessions(id))
    ''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS module_assessment_assignments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL,
                    module_name TEXT NOT NULL,
                    question_id INTEGER NOT NULL,
                    phase TEXT NOT NULL CHECK(phase IN ('pre', 'post')),
                    difficulty_level INTEGER NOT NULL,
                    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(username, module_name, question_id),
                    FOREIGN KEY(username) REFERENCES users(username))
    ''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS module_assessment_enrollments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL,
                    module_name TEXT NOT NULL,
                    variant TEXT NOT NULL CHECK(variant IN ('A', 'B')),
                    enrolled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(username, module_name),
                    FOREIGN KEY(username) REFERENCES users(username))
    ''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS module_assessment_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL,
                    module_name TEXT NOT NULL,
                    phase TEXT NOT NULL CHECK(phase IN ('pre', 'post')),
                    question_id INTEGER NOT NULL,
                    selected_option TEXT NOT NULL,
                    is_correct BOOLEAN NOT NULL,
                    submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(username, module_name, phase, question_id),
                    FOREIGN KEY(username) REFERENCES users(username))
    ''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS module_assessment_scores (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL,
                    module_name TEXT NOT NULL,
                    phase TEXT NOT NULL CHECK(phase IN ('pre', 'post')),
                    variant TEXT NOT NULL CHECK(variant IN ('A', 'B')),
                    correct_count INTEGER NOT NULL DEFAULT 0,
                    total_questions INTEGER NOT NULL DEFAULT 0,
                    score_pct REAL NOT NULL DEFAULT 0,
                    completed_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(username, module_name, phase),
                    FOREIGN KEY(username) REFERENCES users(username))
    ''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS user_consents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL,
                    consent_type TEXT NOT NULL,
                    granted BOOLEAN NOT NULL,
                    consent_text TEXT,
                    consent_details TEXT,
                    recorded_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(username, consent_type),
                    FOREIGN KEY(username) REFERENCES users(username))
    ''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS survey_question_assignments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL,
                    survey_phase TEXT NOT NULL CHECK(survey_phase IN ('pre', 'post')),
                    section_id TEXT NOT NULL,
                    subsection_id TEXT,
                    question_id TEXT NOT NULL,
                    display_order INTEGER NOT NULL DEFAULT 0,
                    assigned_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(username, survey_phase, section_id, subsection_id, question_id),
                    FOREIGN KEY(username) REFERENCES users(username))
    ''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS survey_responses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL,
                    survey_phase TEXT NOT NULL CHECK(survey_phase IN ('pre', 'post')),
                    section_id TEXT NOT NULL,
                    subsection_id TEXT,
                    question_id TEXT NOT NULL,
                    response_value TEXT,
                    submitted_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(username, survey_phase, question_id),
                    FOREIGN KEY(username) REFERENCES users(username))
    ''')

    score_cols = _column_names(cursor, 'module_assessment_scores')
    score_column_defs = {
        'variant': "TEXT NOT NULL DEFAULT 'A'",
        'correct_count': 'INTEGER NOT NULL DEFAULT 0',
        'total_questions': 'INTEGER NOT NULL DEFAULT 0',
        'score_pct': 'REAL NOT NULL DEFAULT 0',
        'completed_timestamp': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP',
    }

    for col_name, col_type in score_column_defs.items():
        if col_name not in score_cols:
            cursor.execute(f'ALTER TABLE module_assessment_scores ADD COLUMN {col_name} {col_type}')

    cursor.execute('''
        INSERT INTO module_assessment_scores (
            username, module_name, phase, variant, correct_count, total_questions, score_pct, completed_timestamp
        )
        SELECT
            r.username,
            r.module_name,
            r.phase,
            COALESCE(e.variant, 'A') AS variant,
            SUM(CASE WHEN r.is_correct = 1 THEN 1 ELSE 0 END) AS correct_count,
            COUNT(*) AS total_questions,
            ROUND((100.0 * SUM(CASE WHEN r.is_correct = 1 THEN 1 ELSE 0 END)) / COUNT(*), 2) AS score_pct,
            MAX(r.submitted_at) AS completed_timestamp
        FROM module_assessment_results r
        LEFT JOIN module_assessment_enrollments e
            ON e.username = r.username AND e.module_name = r.module_name
        GROUP BY r.username, r.module_name, r.phase
        ON CONFLICT(username, module_name, phase) DO UPDATE SET
            variant = excluded.variant,
            correct_count = excluded.correct_count,
            total_questions = excluded.total_questions,
            score_pct = excluded.score_pct,
            completed_timestamp = excluded.completed_timestamp
    ''')
    
    cursor.execute('''CREATE INDEX IF NOT EXISTS idx_attempts_username_time
                    ON scenario_attempts(username, start_time DESC)
    ''')
    cursor.execute('''CREATE INDEX IF NOT EXISTS idx_indicators_attempt
                    ON critical_indicators(scenario_attempt_id)
    ''')
    cursor.execute('''CREATE INDEX IF NOT EXISTS idx_module_progress_user
                    ON module_progress(username, last_accessed DESC)
    ''')
    cursor.execute('''CREATE INDEX IF NOT EXISTS idx_module_assessment_assignments
                    ON module_assessment_assignments(username, module_name, phase)
    ''')
    cursor.execute('''CREATE INDEX IF NOT EXISTS idx_module_assessment_enrollments
                    ON module_assessment_enrollments(username, module_name)
    ''')
    cursor.execute('''CREATE INDEX IF NOT EXISTS idx_module_assessment_results
                    ON module_assessment_results(username, module_name, phase)
    ''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS guest_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guest_id TEXT UNIQUE NOT NULL,
                    consent_granted INTEGER NOT NULL CHECK(consent_granted IN (0, 1)),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)
    ''')

    connect.commit()
    connect.close()


def create_guest_session(consent_granted):
    """Create an anonymous, consented participant record without contact details."""
    if not consent_granted:
        raise ValueError("Guest consent is required")

    with sqlite3.connect(DB_PATH) as connect:
        cursor = connect.cursor()
        for _ in range(5):
            guest_id = "guest_" + secrets.token_hex(8)
            try:
                cursor.execute(
                    "INSERT INTO guest_sessions (guest_id, consent_granted) VALUES (?, ?)",
                    (guest_id, 1),
                )
                return guest_id
            except sqlite3.IntegrityError:
                continue

    raise RuntimeError("Could not create a unique guest id")


def is_guest_username(username):
    if not username:
        return False

    with sqlite3.connect(DB_PATH) as connect:
        row = connect.execute(
            "SELECT 1 FROM guest_sessions WHERE guest_id = ?", (username,)
        ).fetchone()
    return row is not None


if __name__ == '__main__':
    init_database()
