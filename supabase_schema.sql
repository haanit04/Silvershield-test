-- Idempotent schema. Participant IDs include registered users and anonymous guests.
CREATE TABLE IF NOT EXISTS users (
                    id BIGSERIAL PRIMARY KEY,
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
                    difficulty_web_mobile INTEGER DEFAULT 1);

CREATE TABLE IF NOT EXISTS guest_sessions (
                    id BIGSERIAL PRIMARY KEY,
                    guest_id TEXT UNIQUE NOT NULL,
                    consent_granted BOOLEAN NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);

CREATE TABLE IF NOT EXISTS scenario_attempts (
                        id BIGSERIAL PRIMARY KEY,
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
                        message TEXT);

CREATE TABLE IF NOT EXISTS pre_survey (
                    id BIGSERIAL PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL,
                    age TEXT,
                    device TEXT,
                    confidence NUMERIC,
                    response_json TEXT,
                    completed_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP);

CREATE TABLE IF NOT EXISTS post_survey (
                    id BIGSERIAL PRIMARY KEY,
                    username TEXT NOT NULL,
                    confidence_rating NUMERIC,
                    perceived_usefulness NUMERIC,
                    behavior_change TEXT,
                    recommendation_likelihood INTEGER,
                    learning_rating NUMERIC,
                    response_json TEXT,
                    completed_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP);

CREATE TABLE IF NOT EXISTS system_usability_survey (
                    id BIGSERIAL PRIMARY KEY,
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
                    completed_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP);

CREATE TABLE IF NOT EXISTS performance_summary (
                    id BIGSERIAL PRIMARY KEY,
                    username TEXT NOT NULL,
                    scenario_type TEXT NOT NULL,
                    total_attempts INTEGER NOT NULL DEFAULT 0,
                    correct_attempts INTEGER NOT NULL DEFAULT 0,
                    success_rate REAL NOT NULL DEFAULT 0,
                    average_duration_seconds REAL NOT NULL DEFAULT 0,
                    total_indicators_identified INTEGER NOT NULL DEFAULT 0,
                    UNIQUE(username, scenario_type));

CREATE TABLE IF NOT EXISTS module_progress (
                    id BIGSERIAL PRIMARY KEY,
                    username TEXT NOT NULL,
                    module_name TEXT NOT NULL,
                    scenarios_completed INTEGER NOT NULL DEFAULT 0,
                    total_scenarios INTEGER NOT NULL DEFAULT 5,
                    last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(username, module_name));

CREATE TABLE IF NOT EXISTS critical_indicators (
                    id BIGSERIAL PRIMARY KEY,
                    username TEXT NOT NULL,
                    scenario_attempt_id INTEGER NOT NULL,
                    scenario_type TEXT NOT NULL,
                    indicator_name TEXT NOT NULL,
                    identified BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(scenario_attempt_id) REFERENCES scenario_attempts(id));

CREATE TABLE IF NOT EXISTS phone_roleplay_sessions (
                    id BIGSERIAL PRIMARY KEY,
                    username TEXT NOT NULL,
                    scenario_type TEXT NOT NULL,
                    difficulty_level INTEGER DEFAULT 1,
                    started_at TEXT NOT NULL,
                    ended_at TEXT,
                    total_time_seconds REAL,
                    final_outcome TEXT,
                    score INTEGER DEFAULT 0,
                    completed INTEGER DEFAULT 0);

CREATE TABLE IF NOT EXISTS phone_roleplay_events (
                    id BIGSERIAL PRIMARY KEY,
                    session_id INTEGER NOT NULL,
                    event_type TEXT NOT NULL,
                    event_value TEXT,
                    timestamp TEXT NOT NULL,
                    time_offset_seconds REAL,
                    FOREIGN KEY(session_id) REFERENCES phone_roleplay_sessions(id));

CREATE TABLE IF NOT EXISTS phone_roleplay_results (
                    id BIGSERIAL PRIMARY KEY,
                    session_id INTEGER NOT NULL,
                    attempt_count INTEGER DEFAULT 0,
                    critical_indicators_found INTEGER DEFAULT 0,
                    critical_indicators_total INTEGER DEFAULT 0,
                    used_hint INTEGER DEFAULT 0,
                    behavior_pattern TEXT,
                    feedback_shown TEXT,
                    FOREIGN KEY(session_id) REFERENCES phone_roleplay_sessions(id));

CREATE TABLE IF NOT EXISTS module_assessment_assignments (
                    id BIGSERIAL PRIMARY KEY,
                    username TEXT NOT NULL,
                    module_name TEXT NOT NULL,
                    question_id INTEGER NOT NULL,
                    phase TEXT NOT NULL CHECK(phase IN ('pre', 'post')),
                    difficulty_level INTEGER NOT NULL,
                    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(username, module_name, question_id));

CREATE TABLE IF NOT EXISTS module_assessment_enrollments (
                    id BIGSERIAL PRIMARY KEY,
                    username TEXT NOT NULL,
                    module_name TEXT NOT NULL,
                    variant TEXT NOT NULL CHECK(variant IN ('A', 'B')),
                    enrolled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(username, module_name));

CREATE TABLE IF NOT EXISTS module_assessment_results (
                    id BIGSERIAL PRIMARY KEY,
                    username TEXT NOT NULL,
                    module_name TEXT NOT NULL,
                    phase TEXT NOT NULL CHECK(phase IN ('pre', 'post')),
                    question_id INTEGER NOT NULL,
                    selected_option TEXT NOT NULL,
                    is_correct BOOLEAN NOT NULL,
                    submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(username, module_name, phase, question_id));

CREATE TABLE IF NOT EXISTS module_assessment_scores (
                    id BIGSERIAL PRIMARY KEY,
                    username TEXT NOT NULL,
                    module_name TEXT NOT NULL,
                    phase TEXT NOT NULL CHECK(phase IN ('pre', 'post')),
                    variant TEXT NOT NULL CHECK(variant IN ('A', 'B')),
                    correct_count INTEGER NOT NULL DEFAULT 0,
                    total_questions INTEGER NOT NULL DEFAULT 0,
                    score_pct REAL NOT NULL DEFAULT 0,
                    completed_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(username, module_name, phase));

CREATE TABLE IF NOT EXISTS user_consents (
                    id BIGSERIAL PRIMARY KEY,
                    username TEXT NOT NULL,
                    consent_type TEXT NOT NULL,
                    granted BOOLEAN NOT NULL,
                    consent_text TEXT,
                    consent_details TEXT,
                    recorded_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(username, consent_type));

CREATE TABLE IF NOT EXISTS survey_question_assignments (
                    id BIGSERIAL PRIMARY KEY,
                    username TEXT NOT NULL,
                    survey_phase TEXT NOT NULL CHECK(survey_phase IN ('pre', 'post')),
                    section_id TEXT NOT NULL,
                    subsection_id TEXT,
                    question_id TEXT NOT NULL,
                    display_order INTEGER NOT NULL DEFAULT 0,
                    assigned_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(username, survey_phase, section_id, subsection_id, question_id));

CREATE TABLE IF NOT EXISTS survey_responses (
                    id BIGSERIAL PRIMARY KEY,
                    username TEXT NOT NULL,
                    survey_phase TEXT NOT NULL CHECK(survey_phase IN ('pre', 'post')),
                    section_id TEXT NOT NULL,
                    subsection_id TEXT,
                    question_id TEXT NOT NULL,
                    response_value TEXT,
                    submitted_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(username, survey_phase, question_id));

CREATE INDEX IF NOT EXISTS idx_attempts_username_time
                    ON scenario_attempts(username, start_time DESC);
CREATE INDEX IF NOT EXISTS idx_indicators_attempt
                    ON critical_indicators(scenario_attempt_id);
CREATE INDEX IF NOT EXISTS idx_module_progress_user
                    ON module_progress(username, last_accessed DESC);
CREATE INDEX IF NOT EXISTS idx_module_assessment_assignments
                    ON module_assessment_assignments(username, module_name, phase);
CREATE INDEX IF NOT EXISTS idx_module_assessment_enrollments
                    ON module_assessment_enrollments(username, module_name);
CREATE INDEX IF NOT EXISTS idx_module_assessment_results
                    ON module_assessment_results(username, module_name, phase);

ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE guest_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE scenario_attempts ENABLE ROW LEVEL SECURITY;
ALTER TABLE pre_survey ENABLE ROW LEVEL SECURITY;
ALTER TABLE post_survey ENABLE ROW LEVEL SECURITY;
ALTER TABLE system_usability_survey ENABLE ROW LEVEL SECURITY;
ALTER TABLE performance_summary ENABLE ROW LEVEL SECURITY;
ALTER TABLE module_progress ENABLE ROW LEVEL SECURITY;
ALTER TABLE critical_indicators ENABLE ROW LEVEL SECURITY;
ALTER TABLE phone_roleplay_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE phone_roleplay_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE phone_roleplay_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE module_assessment_assignments ENABLE ROW LEVEL SECURITY;
ALTER TABLE module_assessment_enrollments ENABLE ROW LEVEL SECURITY;
ALTER TABLE module_assessment_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE module_assessment_scores ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_consents ENABLE ROW LEVEL SECURITY;
ALTER TABLE survey_question_assignments ENABLE ROW LEVEL SECURITY;
ALTER TABLE survey_responses ENABLE ROW LEVEL SECURITY;

-- Existing deployments may already have integer summary columns. Preserve fractional averages.
ALTER TABLE pre_survey ALTER COLUMN confidence TYPE NUMERIC USING confidence::numeric;
ALTER TABLE post_survey ALTER COLUMN confidence_rating TYPE NUMERIC USING confidence_rating::numeric;
ALTER TABLE post_survey ALTER COLUMN perceived_usefulness TYPE NUMERIC USING perceived_usefulness::numeric;
ALTER TABLE post_survey ALTER COLUMN learning_rating TYPE NUMERIC USING learning_rating::numeric;
