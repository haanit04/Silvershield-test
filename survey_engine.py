import hashlib
import json
import os
import random
import sqlite3
from db_connection import connect as db_connect, using_postgres
from functools import lru_cache
from flask_babel import gettext as _, get_locale


SURVEY_CONFIG_PATH = os.getenv(
    "SURVEY_CONFIG_PATH",
    os.path.join(os.path.dirname(__file__), "survey_config.json"),
)
SURVEY_TRANSLATIONS_PATH = os.getenv(
    "SURVEY_TRANSLATIONS_PATH",
    os.path.join(os.path.dirname(__file__), "survey_translations.json"),
)

SURVEY_PHASE_KEYS = {
    "pre": "preTrainingSurvey",
    "post": "postTrainingSurvey",
}

SELF_EFFICACY_IDS = ["SE1", "SE2", "SE3", "SE4", "SE5", "SE6"]
USEFULNESS_IDS = ["PU1", "PU2", "PU3"]
ENGAGEMENT_IDS = ["HM1", "HM2"]
SUS_IDS = [f"SUS{i}" for i in range(1, 11)]


@lru_cache(maxsize=1)
def load_survey_translations():
    if not os.path.exists(SURVEY_TRANSLATIONS_PATH):
        return {}
    try:
        with open(SURVEY_TRANSLATIONS_PATH, "r", encoding="utf-8") as translations_file:
            data = json.load(translations_file)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _active_survey_language():
    locale = str(get_locale() or "en").lower()
    if locale.startswith("es"):
        return "es"
    if locale.startswith("zh"):
        return "zh"
    return "en"


def _translate_survey_text(text):
    if text is None or not isinstance(text, str):
        return text
    language = _active_survey_language()
    if language != "en":
        translations = load_survey_translations().get(language, {})
        translated = translations.get(text)
        if translated:
            return translated
        translated = translations.get(text.strip())
        if translated:
            return translated
    return _(text)


@lru_cache(maxsize=1)
def load_survey_config():
    with open(SURVEY_CONFIG_PATH, "r", encoding="utf-8") as config_file:
        return json.load(config_file)


def get_consent_config():
    return load_survey_config().get("consent", {})


def get_survey_config(phase):
    config_key = SURVEY_PHASE_KEYS[phase]
    return load_survey_config()[config_key]


def get_survey_completion_table(phase):
    return "pre_survey" if phase == "pre" else "post_survey"


def _seeded_rng(*parts):
    digest = hashlib.sha256(":".join(str(part) for part in parts).encode("utf-8")).hexdigest()
    return random.Random(int(digest[:16], 16))


def _get_existing_assignments(cursor, username, phase):
    cursor.execute(
        """
        SELECT section_id, subsection_id, question_id, display_order
        FROM survey_question_assignments
        WHERE username = ? AND survey_phase = ?
        ORDER BY display_order, question_id
        """,
        (username, phase),
    )
    return cursor.fetchall()


def _ensure_section3_assignments(cursor, username, phase, section):
    existing = _get_existing_assignments(cursor, username, phase)
    if existing:
        return

    pre_assignments_by_subsection = {}
    if phase == "post":
        cursor.execute(
            """
            SELECT subsection_id, question_id
            FROM survey_question_assignments
            WHERE username = ? AND survey_phase = 'pre' AND section_id = ?
            """,
            (username, section["sectionId"]),
        )
        for subsection_id, question_id in cursor.fetchall():
            pre_assignments_by_subsection.setdefault(subsection_id, set()).add(question_id)

    display_order = 0
    for subsection in section.get("subsections", []):
        questions = list(subsection.get("questions", []))
        desired_count = int(subsection.get("questionSelectionCount", len(questions) or 0))
        if desired_count <= 0 or not questions:
            continue

        rng = _seeded_rng(username, phase, subsection["subsectionId"])
        available_questions = questions
        if phase == "post":
            seen_ids = pre_assignments_by_subsection.get(subsection["subsectionId"], set())
            remaining_questions = [
                question for question in questions if question["questionId"] not in seen_ids
            ]
            available_questions = remaining_questions or questions

        selected_count = min(desired_count, len(available_questions))
        selected_questions = rng.sample(available_questions, selected_count)
        for question in selected_questions:
            display_order += 1
            cursor.execute(
                """
                INSERT INTO survey_question_assignments (
                    username, survey_phase, section_id, subsection_id, question_id, display_order
                ) VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT DO NOTHING
                """,
                (
                    username,
                    phase,
                    section["sectionId"],
                    subsection["subsectionId"],
                    question["questionId"],
                    display_order,
                ),
            )


def ensure_phase_assignments(db_path, username, phase):
    survey_config = get_survey_config(phase)
    knowledge_sections = [
        section for section in survey_config.get("sections", []) if section.get("sectionId") == "S3"
    ]
    if not knowledge_sections:
        return

    with db_connect(db_path) as conn:
        cursor = conn.cursor()
        for section in knowledge_sections:
            _ensure_section3_assignments(cursor, username, phase, section)
        conn.commit()


def _decorate_question(question, inherited_scale=None, subsection=None):
    decorated = dict(question)
    question_type = decorated.get("type") or ("singleChoice" if decorated.get("options") else "singleChoice")
    decorated["type"] = question_type
    scale = decorated.get("scale") or inherited_scale
    if isinstance(scale, dict):
        scale = {
            **scale,
            "labels": [_translate_survey_text(label) for label in scale.get("labels", [])],
        }
    decorated["scale"] = scale
    decorated["text"] = _translate_survey_text(decorated.get("text", ""))
    if isinstance(decorated.get("options"), list):
        decorated["options"] = [_translate_survey_text(option) for option in decorated["options"]]
    decorated["required"] = decorated.get("required", True)
    decorated["fieldName"] = decorated["questionId"]
    decorated["subsectionId"] = subsection.get("subsectionId") if subsection else None
    decorated["subsectionTopic"] = _translate_survey_text(subsection.get("topic")) if subsection else None
    return decorated


def _assignment_id_set(cursor, username, phase, section_id, subsection_id):
    cursor.execute(
        """
        SELECT question_id
        FROM survey_question_assignments
        WHERE username = ? AND survey_phase = ? AND section_id = ? AND subsection_id = ?
        ORDER BY display_order, question_id
        """,
        (username, phase, section_id, subsection_id),
    )
    return [row[0] for row in cursor.fetchall()]


def build_survey_view_model(db_path, username, phase):
    ensure_phase_assignments(db_path, username, phase)
    survey = get_survey_config(phase)
    sections = []

    with db_connect(db_path) as conn:
        cursor = conn.cursor()
        for section in survey.get("sections", []):
            section_view = {
                "sectionId": section["sectionId"],
                "title": _translate_survey_text(section.get("title", section["sectionId"])),
                "type": section.get("type", "categorical"),
                "instructions": _translate_survey_text(section.get("instructions")) if section.get("instructions") else None,
                "questions": [],
                "subsections": [],
            }

            if section.get("sectionId") == "S3":
                for subsection in section.get("subsections", []):
                    assigned_ids = _assignment_id_set(
                        cursor,
                        username,
                        phase,
                        section["sectionId"],
                        subsection["subsectionId"],
                    )
                    question_map = {
                        question["questionId"]: _decorate_question(
                            question,
                            inherited_scale=section.get("scale"),
                            subsection=subsection,
                        )
                        for question in subsection.get("questions", [])
                    }
                    section_view["subsections"].append(
                        {
                            "subsectionId": subsection["subsectionId"],
                            "topic": _translate_survey_text(subsection.get("topic")) if subsection.get("topic") else None,
                            "questions": [
                                question_map[question_id]
                                for question_id in assigned_ids
                                if question_id in question_map
                            ],
                        }
                    )
            elif section.get("subsections"):
                for subsection in section.get("subsections", []):
                    subsection_view = {
                        "subsectionId": subsection["subsectionId"],
                        "topic": _translate_survey_text(subsection.get("topic")) if subsection.get("topic") else None,
                        "questions": [
                            _decorate_question(
                                question,
                                inherited_scale=section.get("scale"),
                                subsection=subsection,
                            )
                            for question in subsection.get("questions", [])
                        ],
                    }
                    section_view["subsections"].append(subsection_view)
            else:
                section_view["questions"] = [
                    _decorate_question(question, inherited_scale=section.get("scale"))
                    for question in section.get("questions", [])
                ]

            sections.append(section_view)

    return {
        "phase": phase,
        "title": _translate_survey_text(survey.get("title", f"{phase.title()} Survey")),
        "description": _translate_survey_text(survey.get("description")) if survey.get("description") else None,
        "sections": sections,
        "consent": _translate_consent(get_consent_config()) if phase == "pre" else None,
    }


def _translate_consent(consent):
    if not consent:
        return None
    return {
        **consent,
        "prompt": _translate_survey_text(consent.get("prompt", "")),
        "details": _translate_survey_text(consent.get("details", "")),
        "acceptLabel": _translate_survey_text(consent.get("acceptLabel", "")),
        "declineLabel": _translate_survey_text(consent.get("declineLabel", "")),
    }


def _iter_questions(sections):
    for section in sections:
        for question in section.get("questions", []):
            yield question
        for subsection in section.get("subsections", []):
            for question in subsection.get("questions", []):
                yield question


def _coerce_answer(form_data, question):
    field_name = question["fieldName"]
    question_type = question["type"]
    if question_type == "multiChoice":
        values = form_data.getlist(field_name)
        return values
    return (form_data.get(field_name) or "").strip()


def validate_submission(form_data, survey_model):
    answers = {}
    validation_error = None

    consent_config = survey_model.get("consent")
    if consent_config:
        consent_value = (form_data.get("consent_response") or "").strip().lower()
        answers["consent_response"] = consent_value
        if consent_value not in {"yes", "no"}:
            return None, _("Please record your analytics consent choice before continuing.")
        if consent_config.get("required") and consent_value != "yes":
            return None, _("Consent is required before Silver Shield can collect survey and analytics data.")

    for question in _iter_questions(survey_model["sections"]):
        answer = _coerce_answer(form_data, question)
        if question["type"] == "multiChoice":
            if question.get("required", True) and not answer:
                validation_error = _("Please answer every required survey question before continuing.")
                break
        elif question.get("required", True) and answer == "":
            validation_error = _("Please answer every required survey question before continuing.")
            break

        if question["type"] == "numeric" and answer != "":
            try:
                numeric_answer = int(answer)
            except (TypeError, ValueError):
                validation_error = _("Please enter a whole number.")
                break

            minimum = question.get("min")
            maximum = question.get("max")
            if minimum is not None and numeric_answer < int(minimum):
                validation_error = _(
                    "This study is for adults age %(minimum)s and older.",
                    minimum=minimum,
                )
                break
            if maximum is not None and numeric_answer > int(maximum):
                validation_error = _(
                    "Please enter an age no greater than %(maximum)s.",
                    maximum=maximum,
                )
                break
        answers[question["questionId"]] = answer

    if validation_error:
        return None, validation_error
    return answers, None


def _numeric_average(answers, question_ids):
    numeric_values = []
    for question_id in question_ids:
        value = answers.get(question_id)
        if isinstance(value, list) or value in (None, ""):
            continue
        try:
            numeric_values.append(int(value))
        except (TypeError, ValueError):
            continue
    if not numeric_values:
        return None
    return round(sum(numeric_values) / len(numeric_values), 2)


def _compute_sus_score(answers):
    values = []
    for question_id in SUS_IDS:
        value = answers.get(question_id)
        if value in (None, ""):
            return None
        values.append(int(value))

    adjusted = 0
    for index, value in enumerate(values):
        if index % 2 == 0:
            adjusted += value - 1
        else:
            adjusted += 5 - value
    return adjusted * 2.5


def _json_value(value):
    if isinstance(value, list):
        return json.dumps(value)
    return value


def _upsert_pre_summary(cursor, username, answers):
    cursor.execute(
        """
        INSERT INTO pre_survey (
            username, age, device, confidence, response_json, completed_timestamp
        ) VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(username) DO UPDATE SET
            age = excluded.age,
            device = excluded.device,
            confidence = excluded.confidence,
            response_json = excluded.response_json,
            completed_timestamp = CURRENT_TIMESTAMP
        """,
        (
            username,
            answers.get("D1"),
            json.dumps(answers.get("D6", [])),
            _numeric_average(answers, SELF_EFFICACY_IDS),
            json.dumps(answers),
        ),
    )


def _upsert_post_summary(cursor, username, answers):
    cursor.execute(
        "DELETE FROM post_survey WHERE username = ?",
        (username,),
    )
    cursor.execute(
        """
        INSERT INTO post_survey (
            username,
            confidence_rating,
            perceived_usefulness,
            behavior_change,
            recommendation_likelihood,
            learning_rating,
            response_json,
            completed_timestamp
        ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """,
        (
            username,
            _numeric_average(answers, SELF_EFFICACY_IDS),
            _numeric_average(answers, USEFULNESS_IDS),
            json.dumps({question_id: answers.get(question_id) for question_id in ["BI1", "BI2", "BI3", "BI4", "BI5"]}),
            answers.get("HM2"),
            _numeric_average(answers, ENGAGEMENT_IDS),
            json.dumps(answers),
        ),
    )


def _upsert_usability_summary(cursor, username, answers):
    sus_score = _compute_sus_score(answers)
    if sus_score is None:
        return

    sus_values = [int(answers[question_id]) for question_id in SUS_IDS]
    cursor.execute("DELETE FROM system_usability_survey WHERE username = ?", (username,))
    cursor.execute(
        """
        INSERT INTO system_usability_survey (
            username, sus_q1, sus_q2, sus_q3, sus_q4, sus_q5,
            sus_q6, sus_q7, sus_q8, sus_q9, sus_q10, sus_score
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (username, *sus_values, sus_score),
    )


def save_survey_submission(db_path, username, phase, survey_model, answers):
    with db_connect(db_path) as conn:
        cursor = conn.cursor()

        if survey_model.get("consent"):
            cursor.execute(
                """
                INSERT INTO user_consents (
                    username, consent_type, granted, consent_text, consent_details, recorded_timestamp
                ) VALUES (?, 'analytics', ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(username, consent_type) DO UPDATE SET
                    granted = excluded.granted,
                    consent_text = excluded.consent_text,
                    consent_details = excluded.consent_details,
                    recorded_timestamp = CURRENT_TIMESTAMP
                """,
                (
                    username,
                    answers.get("consent_response") == "yes",
                    survey_model["consent"].get("prompt"),
                    survey_model["consent"].get("details"),
                ),
            )

        cursor.execute(
            "DELETE FROM survey_responses WHERE username = ? AND survey_phase = ?",
            (username, phase),
        )

        for question in _iter_questions(survey_model["sections"]):
            cursor.execute(
                """
                INSERT INTO survey_responses (
                    username, survey_phase, section_id, subsection_id, question_id, response_value
                ) VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT DO NOTHING
                """,
                (
                    username,
                    phase,
                    next(
                        section["sectionId"]
                        for section in survey_model["sections"]
                        if any(existing_question["questionId"] == question["questionId"] for existing_question in section.get("questions", []))
                        or any(
                            existing_question["questionId"] == question["questionId"]
                            for subsection in section.get("subsections", [])
                            for existing_question in subsection.get("questions", [])
                        )
                    ),
                    question.get("subsectionId"),
                    question["questionId"],
                    _json_value(answers.get(question["questionId"])),
                ),
            )

        if phase == "pre":
            _upsert_pre_summary(cursor, username, answers)
        else:
            _upsert_post_summary(cursor, username, answers)
            _upsert_usability_summary(cursor, username, answers)

        conn.commit()
