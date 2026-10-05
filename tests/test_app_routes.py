import json
import sqlite3


def _seed_user(db_path, username="alice", password_hash="hashed"):
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO users (username, email, phone, address, password_hash)
            VALUES (?, ?, ?, ?, ?)
            """,
            (username, f"{username}@example.com", "1234567890", "123 Main St", password_hash),
        )
        conn.commit()

def _seed_pre_survey(db_path, username="alice"):
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO pre_survey (username, age, device, confidence) VALUES (?, ?, ?, ?)",
            (username, "25-34", "Both", 4),
        )
        conn.commit()


def _complete_module_pretest(client, app_module, db_path, module_name, username="alice"):
    _seed_pre_survey(db_path, username=username)
    response = client.get("/dashboard")
    assert response.status_code in {200, 302}


def _survey_answer_for(question):
    if question["type"] == "numeric":
        return "72"
    if question["type"] == "multiChoice":
        return [question["options"][0]]
    if question["type"] == "openText":
        return "No accessibility issues encountered."
    if question.get("scale"):
        return str(question["scale"]["max"])
    return question["options"][0]


def _build_survey_submission(app_module, db_path, username, phase, include_consent=True):
    survey_model = app_module.build_survey_view_model(db_path, username, phase)
    data = {}

    if include_consent and survey_model.get("consent"):
        data["consent_response"] = "yes"

    for section in survey_model["sections"]:
        for question in section.get("questions", []):
            data[question["fieldName"]] = _survey_answer_for(question)
        for subsection in section.get("subsections", []):
            for question in subsection.get("questions", []):
                data[question["fieldName"]] = _survey_answer_for(question)

    return data
def test_home_page_loads(app_client):
    client, _, _ = app_client
    response = client.get("/")
    assert response.status_code == 200


def test_user_performance_requires_login(app_client):
    client, _, _ = app_client
    response = client.get("/api/user_performance")

    assert response.status_code == 401
    assert response.get_json()["success"] is False


def test_register_and_login_flow(app_client):
    client, _, _ = app_client

    register_response = client.post(
        "/register",
        data={
            "username": "alice",
            "password": "StrongPass123!",
            "email": "alice@example.com",
            "phone": "1234567890",
            "address": "123 Main St",
        },
    )

    assert register_response.status_code == 200
    assert register_response.get_json()["success"] is True
    assert register_response.get_json()["redirect_url"].endswith("/pre_survey")

    login_response = client.post(
        "/login",
        data={"username": "alice", "password": "StrongPass123!"},
    )

    login_payload = login_response.get_json()
    assert login_response.status_code == 200
    assert login_payload["success"] is True
    assert login_payload["otp_sent"] is True


def test_seeded_test_user_bypasses_otp(app_client):
    client, app_module, _ = app_client

    send_otp_calls = []
    app_module.send_otp = lambda phone: send_otp_calls.append(phone)

    login_response = client.post(
        "/login",
        data={
            "username": app_module.TEST_USER_USERNAME,
            "password": "SilverShieldTest!1",
        },
    )

    login_payload = login_response.get_json()
    assert login_response.status_code == 200
    assert login_payload["success"] is True
    assert login_payload["twilio_bypassed"] is True
    assert login_payload["otp_sent"] is False
    assert send_otp_calls == []


def test_module_entry_requires_pre_survey_completion(app_client):
    client, _, db_path = app_client
    _seed_user(db_path, username="alice")

    with client.session_transaction() as session:
        session["username"] = "alice"

    response = client.get("/module1")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/pre_survey")


def test_module_entry_allows_access_after_pre_survey(app_client):
    client, _, db_path = app_client
    _seed_user(db_path, username="alice")

    with client.session_transaction() as session:
        session["username"] = "alice"

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO pre_survey (username, age, device, confidence) VALUES (?, ?, ?, ?)",
            ("alice", "25-34", "Both", 4),
        )
        conn.commit()

    response = client.get("/module1")

    assert response.status_code == 200
    assert 'class="module-back-link" href="/dashboard"' in response.get_data(as_text=True)


def test_module_assessment_routes_redirect_to_dashboard(app_client):
    client, _, db_path = app_client
    _seed_user(db_path, username="alice")

    with client.session_transaction() as session:
        session["username"] = "alice"

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO pre_survey (username, age, device, confidence) VALUES (?, ?, ?, ?)",
            ("alice", "25-34", "Both", 4),
        )
        conn.commit()

    pre_route_response = client.get("/module_assessment/desktop/pre")
    post_route_response = client.get("/module_assessment/desktop/post")
    list_route_response = client.get("/module_assessments")

    assert pre_route_response.status_code == 302
    assert pre_route_response.headers["Location"].endswith("/dashboard")
    assert post_route_response.status_code == 302
    assert post_route_response.headers["Location"].endswith("/dashboard")
    assert list_route_response.status_code == 302
    assert list_route_response.headers["Location"].endswith("/dashboard")


def test_module_back_button_points_to_dashboard(app_client):
    client, _, db_path = app_client
    _seed_user(db_path, username="alice")

    with client.session_transaction() as session:
        session["username"] = "alice"

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO pre_survey (username, age, device, confidence) VALUES (?, ?, ?, ?)",
            ("alice", "25-34", "Both", 4),
        )
        conn.commit()

    response = client.get("/module1")
    assert response.status_code == 200
    assert 'class="module-back-link" href="/dashboard"' in response.get_data(as_text=True)


def test_module_back_button_routes_to_post_survey_when_training_complete(app_client):
    client, _, db_path = app_client
    _seed_user(db_path, username="alice")

    with client.session_transaction() as session:
        session["username"] = "alice"

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO pre_survey (username, age, device, confidence) VALUES (?, ?, ?, ?)",
            ("alice", "25-34", "Both", 4),
        )
        conn.execute(
            """
            INSERT INTO module_progress (username, module_name, scenarios_completed, total_scenarios, last_accessed)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            ("alice", "email_desktop", 5, 5),
        )
        conn.execute(
            """
            INSERT INTO module_progress (username, module_name, scenarios_completed, total_scenarios, last_accessed)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            ("alice", "internet_desktop", 5, 5),
        )
        conn.execute(
            """
            INSERT INTO module_progress (username, module_name, scenarios_completed, total_scenarios, last_accessed)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            ("alice", "email_mobile", 5, 5),
        )
        conn.execute(
            """
            INSERT INTO module_progress (username, module_name, scenarios_completed, total_scenarios, last_accessed)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            ("alice", "sms_mobile", 5, 5),
        )
        conn.execute(
            """
            INSERT INTO module_progress (username, module_name, scenarios_completed, total_scenarios, last_accessed)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            ("alice", "call_mobile", 5, 5),
        )
        conn.execute(
            """
            INSERT INTO module_progress (username, module_name, scenarios_completed, total_scenarios, last_accessed)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            ("alice", "web_mobile", 5, 5),
        )
        conn.execute(
            """
            INSERT INTO module_progress (username, module_name, scenarios_completed, total_scenarios, last_accessed)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            ("alice", "phone_roleplay", 5, 5),
        )
        conn.commit()

    response = client.get("/module1")
    assert response.status_code == 200
    assert 'class="module-back-link" href="/post_survey"' in response.get_data(as_text=True)


def test_dashboard_redirects_to_post_survey_when_all_modules_complete(app_client):
    client, _, db_path = app_client
    _seed_user(db_path, username="alice")

    with client.session_transaction() as session:
        session["username"] = "alice"

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO pre_survey (username, age, device, confidence) VALUES (?, ?, ?, ?)",
            ("alice", "25-34", "Both", 4),
        )
        conn.commit()

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO module_progress (username, module_name, scenarios_completed, total_scenarios, last_accessed)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            ("alice", "email_desktop", 5, 5),
        )
        conn.execute(
            """
            INSERT INTO module_progress (username, module_name, scenarios_completed, total_scenarios, last_accessed)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            ("alice", "internet_desktop", 5, 5),
        )
        conn.execute(
            """
            INSERT INTO module_progress (username, module_name, scenarios_completed, total_scenarios, last_accessed)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            ("alice", "email_mobile", 5, 5),
        )
        conn.execute(
            """
            INSERT INTO module_progress (username, module_name, scenarios_completed, total_scenarios, last_accessed)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            ("alice", "sms_mobile", 5, 5),
        )
        conn.execute(
            """
            INSERT INTO module_progress (username, module_name, scenarios_completed, total_scenarios, last_accessed)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            ("alice", "call_mobile", 5, 5),
        )
        conn.execute(
            """
            INSERT INTO module_progress (username, module_name, scenarios_completed, total_scenarios, last_accessed)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            ("alice", "web_mobile", 5, 5),
        )
        conn.execute(
            """
            INSERT INTO module_progress (username, module_name, scenarios_completed, total_scenarios, last_accessed)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            ("alice", "phone_roleplay", 5, 5),
        )
        conn.commit()

    response = client.get("/dashboard")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/post_survey")


def test_dashboard_redirects_to_pre_survey_until_complete(app_client):
    client, _, db_path = app_client
    _seed_user(db_path, username="alice")

    with client.session_transaction() as session:
        session["username"] = "alice"

    response = client.get("/dashboard")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/pre_survey")

def test_mobile_module_renders_translated_spanish_labels(app_client):
    client, app_module, db_path = app_client
    _seed_user(db_path, username="alice")

    with client.session_transaction() as session:
        session["username"] = "alice"
        session["lang"] = "es"

    _complete_module_pretest(client, app_module, db_path, "mobile")

    response = client.get("/module2")
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert '<html lang="es">' in body
    assert "Módulo Móvil" in body


def test_desktop_module_renders_translated_chinese_labels(app_client):
    client, app_module, db_path = app_client
    _seed_user(db_path, username="alice")

    with client.session_transaction() as session:
        session["username"] = "alice"
        session["lang"] = "zh"

    _complete_module_pretest(client, app_module, db_path, "desktop")

    response = client.get("/module1")
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert '<html lang="zh">' in body
    assert ("桌面模块" in body) or ("Desktop Module" in body)
def test_dashboard_access_after_pre_survey_complete(app_client):
    client, _, db_path = app_client
    _seed_user(db_path, username="alice")

    with client.session_transaction() as session:
        session["username"] = "alice"

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO pre_survey (username, age, device, confidence) VALUES (?, ?, ?, ?)",
            ("alice", "25-34", "Both", 4),
        )
        conn.commit()

    response = client.get("/dashboard")
    assert response.status_code == 200


def test_pre_survey_saves_amplify_questions(app_client):
    client, app_module, db_path = app_client
    _seed_user(db_path, username="alice")

    with client.session_transaction() as session:
        session["username"] = "alice"

    response = client.post(
        "/pre_survey",
        data=_build_survey_submission(app_module, db_path, "alice", "pre"),
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/dashboard")

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT age, device, confidence, response_json
            FROM pre_survey
            WHERE username = ?
            """,
            ("alice",),
        )
        row = cursor.fetchone()

        cursor.execute(
            "SELECT granted FROM user_consents WHERE username = ? AND consent_type = 'analytics'",
            ("alice",),
        )
        consent_row = cursor.fetchone()

        cursor.execute(
            "SELECT COUNT(*) FROM survey_responses WHERE username = ? AND survey_phase = 'pre'",
            ("alice",),
        )
        response_count = cursor.fetchone()[0]

    assert row is not None
    assert row[0] == "72"
    assert "Desktop/Laptop" in row[1]
    assert row[2] == 7
    assert '"D1": "72"' in row[3]
    assert consent_row == (1,)
    assert response_count > 20

def test_pre_survey_requires_consent(app_client):
    client, app_module, db_path = app_client
    _seed_user(db_path, username="alice")

    with client.session_transaction() as session:
        session["username"] = "alice"

    response = client.post(
        "/pre_survey",
        data=_build_survey_submission(app_module, db_path, "alice", "pre", include_consent=False),
    )

    assert response.status_code == 200
    assert "consent" in response.get_data(as_text=True).lower()


def test_pre_survey_requires_participant_to_be_at_least_60(app_client):
    client, app_module, db_path = app_client
    _seed_user(db_path, username="alice")

    with client.session_transaction() as session:
        session["username"] = "alice"

    submission = _build_survey_submission(app_module, db_path, "alice", "pre")
    submission["D1"] = "59"
    response = client.post("/pre_survey", data=submission)

    assert response.status_code == 200
    assert "60" in response.get_data(as_text=True)


def test_post_survey_completes_training_flow_and_saves_usability_score(app_client, monkeypatch):
    client, app_module, db_path = app_client
    _seed_user(db_path, username="alice")

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO pre_survey (username, age, confidence, response_json)
            VALUES (?, ?, ?, ?)
            """,
            (
                "alice",
                "72",
                6,
                "{}",
            ),
        )
        conn.commit()

    with client.session_transaction() as session:
        session["username"] = "alice"

    monkeypatch.setattr(app_module, "_all_modules_training_complete", lambda username: (True, []))

    response = client.post(
        "/post_survey",
        data=_build_survey_submission(app_module, db_path, "alice", "post"),
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/dashboard")

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT confidence_rating, perceived_usefulness, response_json FROM post_survey WHERE username = ?",
            ("alice",),
        )
        post_row = cursor.fetchone()

        cursor.execute(
            "SELECT sus_q1, sus_q10, sus_score FROM system_usability_survey WHERE username = ?",
            ("alice",),
        )
        usability_row = cursor.fetchone()

    assert post_row[0] == 7
    assert post_row[1] == 5
    assert '"SUS1": "5"' in post_row[2]
    assert usability_row == (5, 5, 50.0)


def test_post_survey_uses_different_questions_from_same_subsections(app_client, monkeypatch):
    client, app_module, db_path = app_client
    _seed_user(db_path, username="alice")

    with client.session_transaction() as session:
        session["username"] = "alice"

    client.post("/pre_survey", data=_build_survey_submission(app_module, db_path, "alice", "pre"))

    monkeypatch.setattr(app_module, "_all_modules_training_complete", lambda username: (True, []))

    pre_model = app_module.build_survey_view_model(db_path, "alice", "pre")
    post_model = app_module.build_survey_view_model(db_path, "alice", "post")

    def knowledge_by_subsection(model):
        knowledge_section = next(section for section in model["sections"] if section["sectionId"] == "S3")
        return {
            subsection["subsectionId"]: {question["questionId"] for question in subsection["questions"]}
            for subsection in knowledge_section["subsections"]
        }

    pre_questions = knowledge_by_subsection(pre_model)
    post_questions = knowledge_by_subsection(post_model)

    assert set(pre_questions.keys()) == set(post_questions.keys())
    assert all(pre_questions[subsection_id].isdisjoint(post_questions[subsection_id]) for subsection_id in pre_questions)
def test_phone_roleplay_session_requires_login(app_client):
    client, _, _ = app_client
    response = client.post(
        "/phone-roleplay/start-session",
        json={"scenario_type": "bank_fraud", "difficulty_level": 2},
    )

    assert response.status_code == 401
    assert response.get_json()["success"] is False


def test_phone_roleplay_session_can_start_for_logged_in_user(app_client):
    client, _, db_path = app_client
    _seed_user(db_path, username="alice")

    with client.session_transaction() as session:
        session["username"] = "alice"

    response = client.post(
        "/phone-roleplay/start-session",
        json={"scenario_type": "bank_fraud", "difficulty_level": 2},
    )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["success"] is True
    assert payload["session_id"] > 0


def test_generate_sites_list_returns_results(app_client, monkeypatch):
    client, app_module, _ = app_client

    class FakeGroqResponse:
        def __init__(self, site_type):
            self.site_type = site_type

        def json(self):
            payload = {
                "title": f"{self.site_type.title()} Example",
                "url": f"https://{self.site_type}.example.com",
                "description": "Example description",
                "site_type": self.site_type,
            }
            return {"choices": [{"message": {"content": json.dumps(payload)}}]}

    def fake_post(url, headers=None, json=None, timeout=None):
        prompt = json["messages"][0]["content"]
        site_type = "phishing" if "PHISHING" in prompt else "legit"
        return FakeGroqResponse(site_type)

    monkeypatch.setattr(app_module.requests, "post", fake_post)

    response = client.post("/api/generate_sites", json={"mode": "list", "query": "bank login"})

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["success"] is True
    assert payload["query"] == "bank login"
    assert len(payload["results"]) == 5


def test_generate_web_search_returns_results(app_client, monkeypatch):
    client, app_module, _ = app_client

    class FakeGroqResponse:
        def __init__(self, content):
            self.content = content

        def json(self):
            return {"choices": [{"message": {"content": self.content}}]}

    def fake_post(url, headers=None, json=None, timeout=None):
        prompt = json["messages"][0]["content"]
        if "top-level keys: ads, results, pagination, clues" in prompt:
            payload = {
                "ads": [
                    {"title": "Official Bank Help", "url": "https://bank.example.com", "snippet": "Official support.", "site_type": "legit"},
                    {"title": "Verify Bank Login", "url": "https://bank-login-check.com", "snippet": "Urgent account action.", "site_type": "phishing"},
                ],
                "results": [
                    {"title": f"Result {idx}", "url": f"https://example{idx}.com", "snippet": "Example snippet", "site_type": "legit" if idx % 2 == 0 else "phishing"}
                    for idx in range(6)
                ],
                "pagination": {"next_page_label": "Next >", "page_number": 1},
                "clues": []
            }
            return FakeGroqResponse(json_module.dumps(payload))
        return FakeGroqResponse("<div><h2>Example Site</h2></div>")

    import json as json_module
    monkeypatch.setattr(app_module.requests, "post", fake_post)

    response = client.post("/generate-web", json={"mode": "search", "query": "bank login"})

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["success"] is True
    assert payload["query"] == "bank login"
    assert len(payload["web"]["ads"]) == 2
    assert len(payload["web"]["results"]) == 6


def test_internet_pages_fall_back_when_model_refuses(app_client, monkeypatch):
    client, app_module, _ = app_client
    refusal = "I cannot generate content that could be used to phishing victims. Is there something else I can help you with?"

    class RefusalResponse:
        def json(self):
            return {"choices": [{"message": {"content": refusal}}]}

    monkeypatch.setattr(app_module.requests, "post", lambda *args, **kwargs: RefusalResponse())

    desktop_response = client.post(
        "/api/generate_sites",
        json={
            "mode": "open",
            "query": "bank login",
            "title": "Bank Help Center",
            "url": "https://bank.example.com",
            "site_type": "phishing",
        },
    )
    mobile_response = client.post(
        "/generate-web",
        json={
            "mode": "open",
            "query": "bank login",
            "title": "Bank Help Center",
            "url": "https://bank.example.com",
            "site_type": "phishing",
        },
    )

    desktop_payload = desktop_response.get_json()
    mobile_payload = mobile_response.get_json()

    assert desktop_response.status_code == 200
    assert refusal not in desktop_payload["html"]
    assert "confirm" in desktop_payload["html"].lower() or "review" in desktop_payload["html"].lower()

    assert mobile_response.status_code == 200
    assert refusal not in mobile_payload["html"]
    assert "confirm" in mobile_payload["html"].lower() or "review" in mobile_payload["html"].lower()


def test_content_generators_fall_back_when_groq_returns_no_choices(app_client, monkeypatch):
    client, app_module, _ = app_client

    class EmptyGroqResponse:
        def json(self):
            return {}

    monkeypatch.setattr(app_module.requests, "post", lambda *args, **kwargs: EmptyGroqResponse())

    email_response = client.post("/generate-email", json={"platform": "mobile"})
    sms_response = client.post("/generate-sms", json={"theme": "bank login"})
    call_response = client.post("/generate-call", json={"theme": "bank support"})

    email_payload = email_response.get_json()
    sms_payload = sms_response.get_json()
    call_payload = call_response.get_json()

    assert email_response.status_code == 200
    assert email_payload["success"] is True
    assert email_payload["email"]
    assert email_payload["expected_label"] in {"scam", "not_scam"}
    assert email_payload["difficulty"] == 1
    assert isinstance(email_payload["p_spam"], float)

    assert sms_response.status_code == 200
    assert sms_payload["success"] is True
    assert sms_payload["sms"]["text"]

    assert call_response.status_code == 200
    assert call_payload["success"] is True
    assert call_payload["call"]["transcript"]
