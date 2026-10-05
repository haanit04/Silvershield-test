from flask import Flask, render_template, request, jsonify, flash, session, redirect, url_for, send_file, abort
import os
import sqlite3
import random
import hashlib
from dotenv import load_dotenv
import requests
from database import init_database, TEST_USER_USERNAME
from user_login import user_registration, verifying_login
from TWOFA import send_otp, verify_otp
from flask_babel import Babel, gettext, get_locale, _
import json
from datetime import datetime, timezone
import time
from urllib.parse import urlparse
from metrics import (log_scenario_attempt, log_critical_indicators, 
                     update_module_progress, get_user_performance, get_module_progress, 
                     get_attempt_history, get_survey_comparison, get_learning_metrics)
from survey_engine import build_survey_view_model, validate_submission, save_survey_submission
from email_difficulty import band_distance, clamp_level, level_guidance, score_email

load_dotenv()

# Read runtime secrets from environment (.env locally, Render env vars in deployment)
GROQ_KEY = os.getenv("GROQ_KEY")
SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-change-me")
DB_DOWNLOAD_TOKEN = os.getenv("DB_DOWNLOAD_TOKEN")

# Database path (can be overridden in deployment)
DB_PATH = os.getenv("DB_PATH", "silvershieldDatabase.db")

app = Flask(__name__)
app.secret_key = SECRET_KEY
init_database()

# Babel locale selector
def select_locale():
    return session.get('lang', request.accept_languages.best_match(['en', 'es', 'zh']))


def get_llm_output_language():
    lang = session.get('lang', request.accept_languages.best_match(['en', 'es', 'zh'])) or 'en'
    lang = str(lang).lower()
    if lang.startswith('es'):
        return "Spanish"
    if lang.startswith('zh'):
        return "Chinese"
    return "English"


def is_model_refusal(text):
    lowered = (text or "").lower()
    refusal_markers = (
        "i cannot generate content",
        "i can't generate content",
        "i cannot assist with that",
        "i can't assist with that",
        "phishing victims",
        "something else i can help you with",
    )
    return any(marker in lowered for marker in refusal_markers)


MODULE_ROUTE_MAP = {
    "desktop": "module1",
    "mobile": "module2",
    "phone": "phone_roleplay",
}

MODULE_LABELS = {
    "desktop": "Desktop Simulation",
    "mobile": "Mobile Simulation",
    "phone": "Phone Role-Play",
}

MODULE_PROGRESS_REQUIREMENTS = {
    "desktop": ["email_desktop", "internet_desktop"],
    "mobile": ["email_mobile", "sms_mobile", "call_mobile", "web_mobile"],
    "phone": ["phone_roleplay"],
}

REQUIRED_ATTEMPTS_PER_SIMULATION = 5

MODULE_ASSESSMENT_QUESTION_BANKS = {
    "desktop": [
        {
            "id": 1,
            "channel": "email",
            "difficulty": 1,
            "prompt": "Do you think the following email screenshot is real?",
            "email_from": "Samantha Jenkins <samantha.jenkins@amazonpayreview.com>",
            "email_subject": "Urgent: Amazon Pay Update Required",
            "email_html": "<p>Dear valued customer,</p><p>We have recently updated our Amazon Pay system to provide an enhanced user experience. To ensure a seamless transition, it is essential that you reset your password and update your account information.</p><p>Please click <a href='https://amazonpayreview.com/account-update'>here</a> to complete the required steps.</p><p>If you need assistance, contact support at 1-800-123-4567. We are available 24/7.</p><p>Best regards,<br>Samantha Jenkins</p>",
            "options": ["real", "fake"],
            "correct": "fake"
        },
        {
            "id": 2,
            "channel": "email",
            "difficulty": 1,
            "prompt": "Do you think the following email screenshot is real?",
            "email_from": "City Utilities Billing <billing@cityutilities.com>",
            "email_subject": "Monthly Statement Available",
            "email_html": "<p>Hello,</p><p>Your monthly utility statement is now available in your account dashboard. Payment is due on your normal billing date.</p><p>To view your statement, sign in directly through your saved utility portal bookmark or by typing cityutilities.com in your browser.</p><p>Thank you,<br>City Utilities Billing Team</p>",
            "options": ["real", "fake"],
            "correct": "real"
        },
        {
            "id": 3,
            "channel": "email",
            "difficulty": 2,
            "prompt": "Do you think the following email screenshot is real?",
            "email_from": "FedEx Delivery Center <alerts@fedex-delivery-update.net>",
            "email_subject": "Action Needed: Delivery On Hold",
            "email_html": "<p>Hi,</p><p>Your package could not be delivered and is now on hold.</p><p>Pay a re-delivery fee of $2.00 within 12 hours to avoid return to sender:</p><p><a href='https://fedex-delivery-update.net/release'>Release My Package</a></p><p>FedEx Support</p>",
            "options": ["real", "fake"],
            "correct": "fake"
        },
        {
            "id": 4,
            "channel": "email",
            "difficulty": 2,
            "prompt": "Do you think the following email screenshot is real?",
            "email_from": "HR Benefits Team <benefits@contoso.com>",
            "email_subject": "Open Enrollment Reminder",
            "email_html": "<p>Hello team member,</p><p>This is a reminder that open enrollment closes Friday at 5:00 PM.</p><p>Please review plan updates using the HR portal. Do not share passwords or one-time codes with anyone.</p><p>Regards,<br>HR Benefits Team</p>",
            "options": ["real", "fake"],
            "correct": "real"
        },
        {
            "id": 5,
            "channel": "email",
            "difficulty": 3,
            "prompt": "Do you think the following email screenshot is real?",
            "email_from": "Chase Security Desk <alerts@secure-chasehelp.com>",
            "email_subject": "Suspicious Login Detected",
            "email_html": "<p>We noticed unusual login activity on your account.</p><p>For your protection, reply to this email with the one-time code we just sent to your phone so we can verify your identity and unlock access.</p><p>If we do not receive the code in 10 minutes, your account will be frozen.</p>",
            "options": ["real", "fake"],
            "correct": "fake"
        },

       

        {"id": 6, "channel": "chrome", "difficulty": 1, "prompt": "Top search result says IRS payment portal and links to irs-payment-help.net with a Sponsored label. Is this real or fake?", "options": ["real", "fake"], "correct": "fake"},
        {"id": 7, "channel": "chrome", "difficulty": 2, "prompt": "Chrome warning page states Deceptive site ahead for a domain you tried to open. Is this real or fake?", "options": ["real", "fake"], "correct": "real"},
        {"id": 8, "channel": "chrome", "difficulty": 2, "prompt": "Browser popup claims your computer is infected and asks you to call support immediately to avoid data loss. Is this real or fake?", "options": ["real", "fake"], "correct": "fake"},
        {"id": 9, "channel": "chrome", "difficulty": 3, "prompt": "Sign-in page looks like PayPal but URL is paypa1.com/security-check before login. Is this real or fake?", "options": ["real", "fake"], "correct": "fake"},
        {"id": 10, "channel": "chrome", "difficulty": 3, "prompt": "Website shows HTTPS and padlock but asks for full card number, PIN, and OTP on one form. Is this real or fake?", "options": ["real", "fake"], "correct": "fake"},
    ],
    "mobile": [
        {"id": 101, "channel": "email", "difficulty": 1, "prompt": "Mobile email says your Google account storage is full and asks you to sign in using a link to account-recovery-storage.com. Is this real or fake?", "app_label": "Gmail", "email_from": "Google Storage <notice@account-recovery-storage.com>", "email_subject": "Storage limit reached - immediate action", "email_html": "<p>Your cloud storage is full.</p><p>Sign in now to prevent account restrictions: <a href='https://account-recovery-storage.com'>Review storage</a>.</p>", "options": ["real", "fake"], "correct": "fake"},
        {"id": 102, "channel": "email", "difficulty": 2, "prompt": "Email receipt from Apple for an app purchase matches your device and links to reportaproblem.apple.com only. Is this real or fake?", "app_label": "Gmail", "email_from": "Apple <do_not_reply@apple.com>", "email_subject": "Your App Store receipt", "email_html": "<p>Thanks for your purchase.</p><p>If this was not you, visit <a href='https://reportaproblem.apple.com'>reportaproblem.apple.com</a>.</p>", "options": ["real", "fake"], "correct": "real"},
        {"id": 103, "channel": "email", "difficulty": 2, "prompt": "Email claims your payroll direct deposit changed and tells you to verify by sharing your password in reply. Is this real or fake?", "app_label": "Gmail", "email_from": "Payroll Team <payroll-alert@company-payroll-help.com>", "email_subject": "Urgent payroll verification", "email_html": "<p>We detected a direct deposit change request.</p><p>Reply with your employee password to confirm no changes are needed.</p>", "options": ["real", "fake"], "correct": "fake"},
        {"id": 104, "channel": "sms", "difficulty": 1, "prompt": "SMS says FedEx package is delayed and requires a small fee at fdx-track-help.info to continue delivery. Is this real or fake?", "sender": "48773", "message": "FedEx: Delivery on hold. Pay $2.00 to release package: fdx-track-help.info", "options": ["real", "fake"], "correct": "fake"},
        {"id": 105, "channel": "sms", "difficulty": 2, "prompt": "Text from your bank says do not share this one-time code with anyone and contains no links. Is this real or fake?", "sender": "YourBank", "message": "Your one-time code is 881204. We will never ask for this code by call or text.", "options": ["real", "fake"], "correct": "real"},
        {"id": 106, "channel": "sms", "difficulty": 2, "prompt": "SMS says Congratulations, claim gift card now by tapping bit.ly/reward-now in 10 minutes. Is this real or fake?", "sender": "PrizeCenter", "message": "Congrats! You were selected for a gift card. Claim in 10 minutes: bit.ly/reward-now", "options": ["real", "fake"], "correct": "fake"},
        {"id": 107, "channel": "phone", "difficulty": 2, "prompt": "Caller says they are bank fraud team and asks for card number and OTP to secure your account immediately. Is this real or fake?", "caller_name": "Bank Fraud Dept.", "caller_number": "(800) 555-2319", "call_line": "For security verification, read me your one-time code and card number now.", "options": ["real", "fake"], "correct": "fake"},
        {"id": 108, "channel": "phone", "difficulty": 3, "prompt": "Caller says they are Microsoft support and requests remote access app installation to remove malware from your phone. Is this real or fake?", "caller_name": "Microsoft Support", "caller_number": "(888) 555-4402", "call_line": "Install this remote app now so I can clean your phone and secure your accounts.", "options": ["real", "fake"], "correct": "fake"},
        {"id": 109, "channel": "phone", "difficulty": 3, "prompt": "Caller claims to be a relative in urgent trouble and asks for gift card payment while telling you not to contact family. Is this real or fake?", "caller_name": "Unknown Family Caller", "caller_number": "(619) 555-7802", "call_line": "Please do not call anyone. Just buy gift cards now and read me the numbers.", "options": ["real", "fake"], "correct": "fake"},
        {"id": 110, "channel": "chrome", "difficulty": 1, "prompt": "Mobile browser page says Session expired, sign in again at chase-secure-login.co to avoid account lock. Is this real or fake?", "browser_url": "https://chase-secure-login.co/session", "browser_title": "Chase Secure Sign-In", "browser_snippet": "Your session expired. Sign in within 2 minutes to avoid temporary account lock.", "options": ["real", "fake"], "correct": "fake"},
        {"id": 111, "channel": "chrome", "difficulty": 2, "prompt": "Chrome on mobile warns This site may be trying to steal your information before loading. Is this real or fake?", "browser_url": "chrome://safe-browsing-warning", "browser_title": "Security warning", "browser_snippet": "Chrome blocked this page because it may trick you into revealing passwords or card data.", "options": ["real", "fake"], "correct": "real"},
    ],
    "phone": [
        {"id": 201, "channel": "phone", "difficulty": 1, "prompt": "Caller says they are your bank and needs your one-time code right now to stop fraud. Is this real or fake?", "caller_name": "Bank Fraud Dept.", "caller_number": "(800) 555-2319", "call_line": "Read the one-time code now or your account will be locked.", "options": ["real", "fake"], "correct": "fake"},
        {"id": 202, "channel": "phone", "difficulty": 1, "prompt": "Caller says there is a tax warrant and demands gift card payment within 30 minutes. Is this real or fake?", "caller_name": "Government Office", "caller_number": "(877) 555-9021", "call_line": "Pay with gift cards in 30 minutes or police will be dispatched.", "options": ["real", "fake"], "correct": "fake"},
        {"id": 203, "channel": "phone", "difficulty": 2, "prompt": "Caller says they are tech support and asks you to install remote software during the call. Is this real or fake?", "caller_name": "Microsoft Support", "caller_number": "(888) 555-4402", "call_line": "Install the remote app so I can remove malware from your device.", "options": ["real", "fake"], "correct": "fake"},
        {"id": 204, "channel": "phone", "difficulty": 2, "prompt": "Caller says they are your grandchild and asks for urgent money but refuses to answer personal verification questions. Is this real or fake?", "caller_name": "Unknown Family Member", "caller_number": "(619) 555-7802", "call_line": "Do not call anyone else, please wire money right now.", "options": ["real", "fake"], "correct": "fake"},
        {"id": 205, "channel": "phone", "difficulty": 2, "prompt": "Caller says they are from Social Security and requests your full SSN to prevent benefits suspension today. Is this real or fake?", "caller_name": "Social Security Office", "caller_number": "(855) 555-1020", "call_line": "Verify your full SSN now to avoid immediate suspension.", "options": ["real", "fake"], "correct": "fake"},
        {"id": 206, "channel": "phone", "difficulty": 2, "prompt": "Caller asks you to keep the call secret and not speak with family while you send payment. Is this real or fake?", "caller_name": "Account Resolution Team", "caller_number": "(844) 555-7642", "call_line": "For your safety, keep this confidential and do not call family.", "options": ["real", "fake"], "correct": "fake"},
        {"id": 207, "channel": "phone", "difficulty": 3, "prompt": "Caller ID shows your bank name, but caller asks for debit PIN and CVV to verify identity. Is this real or fake?", "caller_name": "Bank Security", "caller_number": "(800) 555-7621", "call_line": "To verify identity, provide your card PIN and CVV now.", "options": ["real", "fake"], "correct": "fake"},
        {"id": 208, "channel": "phone", "difficulty": 3, "prompt": "Caller threatens account freeze unless you move funds to a safe account by wire transfer now. Is this real or fake?", "caller_name": "Fraud Escalation Unit", "caller_number": "(833) 555-2701", "call_line": "Wire your balance to our safe account immediately to prevent loss.", "options": ["real", "fake"], "correct": "fake"},
        {"id": 209, "channel": "phone", "difficulty": 3, "prompt": "Caller says they are government collections and refuses to send official documents by mail or secure portal. Is this real or fake?", "caller_name": "Collections Office", "caller_number": "(866) 555-3188", "call_line": "No paperwork will be sent. Pay now by phone to resolve this case.", "options": ["real", "fake"], "correct": "fake"},
        {"id": 210, "channel": "phone", "difficulty": 3, "prompt": "Caller claims to be your mobile carrier and asks for MFA code to restore service after suspicious login. Is this real or fake?", "caller_name": "Carrier Security", "caller_number": "(877) 555-6651", "call_line": "Tell me the texted verification code so I can restore your service.", "options": ["real", "fake"], "correct": "fake"},
    ],
}

# Backward-compatible alias used by tests and tooling.
MODULE_ASSESSMENT_QUESTION_BANK = MODULE_ASSESSMENT_QUESTION_BANKS["desktop"]


def _get_module_question_bank(module_name):
    return MODULE_ASSESSMENT_QUESTION_BANKS.get(module_name, MODULE_ASSESSMENT_QUESTION_BANKS["desktop"])


def _get_module_question_map(module_name):
    bank = _get_module_question_bank(module_name)
    return {question["id"]: question for question in bank}


def _get_module_redirect(module_name):
    route_name = MODULE_ROUTE_MAP.get(module_name)
    if not route_name:
        return redirect('/dashboard')
    return redirect(url_for(route_name))


def _is_module_phase_complete(username, module_name, phase):
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute(
            '''SELECT COUNT(*)
               FROM module_assessment_assignments
               WHERE username = ? AND module_name = ? AND phase = ?''',
            (username, module_name, phase),
        )
        target_count = cur.fetchone()[0]

        cur.execute(
            '''SELECT COUNT(*)
               FROM module_assessment_results
               WHERE username = ? AND module_name = ? AND phase = ?''',
            (username, module_name, phase),
        )
        answered_count = cur.fetchone()[0]
    return target_count > 0 and answered_count >= target_count


def _get_or_create_module_variant(username, module_name):
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute(
            '''SELECT variant
               FROM module_assessment_enrollments
               WHERE username = ? AND module_name = ?''',
            (username, module_name),
        )
        row = cur.fetchone()
        if row:
            return row[0]

        digest = hashlib.sha256(f"{username}:{module_name}".encode("utf-8")).hexdigest()
        variant = 'A' if int(digest[:8], 16) % 2 == 0 else 'B'
        cur.execute(
            '''INSERT INTO module_assessment_enrollments (username, module_name, variant)
               VALUES (?, ?, ?)''',
            (username, module_name, variant),
        )
        conn.commit()
        return variant


def _balanced_pre_question_ids_for_seed(module_name, seed_value):
    rng = random.Random(seed_value)
    bank = _get_module_question_bank(module_name)
    question_ids = [q["id"] for q in bank]
    question_map = _get_module_question_map(module_name)
    pre_count = max(1, len(question_ids) // 2)
    post_count = len(question_ids) - pre_count
    best_pre_ids = None
    best_diff = None

    for _ in range(250):
        pre_ids = set(rng.sample(question_ids, pre_count))
        post_ids = [qid for qid in question_ids if qid not in pre_ids]

        pre_avg = sum(question_map[qid]["difficulty"] for qid in pre_ids) / pre_count
        post_avg = sum(question_map[qid]["difficulty"] for qid in post_ids) / post_count
        diff = abs(pre_avg - post_avg)

        if best_diff is None or diff < best_diff:
            best_diff = diff
            best_pre_ids = pre_ids

        if diff <= 0.20:
            return pre_ids

    return best_pre_ids or set(question_ids[:5])


def _ensure_module_question_assignments(username, module_name):
    variant = _get_or_create_module_variant(username, module_name)
    bank = _get_module_question_bank(module_name)
    expected_total = len(bank)

    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute(
            '''SELECT question_id, phase
               FROM module_assessment_assignments
               WHERE username = ? AND module_name = ?''',
            (username, module_name),
        )
        rows = cur.fetchall()

        if len(rows) == expected_total:
            return

        if rows:
            cur.execute(
                '''DELETE FROM module_assessment_results
                   WHERE username = ? AND module_name = ?''',
                (username, module_name),
            )
            cur.execute(
                '''DELETE FROM module_assessment_assignments
                   WHERE username = ? AND module_name = ?''',
                (username, module_name),
            )

        pre_ids = _balanced_pre_question_ids_for_seed(module_name, f"{username}:{module_name}:{variant}")
        for question in bank:
            phase = "pre" if question["id"] in pre_ids else "post"
            cur.execute(
                '''INSERT INTO module_assessment_assignments
                   (username, module_name, question_id, phase, difficulty_level)
                   VALUES (?, ?, ?, ?, ?)''',
                (username, module_name, question["id"], phase, question["difficulty"]),
            )

        conn.commit()


def _get_module_phase_questions(username, module_name, phase):
    question_map = _get_module_question_map(module_name)

    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute(
            '''SELECT question_id
               FROM module_assessment_assignments
               WHERE username = ? AND module_name = ? AND phase = ?''',
            (username, module_name, phase),
        )
        question_ids = [row[0] for row in cur.fetchall()]

    random.shuffle(question_ids)
    return [question_map[qid] for qid in question_ids if qid in question_map]


def _build_module_assessment_status(username):
    status = []
    for module_name, route_name in MODULE_ROUTE_MAP.items():
        variant = _get_or_create_module_variant(username, module_name)
        _ensure_module_question_assignments(username, module_name)
        pre_complete = _is_module_phase_complete(username, module_name, 'pre')
        post_complete = _is_module_phase_complete(username, module_name, 'post')
        training_complete = _is_module_training_complete(username, module_name)
        post_available = pre_complete and training_complete
        status.append({
            "module_name": module_name,
            "module_label": _(MODULE_LABELS.get(module_name, module_name.title())),
            "variant": variant,
            "pre_complete": pre_complete,
            "post_complete": post_complete,
            "training_complete": training_complete,
            "post_available": post_available,
            "module_url": url_for(route_name),
            "pre_url": url_for('module_assessment', module_name=module_name, phase='pre'),
            "post_url": url_for('module_assessment', module_name=module_name, phase='post'),
        })
    return status


def _require_module_pretest(module_name):
    username = session.get('username')
    if not username:
        return redirect('/login')

    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM pre_survey WHERE username = ?", (username,))
        if not cur.fetchone():
            flash(_('Please complete the pre-survey first.'), 'info')
            return redirect('/pre_survey')

    _ensure_module_question_assignments(username, module_name)
    if _is_module_phase_complete(username, module_name, 'pre'):
        return None

    flash(_('Please complete the module pre-test first.'), 'info')
    return redirect(url_for('module_assessment', module_name=module_name, phase='pre'))


def _is_module_training_complete(username, module_name):
    required_progress_keys = MODULE_PROGRESS_REQUIREMENTS.get(module_name, [])
    if not required_progress_keys:
        return False

    placeholders = ",".join("?" for _ in required_progress_keys)
    params = [username] + required_progress_keys
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute(
            f'''SELECT module_name, scenarios_completed
                FROM module_progress
                WHERE username = ? AND module_name IN ({placeholders})''',
            params,
        )
        rows = cur.fetchall()

    progress_by_module = {row[0]: row for row in rows}
    for progress_key in required_progress_keys:
        row = progress_by_module.get(progress_key)
        if not row:
            return False
        completed = row[1] or 0
        if completed < REQUIRED_ATTEMPTS_PER_SIMULATION:
            return False
    return True


def _next_incomplete_training_target(username):
    for module_name, route_name in MODULE_ROUTE_MAP.items():
        if not _is_module_training_complete(username, module_name):
            return route_name, _(MODULE_LABELS.get(module_name, module_name.title()))
    fallback_route = next(iter(MODULE_ROUTE_MAP.values()), 'dashboard')
    return fallback_route, _("Training")


def _build_module_posttest_context(username, module_name):
    pre_complete = _is_module_phase_complete(username, module_name, 'pre')
    post_complete = _is_module_phase_complete(username, module_name, 'post')
    training_complete = _is_module_training_complete(username, module_name)
    show_post_test_button = pre_complete and training_complete and not post_complete
    post_test_url = url_for('module_assessment', module_name=module_name, phase='post')
    back_to_dashboard_url = post_test_url if show_post_test_button else url_for('dashboard')
    return {
        "show_post_test_button": show_post_test_button,
        "post_test_url": post_test_url,
        "back_to_dashboard_url": back_to_dashboard_url,
    }

def _has_completed_survey(username, table_name):
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute(f"SELECT 1 FROM {table_name} WHERE username = ? LIMIT 1", (username,))
        return cur.fetchone() is not None


def _all_module_assessments_complete(username):
    module_status = _build_module_assessment_status(username)
    return (
        bool(module_status)
        and all(item["pre_complete"] and item["post_complete"] for item in module_status)
    ), module_status


def _all_modules_training_complete(username):
    module_status = []
    for module_name in MODULE_ROUTE_MAP:
        module_status.append({
            "module_name": module_name,
            "training_complete": _is_module_training_complete(username, module_name),
        })
    return bool(module_status) and all(item["training_complete"] for item in module_status), module_status


def _require_pre_survey_completion(username):
    if _has_completed_survey(username, 'pre_survey'):
        return None
    flash(_('Please complete the pre-training survey before starting modules.'), 'info')
    return redirect('/pre_survey')


def _module_back_url(username):
    all_module_training_complete, module_training_status = _all_modules_training_complete(username)
    if all_module_training_complete and not _has_completed_survey(username, 'post_survey'):
        return url_for('post_survey')
    return url_for('dashboard')
babel = Babel(app, locale_selector=select_locale)


@app.context_processor
def inject_template_helpers():
    return {"get_locale": get_locale}

# Homepage route

# Validate redirects to avoid open redirects from untrusted `next` params.
def _is_safe_redirect_target(target_url):
    if not target_url:
        return False
    parsed_target = urlparse(target_url)
    if parsed_target.scheme or parsed_target.netloc:
        return False
    return target_url.startswith('/')


# Language switch route
@app.route('/set_language/<lang>')
def set_language(lang):
    if lang in ('en', 'es', 'zh'):
        session['lang'] = lang
    next_url = request.args.get('next', '').strip()
    if _is_safe_redirect_target(next_url):
        return redirect(next_url)
    return redirect(request.referrer or url_for('home'))

# Register multimodal blueprint (text-to-speech) if available
try:
    from multimodal import multimodal_bp
    app.register_blueprint(multimodal_bp)
except Exception as _err:
    print('Multimodal blueprint not registered:', _err)

################################
# Loading difficulty from
#       the database
################################
def get_difficulty(category):
    username = session.get('username')
    if not username:
        return 1

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(f'SELECT {category} FROM users WHERE username = ?', (username,))
        row = cursor.fetchone()

    return row[0] if row else 1

################################
# Saving difficulty to the
#        database
################################
def set_difficulty(category, level):
    # 1 - easy, 2 - medium, 3 - hard, 4 - very hard
    level = max(1, min(4, level))

    username = session.get('username')
    if not username:
        return

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(f'UPDATE users SET {category} = ? WHERE username = ?', (level, username))
        conn.commit()

################################
#         Page routes
################################
# Pre Survey #####################

@app.route('/')
def home():
    # Use the same function as Babel
    current_lang = session.get('lang', request.accept_languages.best_match(['en', 'es', 'zh']))
    return render_template('homePage.html', current_lang=current_lang)


@app.route('/pre_survey', methods=['GET', 'POST'])
def pre_survey():
    username = session.get('username')
    if not username:
        return redirect('/login')

    if _has_completed_survey(username, 'pre_survey'):
        return redirect('/dashboard') 

    survey_model = build_survey_view_model(DB_PATH, username, 'pre')
    if request.method == 'POST':
        answers, error_message = validate_submission(request.form, survey_model)
        if error_message:
            flash(error_message, 'error')
            return render_template('survey.html', survey=survey_model)

        save_survey_submission(DB_PATH, username, 'pre', survey_model, answers)
        flash(_('Pre-training survey saved. You can now begin the training modules.'), 'success')
        return redirect('/dashboard')

    return render_template('survey.html', survey=survey_model)


@app.route('/pre_survey_demographics', methods=['GET', 'POST'])
def pre_survey_demographics():
    username = session.get('username')
    if not username:
        return redirect('/login')

    return redirect('/pre_survey')





@app.route('/login', methods=['GET'])
def login():
    return render_template("loginPage.html")


@app.route('/account_creation')
def account_creation():
    return render_template("accountCreation.html")


@app.route('/dashboard')
def dashboard():
    username = session.get('username')
    if not username:
        return redirect('/login')

    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM pre_survey WHERE username = ?", (username,))
        pre_survey_done = cur.fetchone() is not None

    if not pre_survey_done:
        return redirect('/pre_survey')

    all_module_training_complete, module_training_status = _all_modules_training_complete(username)
    post_survey_done = _has_completed_survey(username, 'post_survey')

    if all_module_training_complete and not post_survey_done:
        flash(_('Please complete the post-training survey to finish the training flow.'), 'info')
        return redirect(url_for('post_survey'))
    elif all_module_training_complete:
        assessment_cta_url = url_for('dashboard')
        assessment_cta_title = _("Training Complete")
        assessment_cta_button_label = _("Review Dashboard")
        assessment_cta_description = _("You have completed the post-training survey and all training modules.")
        assessment_cta_hero_label = _("All Final Steps Complete")
    else:
        next_route, next_module_label = _next_incomplete_training_target(username)
        assessment_cta_url = url_for(next_route)
        assessment_cta_title = _("Continue %(module)s", module=next_module_label)
        assessment_cta_button_label = _("Continue %(module)s", module=next_module_label)
        assessment_cta_description = _(
            "Each simulation requires %(attempts)s attempts. Continue where you left off.",
            attempts=REQUIRED_ATTEMPTS_PER_SIMULATION,
        )
        assessment_cta_hero_label = _("Continue %(module)s", module=next_module_label)

    return render_template(
        "dashboard.html",
        module_training_status=module_training_status,
        assessment_cta_url=assessment_cta_url,
        assessment_cta_title=assessment_cta_title,
        assessment_cta_button_label=assessment_cta_button_label,
        assessment_cta_description=assessment_cta_description,
        assessment_cta_hero_label=assessment_cta_hero_label,
    )

@app.route('/post_survey', methods=['GET', 'POST'])
def post_survey():
    username = session.get('username')
    if not username:
        return redirect('/login')

    if _has_completed_survey(username, 'post_survey'):
        return redirect('/dashboard')

    all_module_training_complete, module_training_status = _all_modules_training_complete(username)
    if not all_module_training_complete:
        flash(_('Please complete all training modules before taking the post-training survey.'), 'info')
        return redirect('/dashboard')

    survey_model = build_survey_view_model(DB_PATH, username, 'post')
    if request.method == 'POST':
        answers, error_message = validate_submission(request.form, survey_model)
        if error_message:
            flash(error_message, 'error')
            return render_template('survey.html', survey=survey_model)

        save_survey_submission(DB_PATH, username, 'post', survey_model, answers)
        flash(_('Post-training survey saved. You have completed the full training flow.'), 'success')
        return redirect('/dashboard')

    return render_template('survey.html', survey=survey_model)


@app.route('/system_usability_survey', methods=['GET', 'POST'])
def system_usability_survey():
    username = session.get('username')
    if not username:
        return redirect('/login')

    if not _has_completed_survey(username, 'post_survey'):
        flash(_('The usability items are included in the post-training survey.'), 'info')
        return redirect('/post_survey')

    flash(_('The usability items are included in the post-training survey.'), 'info')
    return redirect('/dashboard')
@app.route("/reset_presurvey")
def reset_presurvey():
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("DROP TABLE IF EXISTS pre_survey")
        conn.commit()
    return "pre_survey table dropped. Restart the server now."


@app.route('/admin/download-db', methods=['GET'])
def download_database():
    token = request.args.get('token', '')

    if not DB_DOWNLOAD_TOKEN or token != DB_DOWNLOAD_TOKEN:
        abort(403)

    if not os.path.exists(DB_PATH):
        return jsonify({"success": False, "error": "Database file not found"}), 404

    return send_file(
        DB_PATH,
        as_attachment=True,
        download_name=os.path.basename(DB_PATH)
    )


@app.route('/module1')
def module1():
    username = session.get('username')
    if not username:
        return redirect('/login')
    redirect_response = _require_pre_survey_completion(username)
    if redirect_response:
        return redirect_response
    return render_template("desktopPage.html", back_to_dashboard_url=_module_back_url(username))


@app.route('/module2')
def module2():
    username = session.get('username')
    if not username:
        return redirect('/login')
    redirect_response = _require_pre_survey_completion(username)
    if redirect_response:
        return redirect_response
    return render_template("MobilePage.html", back_to_dashboard_url=_module_back_url(username))

@app.route('/phone_roleplay')
def phone_roleplay():
    username = session.get('username')
    if not username:
        return redirect('/login')
    redirect_response = _require_pre_survey_completion(username)
    if redirect_response:
        return redirect_response
    return render_template("phoneRoleplay.html", back_to_dashboard_url=_module_back_url(username))


@app.route('/module_assessments')
def module_assessments():
    flash('Module pre/post assessments have been removed from this flow.', 'info')
    return redirect('/dashboard')


@app.route('/module_assessment/<module_name>/<phase>', methods=['GET', 'POST'])
def module_assessment(module_name, phase):

    flash('Module pre/post assessments have been removed from this flow.', 'info')
    return redirect('/dashboard')


@app.route('/logout')
def logout():
    lang = session.get('lang')
    session.clear()
    if lang in ('en', 'es', 'zh'):
        session['lang'] = lang
    flash(_('You have been logged out.'), 'info')
    return redirect('/login')


################################
# Assessment & Analytics Endpoints
################################
@app.route('/api/user_performance', methods=['GET'])
def api_user_performance():
    """
    Get overall performance summary for a user across all scenario types.
    """
    username = session.get('username')
    if not username:
        return jsonify({"success": False, "error": "Not authenticated"}), 401

    result = get_user_performance(username)
    if not result['success']:
        return jsonify(result), 500
    return jsonify(result)


@app.route('/api/module_progress', methods=['GET'])
def api_module_progress():
    """
    Get module completion progress for a user.
    """
    username = session.get('username')
    if not username:
        return jsonify({"success": False, "error": "Not authenticated"}), 401

    result = get_module_progress(username)
    if not result['success']:
        return jsonify(result), 500
    return jsonify(result)


@app.route('/api/attempt_history', methods=['GET'])
def api_attempt_history():
    """
    Get detailed history of scenario attempts for a user.
    """
    username = session.get('username')
    if not username:
        return jsonify({"success": False, "error": "Not authenticated"}), 401

    scenario_type = request.args.get('type')
    limit = request.args.get('limit', 20, type=int)

    result = get_attempt_history(username, scenario_type, limit)
    if not result['success']:
        return jsonify(result), 500
    return jsonify(result)


@app.route('/api/survey_comparison', methods=['GET'])
def api_survey_comparison():
    """
    Compare pre-survey and post-survey results for behavioral change assessment.
    """
    username = session.get('username')
    if not username:
        return jsonify({"success": False, "error": "Not authenticated"}), 401

    result = get_survey_comparison(username)
    if not result['success']:
        return jsonify(result), 500
    return jsonify(result)


@app.route('/api/learning_metrics', methods=['GET'])
def api_learning_metrics():
    """
    Comprehensive learning metrics including time spent, difficulty progression,
    and identified critical indicators.
    """
    username = session.get('username')
    if not username:
        return jsonify({"success": False, "error": "Not authenticated"}), 401

    result = get_learning_metrics(username)
    if not result['success']:
        return jsonify(result), 500
    return jsonify(result)


@app.route('/save_progress')
def save_progress():
    flash('Progress saved successfully!', 'success')
    return render_template("dashboard.html")

################################
#      Registration route
################################
@app.route('/register', methods=['POST'])
def register():
    username = request.form['username']
    password = request.form['password']
    email = request.form['email']
    phone = request.form['phone']
    address = request.form['address']

    success, message = user_registration(username, password, email, phone, address)
    if success:
        session['username'] = username
        return jsonify(success=True, message=message, redirect_url=url_for('pre_survey'))
    return jsonify(success=False, message=message)


################################
#      Logging in route
################################
@app.route('/login', methods=['POST'])
def login_post():
    usernameorEmail = request.form['username'].strip()
    password = request.form['password'].strip()

    valid, phone, canonical_username = verifying_login(usernameorEmail, password)

    if not valid:
        return jsonify({"success": False, "message": "Invalid username or password"})

    # Storing logged in user for session
    session["username"] = canonical_username

    if canonical_username == TEST_USER_USERNAME:
        return jsonify({
            "success": True,
            "otp_sent": False,
            "twilio_bypassed": True,
            "message": "Test user logged in without OTP"
        })

    if not phone.startswith("+"):
        phone = "+1" + phone

    try:
        send_otp(phone)
        return jsonify({"success": True, "otp_sent": True, "phone": phone})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

################################
#       Validation route
################################
@app.route('/check_username')
def check_username():
    username = request.args.get("username")

    if not username:
        return jsonify({"exists": False})

    with sqlite3.connect("silvershieldDatabase.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM users WHERE username = ?", (username,))
        exists = cursor.fetchone() is not None

    return jsonify({"exists": exists})

@app.route('/check_email')
def check_email():
    email = request.args.get("email")

    if not email:
        return jsonify({"exists": False})

    with sqlite3.connect("silvershieldDatabase.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM users WHERE email = ?", (email,))
        exists = cursor.fetchone() is not None

    return jsonify({"exists": exists})

@app.route('/send_otp', methods=['POST'])
def send_otp_route():
    phone = request.form['phone']

    if not phone.startswith("+"):
        phone = "+1" + phone

    try:
        send_otp(phone)
        return jsonify({"success": True, "message": "OTP sent"})
    except Exception as e:
        print("Error sending OTP", e)
        return jsonify({"success": False, "message": str(e)})

@app.route('/verify_otp', methods=['POST'])
def verify_otp_route():
    if session.get("username") == TEST_USER_USERNAME:
        return jsonify({"success": True, "message": "OTP bypassed for test user"})

    phone = request.form['phone']
    code = request.form['code']

    if not phone.startswith("+"):
        phone = "+1" + phone

    try:
        if verify_otp(phone, code):
            return jsonify({"success": True, "message": "OTP verified"})
        else:
            return jsonify({"success": False, "message": "OTP not verified"})
    except Exception as e:
        print("Error verifying OTP", e)
        return jsonify({"success": False, "message": str(e)})

##############################
# Phone Roleplay AI
##############################
@app.route("/generate-roleplay-line", methods=["POST"])
def generate_roleplay_line():
    data = request.get_json() or {}

    scenario_type = data.get("scenario_type")
    prompt_key = data.get("prompt_key")
    difficulty = int(data.get("difficulty", 1))

    print("roleplay line request:", scenario_type, prompt_key, difficulty)

    if not scenario_type or not prompt_key:
        return jsonify({"success": False, "error": "Missing fields"}), 400

    difficulty_text = {
        1: "Make the scam obvious and easy for beginners to detect.",
        2: "Make the scam somewhat believable but still noticeable.",
        3: "Make the scam convincing with subtle warning signs.",
        4: "Make the scam highly convincing with very subtle red flags."
    }.get(difficulty, "Make the scam realistic.")

    scenario_guidance = {
        "bank_fraud": "A caller pretends to be from a bank fraud department and tries to get account details or one-time codes.",
        "tech_support": "A caller pretends to be tech support and tries to get remote access or frighten the user into acting.",
        "grandparent": "A caller pretends to be a family member in urgent trouble and pressures the user to send money.",
        "government": "A caller pretends to be a government agency and uses threats or legal pressure to demand payment or personal information."
    }.get(scenario_type, "A suspicious scam phone call.")

    prompt_purposes = {
        "opening": "Generate the opening line of the scam call.",
        "ask_for_code": "Generate a follow-up line asking for sensitive verification information or a one-time code.",
        "push_for_account_number": "Generate a line pushing the victim to provide account details.",
        "urgency_if_call_later": "Generate a line using urgency when the victim says to call later.",
        "freeze_account_pressure": "Generate a line threatening account freezing or similar pressure.",
        "fake_name_and_department": "Generate a line where the scammer gives a fake professional identity to sound trustworthy.",
        "remote_access_request": "Generate a line asking the victim to download software or allow remote access.",
        "fake_system_alert": "Generate a line claiming the caller received a technical alert from the victim's device.",
        "family_emergency_opening": "Generate an opening line for a fake family emergency scam.",
        "family_pressure": "Generate a line pressuring the victim not to verify with others and to send money quickly.",
        "government_threat_opening": "Generate an opening line for a government impersonation scam.",
        "gift_card_payment": "Generate a line demanding immediate payment using gift cards or wire transfer.",
        "refuse_documentation": "Generate a line refusing to send official paperwork and pushing urgency."
    }

    purpose_text = prompt_purposes.get(prompt_key, "Generate a realistic scammer line.")

    output_language = get_llm_output_language()

    prompt = f"""
You are generating one short line of spoken dialogue for a cybersecurity training role-play.

Scenario type: {scenario_type}
Scenario guidance: {scenario_guidance}
Dialogue purpose: {purpose_text}
Difficulty level: {difficulty}
Difficulty guidance: {difficulty_text}

Rules:
- Output only the scammer's spoken dialogue.
- Keep it to 1 to 3 sentences.
- Make it realistic, clear, and suitable for older adults in a training setting.
- Write the dialogue in {output_language}.
- No markdown.
- No labels.
- No quotation marks around the whole answer.
- Do not include explicit violence or extreme threats.
"""

    headers = {
        "Authorization": f"Bearer {GROQ_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "openai/gpt-oss-20b",
        "reasoning_effort": "low",
    "include_reasoning": False,
    "max_completion_tokens": 2048,
        "messages": [{"role": "user", "content": prompt}]
    }

    resp = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers=headers,
        json=payload
    )

    result = resp.json()
    print("roleplay raw response:", result)

    if "choices" not in result:
        return jsonify({"success": False, "error": "Groq returned no content"}), 500

    line = result["choices"][0]["message"]["content"].strip()

    if line.startswith("```"):
        line = line.replace("```", "").strip()

    return jsonify({"success": True, "line": line})


################################
#   Phone Roleplay Assessment
################################
@app.route("/phone-roleplay/start-session", methods=["POST"])
def start_phone_roleplay_session():
    data = request.get_json() or {}

    username = session.get("username")
    if not username:
        return jsonify({"success": False, "error": "Not logged in"}), 401

    scenario_type = data.get("scenario_type")
    difficulty_level = int(data.get("difficulty_level", 1))

    if not scenario_type:
        return jsonify({"success": False, "error": "Missing scenario_type"}), 400

    started_at = datetime.now(timezone.utc).isoformat()

    with sqlite3.connect("silvershieldDatabase.db") as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO phone_roleplay_sessions
            (username, scenario_type, difficulty_level, started_at)
            VALUES (?, ?, ?, ?)
        """, (username, scenario_type, difficulty_level, started_at))
        conn.commit()
        session_id = cursor.lastrowid

        cursor.execute("""
            INSERT INTO phone_roleplay_results (session_id)
            VALUES (?)
        """, (session_id,))
        conn.commit()

    return jsonify({"success": True, "session_id": session_id})


@app.route("/phone-roleplay/log-event", methods=["POST"])
def log_phone_roleplay_event():
    data = request.get_json() or {}

    session_id = data.get("session_id")
    event_type = data.get("event_type")
    event_value = data.get("event_value", "")
    time_offset_seconds = data.get("time_offset_seconds", 0)

    if not session_id or not event_type:
        return jsonify({"success": False, "error": "Missing fields"}), 400

    timestamp = datetime.now(timezone.utc).isoformat()

    with sqlite3.connect("silvershieldDatabase.db") as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO phone_roleplay_events
            (session_id, event_type, event_value, timestamp, time_offset_seconds)
            VALUES (?, ?, ?, ?, ?)
        """, (session_id, event_type, event_value, timestamp, time_offset_seconds))
        conn.commit()

    return jsonify({"success": True})


@app.route("/phone-roleplay/finish-session", methods=["POST"])
def finish_phone_roleplay_session():
    data = request.get_json() or {}

    session_id = data.get("session_id")
    final_outcome = data.get("final_outcome", "")
    score = int(data.get("score", 0))
    attempt_count = int(data.get("attempt_count", 0))
    critical_indicators_found = int(data.get("critical_indicators_found", 0))
    critical_indicators_total = int(data.get("critical_indicators_total", 0))
    used_hint = int(data.get("used_hint", 0))
    behavior_pattern = data.get("behavior_pattern", "")
    feedback_shown = data.get("feedback_shown", "")

    if not session_id:
        return jsonify({"success": False, "error": "Missing session_id"}), 400

    ended_at = datetime.now(timezone.utc).isoformat()

    with sqlite3.connect("silvershieldDatabase.db") as conn:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT username, started_at FROM phone_roleplay_sessions
            WHERE id = ?
        """, (session_id,))
        row = cursor.fetchone()

        if not row:
            return jsonify({"success": False, "error": "Session not found"}), 404

        session_username = row[0]
        started_at = datetime.fromisoformat(row[1])
        ended_dt = datetime.fromisoformat(ended_at)
        total_time_seconds = (ended_dt - started_at).total_seconds()

        cursor.execute("""
            UPDATE phone_roleplay_sessions
            SET ended_at = ?, total_time_seconds = ?, final_outcome = ?, score = ?, completed = 1
            WHERE id = ?
        """, (ended_at, total_time_seconds, final_outcome, score, session_id))

        cursor.execute("""
            UPDATE phone_roleplay_results
            SET attempt_count = ?,
                critical_indicators_found = ?,
                critical_indicators_total = ?,
                used_hint = ?,
                behavior_pattern = ?,
                feedback_shown = ?
            WHERE session_id = ?
        """, (
            attempt_count,
            critical_indicators_found,
            critical_indicators_total,
            used_hint,
            behavior_pattern,
            feedback_shown,
            session_id
        ))

        conn.commit()

    if session_username:
        update_module_progress(session_username, "phone_roleplay")

    return jsonify({
        "success": True,
        "total_time_seconds": total_time_seconds
    })


@app.route("/phone-roleplay/progress-summary", methods=["GET"])
def phone_roleplay_progress_summary():
    username = session.get("username")
    if not username:
        return jsonify({"success": False, "error": "Not logged in"}), 401

    with sqlite3.connect("silvershieldDatabase.db") as conn:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT COUNT(*), COALESCE(AVG(score), 0), COALESCE(AVG(total_time_seconds), 0)
            FROM phone_roleplay_sessions
            WHERE username = ? AND completed = 1
        """, (username,))
        overall = cursor.fetchone()

        cursor.execute("""
            SELECT scenario_type, COUNT(*), COALESCE(AVG(score), 0)
            FROM phone_roleplay_sessions
            WHERE username = ? AND completed = 1
            GROUP BY scenario_type
        """, (username,))
        by_scenario = cursor.fetchall()

    return jsonify({
        "success": True,
        "overall": {
            "completed_sessions": overall[0],
            "average_score": round(overall[1], 2),
            "average_time_seconds": round(overall[2], 2)
        },
        "by_scenario": [
            {
                "scenario_type": row[0],
                "completed_sessions": row[1],
                "average_score": round(row[2], 2)
            }
            for row in by_scenario
        ]
    })
################################
#         Email AI
################################
def _clean_model_html(raw):
    candidate = (raw or "").strip()
    if candidate.startswith("```"):
        candidate = candidate.replace("```html", "").replace("```", "").strip()
    if len(candidate) < 10:
        return None
    return candidate


def _request_generated_email(prompt):
    headers = {
        "Authorization": f"Bearer {GROQ_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "openai/gpt-oss-20b",
        "reasoning_effort": "low",
        "include_reasoning": False,
        "max_completion_tokens": 2048,
        "messages": [{"role": "user", "content": prompt}]
    }
    resp = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers=headers,
        json=payload
    )
    groq_data = resp.json()
    if "choices" not in groq_data:
        return None
    return _clean_model_html(groq_data["choices"][0]["message"]["content"])


def _fallback_email_html(is_scam):
    if is_scam:
        return """
<b>From:</b> Account Security &lt;security-review@notice-check.com&gt;<br>
<b>To:</b> user@example.com<br>
<b>Subject:</b> Urgent sign-in review needed<br><br>
<hr><br>
<p style="font-family:Arial; font-size:15px; line-height:1.55;">We noticed unusual activity connected to your recent account use. Please review your sign-in details as soon as possible to avoid interruption.</p>
<p style="font-family:Arial; font-size:15px; line-height:1.55;">Use the secure verification page here: <a href="https://account-review-notice.com">Verify now</a></p>
""".strip()
    return """
<b>From:</b> Community Services &lt;updates@community-center.org&gt;<br>
<b>To:</b> user@example.com<br>
<b>Subject:</b> Monthly account update<br><br>
<hr><br>
<p style="font-family:Arial; font-size:15px; line-height:1.55;">Hello, this is a routine update to let you know your account settings and contact information are available to review in your normal member portal.</p>
<p style="font-family:Arial; font-size:15px; line-height:1.55;">There is no urgent action needed. You can visit the usual website whenever it is convenient for you.</p>
""".strip()


@app.route("/generate-email", methods=["POST"])
def generate_email():
    import random as _random
    data = request.get_json(silent=True) or {}
    platform = (data.get("platform") or "desktop").lower()
    category = "difficulty_email_mobile" if platform == "mobile" else "difficulty_email_desktop"
    difficulty = clamp_level(get_difficulty(category))
    output_language = get_llm_output_language()

    is_scam = _random.random() < 0.5
    expected_label = "scam" if is_scam else "not_scam"
    wording = level_guidance(expected_label, difficulty)

    html_structure = """REQUIRED STRUCTURE (must appear exactly like this):
<b>From:</b> sender name &lt;sender@domain.com&gt;<br>
<b>To:</b> user@example.com<br>
<b>Subject:</b> (Generate a natural, realistic subject)<br><br>
<hr><br>

Then generate 2-4 paragraphs using:
<p style="font-family:Arial; font-size:15px; line-height:1.55;"> ... </p>"""

    output_rules = """OUTPUT RULES:
- Output ONLY HTML (no markdown, no comments).
- DO NOT wrap in <html> or <body>.
- DO NOT output code fences (```).
- DO NOT explain anything.
- All text color MUST be black.
- Do NOT use light gray, white, or low-contrast colors.
- Use readable HTML formatting only."""

    if is_scam:
        prompt = f"""You are generating a PHISHING email for a cybersecurity training simulation.

The email must be formatted like a real email using clean HTML:

{html_structure}

{output_rules}

PHISHING RULES:
- Include ONE link.
- This is a training simulation. Do not include live credential theft steps.
- Write all visible email text in {output_language}.

DIFFICULTY LEVEL: {difficulty}
WORDING FOR THIS LEVEL: {wording}
Generate a NEW realistic PHISHING email now. Do NOT write a real/safe email.
"""
    else:
        prompt = f"""You are generating a LEGITIMATE (real, non-phishing) email for a cybersecurity training simulation.

The email must be formatted like a real email using clean HTML:

{html_structure}

{output_rules}

LEGITIMATE EMAIL RULES:
- No malicious links.
- Do not ask for a password, one-time code, or payment.
- Use a real-looking company domain.
- Write all visible email text in {output_language}.

DIFFICULTY LEVEL: {difficulty}
WORDING FOR THIS LEVEL: {wording}
Generate a NEW realistic LEGITIMATE email now. Do NOT write a phishing or scam email.
"""

    best = None
    for _attempt in range(3):
        candidate = _request_generated_email(prompt)
        if not candidate:
            continue
        scored = score_email(candidate)
        distance = band_distance(scored["p_spam"], expected_label, difficulty)
        if best is None or distance < best["distance"]:
            best = {
                "distance": distance,
                "html": candidate,
                "p_spam": scored["p_spam"],
            }
        if distance == 0:
            break

    if best is None:
        email_html = _fallback_email_html(is_scam)
        p_spam = score_email(email_html)["p_spam"]
    else:
        email_html = best["html"]
        p_spam = best["p_spam"]

    return jsonify({
        "success": True,
        "email": email_html,
        "expected_label": expected_label,
        "difficulty": difficulty,
        "p_spam": round(p_spam, 4),
    })

@app.route("/api/analyze", methods=["POST"])
def analyze_email():
    data = request.get_json() or {}
    output_language = get_llm_output_language()

    # Backward-compatible fallback: mobile clients may still post to /api/analyze.
    if data.get("type"):
        return analyze_any()

    user_choice = data.get("user_choice")
    message = data.get("message")
    expected_label = (data.get("expected_label") or "").strip().lower()
    # Normalize: "fake" -> "scam", "real" -> "not_scam"
    if expected_label == "fake":
        expected_label = "scam"
    elif expected_label == "real":
        expected_label = "not_scam"
    if expected_label not in ("scam", "not_scam"):
        expected_label = ""

    if not user_choice or not message:
        return jsonify({"success": False, "error": "Missing fields"}), 400

    # Normalize user_choice to scam/not_scam for comparison
    normalized_choice = user_choice.strip().lower()
    if normalized_choice == "fake":
        normalized_choice = "scam"
    elif normalized_choice == "real":
        normalized_choice = "not_scam"

    difficulty = get_difficulty("difficulty_email_desktop")

    if expected_label:
        # Deterministic correctness — AI explains why
        is_correct = (normalized_choice == expected_label)
        correct_answer_label = "PHISHING" if expected_label == "scam" else "LEGITIMATE"
        user_answer_label = "FAKE (phishing)" if normalized_choice == "scam" else "REAL (legitimate)"
        explain_prompt = f"""You are a cybersecurity trainer giving feedback on an email classification exercise.

The trainee was shown this email:
--- EMAIL START ---
{message}
--- EMAIL END ---

The correct classification is: {correct_answer_label}
The trainee answered: {user_answer_label} — which is {'CORRECT' if is_correct else 'INCORRECT'}.

Write a 1-2 sentence explanation of WHY this email is {correct_answer_label}, pointing to specific clues in the content.
Then list 2-3 short clue strings.
Write feedback and clues in {output_language}.

Respond ONLY with valid JSON, no markdown:
{{"correct": {'true' if is_correct else 'false'}, "feedback": "explanation here", "clues": ["clue 1", "clue 2"]}}"""
        headers = {"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"}
        payload = {"model": "openai/gpt-oss-20b", "reasoning_effort": "low", "include_reasoning": False, "max_completion_tokens": 2048, "messages": [{"role": "user", "content": explain_prompt}]}
        try:
            groq_resp = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload)
            raw = groq_resp.json()["choices"][0]["message"]["content"].strip()
            if raw.startswith("```"):
                raw = raw.replace("```json", "").replace("```", "").strip()
            parsed = json.loads(raw)
            parsed["correct"] = is_correct  # always enforce deterministic result
        except Exception:
            parsed = {"correct": is_correct, "feedback": f"This email is {correct_answer_label.lower()}.", "clues": []}
    else:
        prompt = f"""
You are analyzing whether an email is REAL (legitimate) or FAKE (phishing).

Here is the email:

--- EMAIL START ---
{message}
--- EMAIL END ---

The user selected: {user_choice.upper()}
Write feedback and clues in {output_language}.

You MUST respond with ONLY a JSON object. Use double quotes. No markdown.
{{"correct": true or false, "feedback": "One sentence.", "clues": ["clue1"]}}
"""

        headers = {
            "Authorization": f"Bearer {GROQ_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "openai/gpt-oss-20b", "reasoning_effort": "low", "include_reasoning": False, "max_completion_tokens": 2048,
            "messages": [{"role": "user", "content": prompt}]
        }
        groq_resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers, json=payload
        )
        groq_data = groq_resp.json()
        if "choices" not in groq_data:
            return jsonify({"success": False, "error": "Groq API error"}), 500
        raw = groq_data["choices"][0]["message"]["content"].strip()
        if raw.startswith("```"):
            raw = raw.replace("```json", "").replace("```", "").strip()
        try:
            parsed = json.loads(raw)
        except Exception:
            parsed = {"correct": False, "feedback": "Could not parse AI response.", "clues": []}

    # Apply difficulty update
    is_correct = parsed.get("correct", False)
    if is_correct:
        set_difficulty("difficulty_email_desktop", difficulty + 1)
    else:
        set_difficulty("difficulty_email_desktop", 1)

    username = session.get('username')
    if username:
        correct_answer = user_choice if is_correct else ("fake" if user_choice == "real" else "real")
        time_spent = request.get_json().get("time_spent_seconds")
        indicators_found = parsed.get("clues", []) if is_correct else []
        log_scenario_attempt(
            username,
            "email",
            "desktop",
            user_choice,
            correct_answer,
            is_correct,
            difficulty,
            json.dumps(parsed),
            duration_seconds=time_spent,
            message=message,
            indicators_found=indicators_found
        )
        update_module_progress(username, "email_desktop")

    return jsonify({
        "success": True,
        "feedback": parsed,
        "difficulty_now": get_difficulty("difficulty_email_desktop")
    })

################################
#
# Desktop Internet AI
#
#################################
@app.route("/api/generate_sites", methods=["POST"])
def generate_sites():
    import random

    data = request.get_json(silent=True) or {}
    mode = (data.get("mode") or "list").lower()
    query = (data.get("query") or "security alerts").strip()
    difficulty = get_difficulty("difficulty_internet_desktop")
    output_language = get_llm_output_language()

    headers = {
        "Authorization": f"Bearer {GROQ_KEY}",
        "Content-Type": "application/json"
    }

    def infer_brand_details(search_query):
        known_brands = {
            "amazon": ("Amazon", "amazon.com"),
            "chase": ("Chase", "chase.com"),
            "paypal": ("PayPal", "paypal.com"),
            "usps": ("USPS", "usps.com"),
            "microsoft": ("Microsoft", "microsoft.com"),
            "apple": ("Apple", "apple.com"),
            "google": ("Google", "google.com"),
            "bank": ("Your Bank", "securebank.example.com"),
        }
        lowered = search_query.lower()
        for key, details in known_brands.items():
            if key in lowered:
                return details

        cleaned = "".join(ch for ch in search_query if ch.isalnum() or ch.isspace()).strip() or "Online Safety"
        slug = "-".join(cleaned.lower().split()) or "online-safety"
        return cleaned.title(), f"{slug}.example.com"

    def safe_extract_json(raw_text):
        raw_text = (raw_text or "").strip()
        if raw_text.startswith("```"):
            raw_text = raw_text.replace("```json", "").replace("```", "").strip()
        try:
            return json.loads(raw_text)
        except Exception:
            return None

    def normalize_result(parsed, fallback):
        if not isinstance(parsed, dict):
            return fallback
        return {
            "title": (parsed.get("title") or parsed.get("headline") or fallback["title"]).strip(),
            "url": (parsed.get("url") or parsed.get("link") or fallback["url"]).strip(),
            "description": (parsed.get("description") or parsed.get("snippet") or parsed.get("text") or fallback["description"]).strip(),
            "site_type": parsed.get("site_type") if parsed.get("site_type") in ("legit", "phishing") else fallback["site_type"],
            "is_sponsored": bool(parsed.get("is_sponsored", fallback.get("is_sponsored", False))),
        }

    def generate_one(prompt_text, fallback):
        for _attempt in range(2):
            try:
                payload = {
                    "model": "openai/gpt-oss-20b", "reasoning_effort": "low", "include_reasoning": False, "max_completion_tokens": 2048,
                    "messages": [{"role": "user", "content": prompt_text}]
                }
                response = requests.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=20
                )
                raw_response = response.json()["choices"][0]["message"]["content"]
                if is_model_refusal(raw_response):
                    return fallback
                parsed = safe_extract_json(raw_response)
                if parsed:
                    return normalize_result(parsed, fallback)
            except Exception:
                continue
        return fallback

    brand_name, legit_domain = infer_brand_details(query)
    phishing_domain = f"{brand_name.lower().replace(' ', '')}-security-check.com"

    if mode == "list":
        sponsored_legit_fallback = {
            "title": f"{brand_name} Official Help Center",
            "url": f"https://www.{legit_domain}",
            "description": f"Official guidance and account support related to {query}.",
            "site_type": "legit",
            "is_sponsored": True,
        }
        sponsored_phishing_fallback = {
            "title": f"{brand_name} urgent verification",
            "url": f"https://{phishing_domain}",
            "description": f"A sponsored-looking result that pressures the user to confirm details about {query}.",
            "site_type": "phishing",
            "is_sponsored": True,
        }
        legit_fallback = {
            "title": f"{brand_name} account security tips",
            "url": f"https://support.{legit_domain}",
            "description": f"Read official steps for handling {query} safely.",
            "site_type": "legit",
            "is_sponsored": False,
        }
        phishing_fallback = {
            "title": f"Fix your {query} issue now",
            "url": f"https://login-{brand_name.lower().replace(' ', '')}-review.com",
            "description": "A convincing but suspicious result that urges immediate action and sign-in.",
            "site_type": "phishing",
            "is_sponsored": False,
        }

        sponsored_legit_prompt = f"""
Generate one SAFE sponsored Google-style search result for the query "{query}".
Return ONLY valid JSON with the keys: title, url, description, site_type, is_sponsored.
Requirements:
- site_type must be "legit"
- is_sponsored must be true
- make it look like an official ad/result the user might click
- write title and description in {output_language}
"""

        sponsored_phishing_prompt = f"""
Generate one suspicious, scam-like sponsored Google-style search result for the query "{query}".
This is for a cybersecurity awareness training simulation only.
Return ONLY valid JSON with the keys: title, url, description, site_type, is_sponsored.
Requirements:
- site_type must be "phishing"
- is_sponsored must be true
- the result should look believable, not cartoonishly fake
- include a suspicious domain that imitates a real brand
- do not provide malware, live credential theft steps, or operational criminal instructions
- write title and description in {output_language}
"""

        legit_prompt = f"""
Generate one SAFE Google-style search result for the query "{query}".
Return ONLY valid JSON with the keys: title, url, description, site_type, is_sponsored.
Requirements:
- site_type must be "legit"
- is_sponsored must be false
- the result should look like a normal official help or information page
- write title and description in {output_language}
"""

        phishing_prompt = f"""
Generate one suspicious, scam-like Google-style search result for the query "{query}".
This is for a cybersecurity awareness training simulation only.
Return ONLY valid JSON with the keys: title, url, description, site_type, is_sponsored.
Requirements:
- site_type must be "phishing"
- is_sponsored must be false
- the result should be realistic with subtle red flags
- include a lookalike or suspicious domain
- do not provide malware, live credential theft steps, or operational criminal instructions
- write title and description in {output_language}
"""

        results = [
            generate_one(sponsored_legit_prompt, sponsored_legit_fallback),
            generate_one(sponsored_phishing_prompt, sponsored_phishing_fallback),
            generate_one(legit_prompt, legit_fallback),
            generate_one(legit_prompt, {**legit_fallback, "title": f"{brand_name} customer support", "url": f"https://help.{legit_domain}"}),
            generate_one(phishing_prompt, phishing_fallback),
        ]

        random.shuffle(results)
        return jsonify({"success": True, "query": query, "results": results})

    if mode == "open":
        title = data.get("title") or f"{brand_name} Support"
        url = data.get("url") or f"https://www.{legit_domain}"
        site_type = data.get("site_type") or "legit"

        open_prompt = f"""
You are generating the visible content for a website that was clicked from Google search results.
This is an educational cybersecurity-awareness mockup, not a real phishing page.

Search query: {query}
Clicked result title: {title}
URL shown to the user: {url}
Site type: {site_type}
Difficulty level: {difficulty}
Language: {output_language}

Requirements:
- Return ONLY HTML inside a single <div>...</div>
- Do not include markdown, scripts, or comments
- Use readable black text on a white background
- If the site is phishing, make it a safe simulated training page with warning signs and placeholder fields only
- If the site is legitimate, make it look helpful, normal, and trustworthy
- Do not include malware, exploit steps, or anything operationally harmful
"""

        html = None
        try:
            payload = {
                "model": "openai/gpt-oss-20b", "reasoning_effort": "low", "include_reasoning": False, "max_completion_tokens": 2048,
                "messages": [{"role": "user", "content": open_prompt}]
            }
            response = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=20
            )
            html = response.json()["choices"][0]["message"]["content"].strip()
            if html.startswith("```"):
                html = html.replace("```html", "").replace("```", "").strip()
            if is_model_refusal(html):
                html = None
        except Exception:
            html = None

        if not html:
            if site_type == "phishing":
                html = f"""
<div style=\"font-family:Arial,sans-serif;color:#000;\">
  <h2>{title}</h2>
  <p><strong>Urgent account review required</strong></p>
  <p>We noticed unusual activity connected to <strong>{query}</strong>. Please confirm your login details immediately to avoid disruption.</p>
  <form>
    <label>Email or username</label><br>
    <input style=\"width:100%;padding:8px;margin:6px 0 12px;\" placeholder=\"Enter your account\"><br>
    <label>Password</label><br>
    <input style=\"width:100%;padding:8px;margin:6px 0 12px;\" type=\"password\" placeholder=\"Enter your password\"><br>
    <button style=\"padding:10px 16px;background:#1a73e8;color:#fff;border:none;border-radius:6px;\">Verify now</button>
  </form>
</div>
"""
            else:
                html = f"""
<div style=\"font-family:Arial,sans-serif;color:#000;\">
  <h2>{title}</h2>
  <p>Welcome to the official help page for <strong>{query}</strong>.</p>
  <ul>
    <li>Review recent account activity</li>
    <li>Read safety and privacy guidance</li>
    <li>Contact verified support if needed</li>
  </ul>
  <p>This page provides general information and does not ask for urgent credentials or payments.</p>
</div>
"""

        return jsonify({
            "success": True,
            "query": query,
            "html": html,
            "site_type": site_type,
            "ai_context": html,
            "difficulty": difficulty
        })

    return jsonify({"success": False, "error": "Invalid mode"}), 400


@app.route("/api/analyze_website", methods=["POST"])
def analyze_website():
    data = request.get_json()
    output_language = get_llm_output_language()

    user_choice = data.get("user_choice")
    html = data.get("ai_context")
    site_type = data.get("site_type")

    if not user_choice or not html or not site_type:
        return jsonify({"success": False, "error": "Missing fields"}), 400

    difficulty = get_difficulty("difficulty_internet_desktop")

    # Deterministic scoring: site_type is ground truth set at generation time.
    # "legit" -> user must pick "real"; "phishing" -> user must pick "fake".
    choice = user_choice.strip().lower()
    if site_type == "phishing":
        is_correct = choice in ("fake", "scam")
        correct_answer_label = "PHISHING"
    else:
        is_correct = choice in ("real", "legit", "not_scam")
        correct_answer_label = "LEGITIMATE"
    user_answer_label = "FAKE (phishing)" if choice in ("fake", "scam") else "REAL (legitimate)"

    explain_prompt = f"""You are a cybersecurity trainer giving feedback on a website classification exercise.

The trainee was shown this website HTML:
--- SITE START ---
{html[:2000]}
--- SITE END ---

The correct classification is: {correct_answer_label}
The trainee answered: {user_answer_label} — which is {'CORRECT' if is_correct else 'INCORRECT'}.

Write a 1-2 sentence explanation of WHY this site is {correct_answer_label}, pointing to specific clues in the content.
Then list 2-3 short clue strings.
Write explanation and clues in {output_language}.

Respond ONLY with valid JSON, no markdown:
{{"correct": {'true' if is_correct else 'false'}, "explanation": "explanation here", "clues": ["clue 1", "clue 2"]}}"""
    headers_ai = {"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"}
    payload_ai = {"model": "openai/gpt-oss-20b", "reasoning_effort": "low", "include_reasoning": False, "max_completion_tokens": 2048, "messages": [{"role": "user", "content": explain_prompt}]}
    try:
        resp_ai = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers_ai, json=payload_ai)
        raw_ai = resp_ai.json()["choices"][0]["message"]["content"].strip()
        if raw_ai.startswith("```"):
            raw_ai = raw_ai.replace("```json", "").replace("```", "").strip()
        parsed = json.loads(raw_ai)
        parsed["correct"] = is_correct  # always enforce deterministic result
    except Exception:
        parsed = {"correct": is_correct, "explanation": f"This site is {correct_answer_label.lower()}.", "clues": []}
    if is_correct:
        set_difficulty("difficulty_internet_desktop", difficulty + 1)
    else:
        set_difficulty("difficulty_internet_desktop", 1)

    username = session.get('username')
    if username:
        time_spent = request.get_json().get("time_spent_seconds")
        ai_context = request.get_json().get("ai_context")
        indicators_found = parsed.get("clues", []) if is_correct else []
        log_scenario_attempt(
            username,
            "internet",
            "desktop",
            user_choice,
            site_type,
            is_correct,
            difficulty,
            json.dumps(parsed),
            duration_seconds=time_spent,
            message=ai_context,
            indicators_found=indicators_found
        )
        update_module_progress(username, "internet_desktop")

    return jsonify({
        "success": True,
        "feedback": parsed,
        "difficulty_now": get_difficulty("difficulty_internet_desktop")
    })

################################
#         Mobile SMS
################################
@app.route("/generate-sms", methods=["POST"])
def generate_sms():
    """
    Generates an SMS scam or safe message (randomly chosen).
    Returns JSON.
    """
    import random as _random
    difficulty = get_difficulty("difficulty_sms_mobile")
    output_language = get_llm_output_language()
    is_scam = _random.random() < 0.5
    expected_label = "scam" if is_scam else "not_scam"

    scam_difficulty_text = {
        1: "Make the scam VERY obvious: bad grammar, weird link, over-the-top urgency.",
        2: "Scam is noticeable but not too obvious. Some strange phrasing or link.",
        3: "Mostly convincing SMS with subtle red flags only.",
        4: "Extremely convincing SMS; only trained users notice the clues.",
    }[difficulty]

    safe_difficulty_text = {
        1: "A clearly normal message — no urgency, proper grammar, recognizable brand.",
        2: "A mostly normal message but with a generic tone that could be suspicious.",
        3: "A realistic legitimate notification that looks almost identical to real brand messages.",
        4: "A perfectly legitimate message indistinguishable from real bank/brand texts.",
    }[difficulty]

    theme = request.json.get("theme", "bank / package / delivery / login security")

    if is_scam:
        prompt = f"""
    You generate a REALISTIC PHISHING TEXT MESSAGE. It must look like real scam texts people receive.

    RULES:
    - Output ONLY valid JSON.
    - NO markdown.
    - NO commentary before or after.
    - NO explanations.
    - ONLY the JSON object.
    - Use double quotes.
    - MUST follow this structure exactly:

    {{
      "number": "+1 555 123 4567",
      "text": "SMS message body...",
      "time": "10:52 AM",
      "clues": ["scam clue 1", "scam clue 2"]
    }}

    REALISM REQUIREMENTS:
    - Must imitate real scam SMS patterns.
    - Use typo-squatted brands (Amzon, PayPall, US Postal Servce).
    - Include urgency, threats, refunds, delivery issues, bank locks.
    - Include a suspicious, shortened, or weird URL.
    - NEVER mention SilverShield.
    - Write the SMS text and clues in {output_language}.

    TASK:
    Create **one** SCAM SMS message.
    Difficulty = {difficulty}
    Style = {scam_difficulty_text}
    Theme = {theme}

    FINAL RULE:
    Respond with ONLY the JSON object. NOTHING else.
    """
    else:
        prompt = f"""
    You generate a REALISTIC LEGITIMATE TEXT MESSAGE from a real company or service.

    RULES:
    - Output ONLY valid JSON.
    - NO markdown.
    - NO commentary before or after.
    - NO explanations.
    - ONLY the JSON object.
    - Use double quotes.
    - MUST follow this structure exactly:

    {{
      "number": "+1 555 123 4567",
      "text": "SMS message body...",
      "time": "10:52 AM",
      "clues": []
    }}

    REALISM REQUIREMENTS:
    - Must look like a real notification from a well-known brand (Amazon, Chase Bank, UPS, etc.).
    - Use correct brand names and professional tone.
    - Include a legitimate-looking URL from the real brand domain.
    - NO urgency or threats. Just a routine update, delivery notification, or account alert.
    - NEVER mention SilverShield.
    - Write the SMS text in {output_language}.

    TASK:
    Create **one** LEGITIMATE SMS message.
    Difficulty = {difficulty}
    Style = {safe_difficulty_text}
    Theme = {theme}

    FINAL RULE:
    Respond with ONLY the JSON object. NOTHING else.
    """

    headers = {
        "Authorization": f"Bearer {GROQ_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "openai/gpt-oss-20b", "reasoning_effort": "low", "include_reasoning": False, "max_completion_tokens": 2048,
        "messages": [{"role": "user", "content": prompt}]
    }

    r = requests.post("https://api.groq.com/openai/v1/chat/completions",
                      headers=headers, json=payload)

    data = r.json()

    if "choices" not in data:
        fallback_sms = {
            "number": "+1 555 123 4567" if is_scam else "+1 800 555 0100",
            "text": (
                "Bank notice: unusual activity detected. Confirm your account now at secure-review-alert.com"
                if is_scam else
                "Reminder: your scheduled service update is now available in your normal account portal. No urgent action is needed."
            ),
            "time": "10:52 AM",
            "clues": ["Urgent pressure", "Suspicious link"] if is_scam else []
        }
        return jsonify({
            "success": True,
            "difficulty": difficulty,
            "expected_label": expected_label,
            "sms": fallback_sms
        })

    raw = data["choices"][0]["message"]["content"].strip()

    # Handle markdown
    if raw.startswith("```"):
        raw = raw.replace("```json", "").replace("```", "").strip()

    # Cut trailing noise
    last = raw.rfind("}")
    if last != -1:
        raw = raw[:last+1]

    try:
        sms_obj = json.loads(raw)
    except Exception:
        return jsonify({
            "success": True,
            "difficulty": difficulty,
            "sms": {
                "number": "+1 000 000 0000",
                "text": "Failed to generate message. Try again.",
                "time": "12:00 PM",
                "clues": []
            }
        })

    return jsonify({
        "success": True,
        "difficulty": difficulty,
        "expected_label": expected_label,
        "sms": sms_obj
    })


################################
#       Mobile Call
################################
@app.route("/generate-call", methods=["POST"])
def generate_call():
    import random as _random
    difficulty = get_difficulty("difficulty_call_mobile")
    output_language = get_llm_output_language()
    is_scam = _random.random() < 0.5
    expected_label = "scam" if is_scam else "not_scam"

    scam_difficulty_text = {
        1: "Obvious scam: caller is clearly suspicious.",
        2: "Moderately subtle scam: some clues remain.",
        3: "Convincing scam: only subtle clues.",
        4: "Extremely convincing scam: only experts notice the red flags.",
    }[difficulty]

    safe_difficulty_text = {
        1: "Clearly legitimate: professional tone, no pressure, easy to identify as real.",
        2: "Legitimate but with a generic script that could raise mild doubt.",
        3: "Realistic legitimate call with subtle details that confirm it's real.",
        4: "Perfect legitimate call — indistinguishable from a real company rep.",
    }[difficulty]

    theme = request.json.get("theme", "government agency or tech support")

    if is_scam:
        prompt = f"""
You are generating a REALISTIC PHONE SCAM CALL TRANSCRIPT.

STRICT RULES:
- Output ONLY VALID JSON.
- No markdown.
- No text outside the JSON.
- JSON MUST follow:

{{
  "number": "(555) 123-9876",
  "caller_name": "string",
  "transcript": "Full transcript with \\n line breaks.",
  "clues": ["clue1", "clue2"]
}}

TASK:
Difficulty={difficulty}
{scam_difficulty_text}
Theme={theme}
Write caller_name, transcript, and clues in {output_language}.
"""
    else:
        prompt = f"""
You are generating a REALISTIC LEGITIMATE PHONE CALL TRANSCRIPT from a real company or service.

STRICT RULES:
- Output ONLY VALID JSON.
- No markdown.
- No text outside the JSON.
- JSON MUST follow:

{{
  "number": "(800) 123-4567",
  "caller_name": "string",
  "transcript": "Full transcript with \\n line breaks.",
  "clues": []
}}

REQUIREMENTS:
- Caller represents a real well-known company (e.g. Chase Bank, UPS, Amazon).
- Professional tone. No threats, no urgency, no requests for passwords or gift cards.
- Routine purpose: appointment reminder, delivery update, account notification.
- NEVER mention SilverShield.

TASK:
Difficulty={difficulty}
{safe_difficulty_text}
Theme={theme}
Write caller_name and transcript in {output_language}.
"""

    headers = {
        "Authorization": f"Bearer {GROQ_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "openai/gpt-oss-20b", "reasoning_effort": "low", "include_reasoning": False, "max_completion_tokens": 2048,
        "messages": [{"role": "user", "content": prompt}]
    }

    r = requests.post("https://api.groq.com/openai/v1/chat/completions",
                      headers=headers, json=payload)
    data = r.json()

    if "choices" not in data:
        fallback_call = {
            "number": "(555) 123-9876" if is_scam else "(800) 123-4567",
            "caller_name": "Account Security Desk" if is_scam else "Customer Support",
            "transcript": (
                "Hello, we detected suspicious activity on your account and need you to confirm your information immediately. Please stay on the line and verify your details now."
                if is_scam else
                "Hello, this is a routine courtesy call to let you know your account information is available in your usual support portal. There is no urgent action required today."
            ),
            "clues": ["Urgency", "Requests quick action"] if is_scam else []
        }
        return jsonify({
            "success": True,
            "difficulty": difficulty,
            "expected_label": expected_label,
            "call": fallback_call
        })

    raw = data["choices"][0]["message"]["content"].strip()

    if raw.startswith("```"):
        raw = raw.replace("```json", "").replace("```", "").strip()

    last = raw.rfind("}")
    raw = raw[:last+1]

    try:
        call_obj = json.loads(raw)
    except Exception:
        call_obj = {
            "number": "(555) 123-9876" if is_scam else "(800) 123-4567",
            "caller_name": "Account Security Desk" if is_scam else "Customer Support",
            "transcript": (
                "Hello, we detected suspicious activity on your account and need you to confirm your information immediately. Please stay on the line and verify your details now."
                if is_scam else
                "Hello, this is a routine courtesy call to let you know your account information is available in your usual support portal. There is no urgent action required today."
            ),
            "clues": ["Urgency", "Requests quick action"] if is_scam else []
        }

    return jsonify({
        "success": True,
        "difficulty": difficulty,
        "expected_label": expected_label,
        "call": call_obj
    })


################################
#        Mobile Web
################################
@app.route("/generate-web", methods=["POST"])
def generate_web():
    import random as _random

    data = request.get_json(silent=True) or {}
    mode = (data.get("mode") or "search").lower()
    difficulty = get_difficulty("difficulty_web_mobile")
    output_language = get_llm_output_language()
    query = (data.get("query") or data.get("theme") or "bank account security tips").strip()

    headers = {"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"}

    def safe_extract_json(raw_text):
        raw_text = (raw_text or "").strip()
        if raw_text.startswith("```"):
            raw_text = raw_text.replace("```json", "").replace("```", "").strip()
        try:
            return json.loads(raw_text)
        except Exception:
            return None

    def normalize_item(item, fallback_type="legit"):
        if not isinstance(item, dict):
            return None

        title = (item.get("title") or item.get("headline") or item.get("name") or "").strip()
        url = (item.get("url") or item.get("link") or item.get("domain") or "").strip()
        snippet = (item.get("snippet") or item.get("description") or item.get("text") or "").strip()
        site_type = item.get("site_type") if item.get("site_type") in ("legit", "phishing") else fallback_type

        if not title and not url and not snippet:
            return None

        return {
            "title": title,
            "url": url,
            "snippet": snippet,
            "site_type": site_type,
        }

    def build_fallback_items():
        slug = "-".join(query.lower().split()) or "security-tips"
        ads = [
            {
                "title": f"Official help for {query}",
                "url": f"https://www.{slug}.example.com",
                "snippet": f"Review the official information related to {query}.",
                "site_type": "legit",
            },
            {
                "title": f"Fix {query} immediately",
                "url": f"https://{slug}-verify-now.com",
                "snippet": "An urgent-looking ad asking you to confirm details right away.",
                "site_type": "phishing",
            },
        ]
        results = [
            {
                "title": f"What to know about {query}",
                "url": f"https://support.{slug}.example.com",
                "snippet": "Read practical safety guidance from an official-looking help center.",
                "site_type": "legit",
            },
            {
                "title": f"{query.title()} account verification",
                "url": f"https://login-{slug}-review.com",
                "snippet": "A believable but suspicious page asking you to sign in quickly.",
                "site_type": "phishing",
            },
            {
                "title": f"{query.title()} customer support",
                "url": f"https://www.{slug}.support.example.com",
                "snippet": "Contact details and FAQs for the topic you searched.",
                "site_type": "legit",
            },
            {
                "title": f"{query.title()} alerts and updates",
                "url": f"https://alerts-{slug}.net",
                "snippet": "A vague result using urgency and generic warnings to pressure the user.",
                "site_type": "phishing",
            },
            {
                "title": f"How to stay safe online with {query}",
                "url": "https://staysafeonline.org",
                "snippet": "General cybersecurity advice presented in a calm, educational tone.",
                "site_type": "legit",
            },
            {
                "title": f"Report suspicious {query} messages",
                "url": "https://consumer.ftc.gov",
                "snippet": "A legitimate public information page about scams and fraud reporting.",
                "site_type": "legit",
            },
        ]
        return ads, results

    if mode == "open":
        title = data.get("title") or query.title()
        url = data.get("url") or "https://example.com"
        site_type = data.get("site_type") or "legit"

        prompt = f"""
Generate the main visible content of a mobile-friendly webpage that a user clicked from Google search results.
This is an educational cybersecurity-awareness mockup, not a real phishing page.
Search query: {query}
Page title: {title}
URL: {url}
Site type: {site_type}
Difficulty level: {difficulty}
Language: {output_language}

Return ONLY HTML inside a single <div>...</div>.
Make the site easy to inspect for trust signals and warning signs.
Use safe placeholder content only and do not include operationally harmful instructions.
"""

        html = None
        try:
            payload = {
                "model": "openai/gpt-oss-20b", "reasoning_effort": "low", "include_reasoning": False, "max_completion_tokens": 2048,
                "messages": [{"role": "user", "content": prompt}]
            }
            response = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=20
            )
            html = response.json()["choices"][0]["message"]["content"].strip()
            if html.startswith("```"):
                html = html.replace("```html", "").replace("```", "").strip()
            if is_model_refusal(html):
                html = None
        except Exception:
            html = None

        if not html:
            if site_type == "phishing":
                html = f"""
<div style=\"font-family:Arial,sans-serif;color:#000;\">
  <h2>{title}</h2>
  <p><strong>Security check required</strong></p>
  <p>To continue with <strong>{query}</strong>, confirm your account information now.</p>
  <input style=\"width:100%;padding:8px;margin:8px 0;\" placeholder=\"Username or email\">
  <input style=\"width:100%;padding:8px;margin:8px 0;\" placeholder=\"Password\" type=\"password\">
  <button style=\"padding:10px 14px;background:#1a73e8;color:#fff;border:none;border-radius:6px;\">Sign in</button>
</div>
"""
            else:
                html = f"""
<div style=\"font-family:Arial,sans-serif;color:#000;\">
  <h2>{title}</h2>
  <p>This is an informational page related to <strong>{query}</strong>.</p>
  <ul>
    <li>Review your settings and safety tips</li>
    <li>Read official guidance</li>
    <li>Use verified support channels if needed</li>
  </ul>
</div>
"""

        return jsonify({
            "success": True,
            "difficulty": difficulty,
            "query": query,
            "html": html,
            "site_type": site_type
        })

    prompt = f"""
Generate realistic Google-style mobile search results for the user query: "{query}".
Return ONLY valid JSON with these top-level keys: ads, results, pagination, clues.
Requirements:
- include exactly 2 ads and exactly 6 results
- each item must contain: title, url, snippet, site_type
- mix legitimate and phishing results so the user has to inspect carefully
- keep phishing results believable, not cartoonishly fake
- write all visible text in {output_language}
"""

    web_obj = None
    try:
        payload = {
            "model": "openai/gpt-oss-20b", "reasoning_effort": "low", "include_reasoning": False, "max_completion_tokens": 2048,
            "messages": [{"role": "user", "content": prompt}]
        }
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=20
        )
        raw = response.json()["choices"][0]["message"]["content"].strip()
        web_obj = safe_extract_json(raw)
    except Exception:
        web_obj = None

    if not isinstance(web_obj, dict):
        ads, results = build_fallback_items()
        web_obj = {
            "ads": ads,
            "results": results,
            "pagination": {"next_page_label": "Next >", "page_number": 1},
            "clues": []
        }

    ads = [normalize_item(x, x.get("site_type", "legit") if isinstance(x, dict) else "legit") for x in (web_obj.get("ads") or [])]
    results = [normalize_item(x, x.get("site_type", "legit") if isinstance(x, dict) else "legit") for x in (web_obj.get("results") or [])]

    if len([x for x in ads if x]) < 2 or len([x for x in results if x]) < 6:
        fallback_ads, fallback_results = build_fallback_items()
        ads = [normalize_item(x, x["site_type"]) for x in fallback_ads]
        results = [normalize_item(x, x["site_type"]) for x in fallback_results]

    _random.shuffle(results)

    web_obj["ads"] = [x for x in ads if x][:2]
    web_obj["results"] = [x for x in results if x][:6]
    web_obj["pagination"] = web_obj.get("pagination") or {"next_page_label": "Next >", "page_number": 1}

    return jsonify({
        "success": True,
        "difficulty": difficulty,
        "query": query,
        "web": web_obj
    })

@app.route("/api/analyze_any", methods=["POST"])
def analyze_any():
    """
    Unified analyzer for: desktop email, desktop internet,
    mobile SMS, mobile call, mobile web.

    Expected JSON:
    {
        "type": "email" | "internet" | "sms" | "call" | "web",
        "user_choice": "scam" | "not_scam" | "fake" | "real",
        "message": "<content the user saw>"
    }
    """

    data = request.get_json() or {}
    output_language = get_llm_output_language()
    msg_type = data.get("type", "").lower()
    time_spent = data.get("time_spent_seconds")
    user_choice = data.get("user_choice")
    message = data.get("message")

    if not msg_type or not user_choice or not message:
        return jsonify({"success": False, "error": "Missing fields"}), 400

    #Normalize user choice
    choice = user_choice.strip().lower()
    if choice == "fake":
        choice = "scam"
    elif choice == "real":
        choice = "not_scam"

    #Map type → difficulty column name
    difficulty_map = {
        "email": "difficulty_email_desktop",
        "internet": "difficulty_internet_desktop",
        "sms": "difficulty_sms_mobile",
        "call": "difficulty_call_mobile",
        "web": "difficulty_web_mobile",
    }

    if msg_type not in difficulty_map:
        return jsonify({"success": False, "error": "Unknown message type"}), 400

    platform_map = {
        "email": "desktop",
        "internet": "desktop",
        "sms": "mobile",
        "call": "mobile",
        "web": "mobile",
    }

    platform = platform_map[msg_type]

    # Allow caller to override platform (e.g. mobile email vs desktop email)
    request_platform = data.get("platform", "").lower()
    if request_platform in ("mobile", "desktop"):
        platform = request_platform

    category = difficulty_map[msg_type]
    if msg_type == "email" and platform == "mobile":
        category = "difficulty_email_mobile"

    difficulty = get_difficulty(category)

    #Human-readable label (for prompt)
    type_label = {
        "email": "EMAIL",
        "internet": "WEBPAGE / SEARCH RESULT",
        "sms": "TEXT MESSAGE (SMS)",
        "call": "PHONE CALL TRANSCRIPT",
        "web": "MOBILE WEBPAGE / SEARCH RESULT"
    }.get(msg_type, "MESSAGE")

    expected_label = data.get("expected_label")
    if isinstance(expected_label, str):
        expected_label = expected_label.strip().lower()
        if expected_label == "fake":
            expected_label = "scam"
        elif expected_label == "real":
            expected_label = "not_scam"
        if expected_label not in ("scam", "not_scam"):
            expected_label = None
    else:
        expected_label = None

    if expected_label:
        is_correct_local = (choice == expected_label)
        correct_answer_label = "SCAM" if expected_label == "scam" else "LEGITIMATE"
        user_answer_label = "SCAM" if choice == "scam" else "LEGITIMATE"
        explain_prompt = f"""You are a cybersecurity trainer giving feedback on a {type_label} classification exercise.

The trainee was shown this content:
--- CONTENT START ---
{message[:2000]}
--- CONTENT END ---

The correct classification is: {correct_answer_label}
The trainee answered: {user_answer_label} — which is {'CORRECT' if is_correct_local else 'INCORRECT'}.

Write a 1-2 sentence explanation of WHY this content is {correct_answer_label}, pointing to specific clues.
Then list 2-3 short clue strings.
Write feedback and clues in {output_language}.

Respond ONLY with valid JSON, no markdown:
{{"correct": {'true' if is_correct_local else 'false'}, "feedback": "explanation here", "clues": ["clue 1", "clue 2"]}}"""
        headers_ex = {"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"}
        payload_ex = {"model": "openai/gpt-oss-20b", "reasoning_effort": "low", "include_reasoning": False, "max_completion_tokens": 2048, "messages": [{"role": "user", "content": explain_prompt}]}
        try:
            r_ex = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers_ex, json=payload_ex)
            raw_ex = r_ex.json()["choices"][0]["message"]["content"].strip()
            if raw_ex.startswith("```"):
                raw_ex = raw_ex.replace("```json", "").replace("```", "").strip()
            parsed = json.loads(raw_ex)
            parsed["correct"] = is_correct_local  # enforce deterministic result
        except Exception:
            parsed = {"correct": is_correct_local, "feedback": f"This {type_label.lower()} is {correct_answer_label.lower()}.", "clues": []}
    else:
        # -------------------------------------------
        # Build AI prompt
        # -------------------------------------------
        prompt = f"""
You are a cybersecurity training AI.

The trainee reviewed the following {type_label}:

--- USER CONTENT START ---
{message}
--- USER CONTENT END ---

The trainee selected: {choice.upper()} (SCAM vs NOT SCAM)

### STRICT RULES ###
- Respond ONLY with valid JSON.
- No markdown.
- No commentary outside the JSON.
- Use DOUBLE QUOTES.
- Write feedback and clues in {output_language}.

### REQUIRED JSON OUTPUT ###
{{
  "correct": true or false,
  "feedback": "One or two sentence explanation.",
  "clues": ["short clue 1", "short clue 2"]
}}
"""

        headers = {
            "Authorization": f"Bearer {GROQ_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "openai/gpt-oss-20b", "reasoning_effort": "low", "include_reasoning": False, "max_completion_tokens": 2048,
            "messages": [{"role": "user", "content": prompt}]
        }

        #Call Groq API
        r = requests.post("https://api.groq.com/openai/v1/chat/completions",
                          headers=headers, json=payload)

        data = r.json()
        print("UNIFIED ANALYZER RAW:", data)

        if "choices" not in data:
            return jsonify({"success": False, "error": "Groq returned no choices"}), 500

        raw = data["choices"][0]["message"]["content"].strip()

        #Clean JSON fences
        if raw.startswith("```"):
            raw = raw.replace("```json", "").replace("```", "").strip()

        #Parse JSON safely
        try:
            parsed = json.loads(raw)
        except Exception:
            parsed = {
                "correct": False,
                "feedback": "AI response could not be parsed.",
                "clues": []
            }

    #####################
    # Updating difficulty
    #####################
    is_correct = parsed.get("correct", False)
    if is_correct:
        set_difficulty(category, difficulty + 1)
    else:
        set_difficulty(category, 1)

    username = session.get('username')
    if username:
        correct_answer = choice if is_correct else ("not_scam" if choice == "scam" else "scam")
        scenario_type_full = f"{msg_type}_{platform}"
        indicators_found = parsed.get("clues", []) if is_correct else []
        log_scenario_attempt(
            username,
            scenario_type_full,
            platform,
            choice,
            correct_answer,
            is_correct,
            difficulty,
            json.dumps(parsed),
            duration_seconds=time_spent,
            message=message,
            indicators_found=indicators_found
        )
        update_module_progress(username, scenario_type_full)

    return jsonify({
        "success": True,
        "feedback": parsed,
        "difficulty_now": get_difficulty(category)
    })

# Main
if __name__ == '__main__':
    port = int(os.getenv("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
