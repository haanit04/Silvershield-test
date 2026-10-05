from email_difficulty import in_band, level_for, score_email


SCAMMY = (
    "<p>Urgent: verify your password immediately or the account will be suspended.</p>"
    "<a href='https://login-alert-review.com'>amazon.com</a>"
)
CALM = (
    "<p>Your monthly statement is ready. Payment is due on the normal date.</p>"
    "<a href='https://cityutilities.com/statement'>View statement</a>"
)
POLITE = "<p>Hello, your monthly statement is ready when you have time.</p>"
LOOKALIKE = POLITE + "<a href='https://cityutilities-billing-review.com'>cityutilities.com</a>"
MATCHING = POLITE + "<a href='https://cityutilities.com/statement'>View statement</a>"


def test_scam_wording_scores_higher_than_a_routine_note():
    scam_score = score_email(SCAMMY)["p_spam"]
    calm_score = score_email(CALM)["p_spam"]
    assert scam_score > calm_score


def test_same_wording_is_easy_scam_and_hard_legitimate():
    p_spam = score_email(SCAMMY)["p_spam"]
    assert level_for(p_spam, "scam") == 1
    assert level_for(p_spam, "not_scam") == 4


def test_lookalike_domain_and_mismatched_link_raise_the_score():
    suspicious = score_email(LOOKALIKE)
    ordinary = score_email(MATCHING)
    assert suspicious["p_spam"] > ordinary["p_spam"]
    assert "feat_suspicious_domain" in suspicious["features"]
    assert "feat_link_mismatch" in suspicious["features"]


def test_obvious_scam_wording_is_outside_the_hard_phishing_band():
    p_spam = score_email(SCAMMY)["p_spam"]
    assert in_band(p_spam, "scam", 4) is False
    assert "verify" in score_email(SCAMMY)["top_scam_words"]


def test_generate_email_retries_until_the_level_band_matches(app_client, monkeypatch):
    client, app_module, _ = app_client
    monkeypatch.setattr(app_module.random, "random", lambda: 0.0)

    calls = {"n": 0}

    class Response:
        def __init__(self, html):
            self._html = html

        def json(self):
            return {"choices": [{"message": {"content": self._html}}]}

    def fake_post(*args, **kwargs):
        html = CALM if calls["n"] == 0 else SCAMMY
        calls["n"] += 1
        return Response(html)

    monkeypatch.setattr(app_module.requests, "post", fake_post)

    response = client.post("/generate-email", json={"platform": "desktop"})
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["success"] is True
    assert payload["expected_label"] == "scam"
    assert payload["difficulty"] == 1
    assert "Urgent" in payload["email"]
    assert calls["n"] == 2
    assert payload["p_spam"] >= 0.78
    assert "top_scam_words" not in payload
