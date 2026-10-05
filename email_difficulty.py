"""Naive Bayes difficulty score for generated training emails.

The generator still chooses scam vs legitimate. This module only estimates how
spam-like the wording is, then checks that estimate against the user's level.
"""

import json
import math
import re
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlparse

COUNTS_PATH = Path(__file__).resolve().parent / "data" / "email_token_counts.json"

STOPWORDS = {
    "a", "an", "the", "and", "or", "of", "to", "for", "in", "on", "at", "by",
    "with", "from", "your", "you", "our", "we", "is", "are", "was", "be", "this",
    "that", "it", "as", "if", "not", "no", "do", "does", "did", "have", "has",
    "had", "will", "can", "may", "please", "hello", "hi", "dear", "thanks",
    "thank", "regards", "www", "com", "net", "org", "html", "http", "https",
}

KNOWN_GOOD_DOMAINS = {
    "amazon.com",
    "apple.com",
    "chase.com",
    "cityutilities.com",
    "community-center.org",
    "contoso.com",
    "fedex.com",
    "google.com",
    "irs.gov",
    "microsoft.com",
    "paypal.com",
    "reportaproblem.apple.com",
    "ups.com",
    "usps.com",
}

URGENCY_RE = re.compile(
    r"\b(urgent|urgently|immediately|asap|suspended|frozen|expire|expires|expiring)\b"
    r"|act now|limited time|final notice|within \d+ (minutes|hours)",
    re.I,
)
CREDENTIAL_RE = re.compile(
    r"\b(password|passcode|otp|pin|cvv|ssn)\b|one[- ]time code|social security",
    re.I,
)
TAG_RE = re.compile(r"<[^>]+>")
HREF_RE = re.compile(r"href\s*=\s*['\"]([^'\"]+)['\"]", re.I)
ANCHOR_RE = re.compile(
    r"<a\b[^>]*href\s*=\s*['\"]([^'\"]+)['\"][^>]*>(.*?)</a>",
    re.I | re.S,
)
DOMAIN_IN_TEXT_RE = re.compile(r"\b([a-z0-9-]+(?:\.[a-z0-9-]+)+)\b", re.I)
WORD_RE = re.compile(r"[a-z0-9]+")

SCAM_GUIDANCE = {
    1: "Use several obvious scam words (urgent, verify, password, immediately). Include one clearly fake link domain.",
    2: "Use one or two clear scam words such as verify or urgent. Keep the rest professional, with one off-looking link domain.",
    3: "Sound professional. Use at most one mild scam-leaning word. Include one subtle lookalike domain.",
    4: "Avoid typical scam words such as urgent, verify, password, and immediately. Sound like ordinary company mail with one easy-to-miss clue.",
}

HAM_GUIDANCE = {
    1: "Use ordinary wording only. No urgency, no password or code request, and a real company domain.",
    2: "Mostly ordinary wording. You may mention account or payment once. No password or code request.",
    3: "Write a realistic notice that mentions the account calmly. Do not ask for a password, code, or payment.",
    4: "You may use a few words often seen in scam mail, such as unusual or verify, but the sender domain must be real and the email must not ask for a password, code, or payment.",
}

_model = None


def clamp_level(level):
    try:
        level = int(level)
    except (TypeError, ValueError):
        level = 1
    return max(1, min(4, level))


def level_guidance(expected_label, level):
    table = SCAM_GUIDANCE if expected_label == "scam" else HAM_GUIDANCE
    return table[clamp_level(level)]


def _hostname(url):
    raw = (url or "").strip()
    if not raw:
        return ""
    host = urlparse(raw).hostname
    if not host and "://" not in raw:
        host = urlparse("https://" + raw).hostname
    return (host or "").lower()


def _same_site(host, mentioned):
    host = (host or "").lower()
    mentioned = (mentioned or "").lower()
    return host == mentioned or host.endswith("." + mentioned) or mentioned.endswith("." + host)


def _is_known_good(host):
    for domain in KNOWN_GOOD_DOMAINS:
        if host == domain or host.endswith("." + domain):
            return True
    return False


def _suspicious_host(host):
    if not host or _is_known_good(host):
        return False
    labels = host.split(".")
    name = ".".join(labels[:-1]) if len(labels) > 1 else host
    if "-" in name:
        return True
    markers = ("secure", "verify", "login", "update", "review", "alert", "account", "support", "billing")
    return any(marker in name for marker in markers)


def _link_hosts(html):
    return [host for host in (_hostname(match) for match in HREF_RE.findall(html or "")) if host]


def _has_link_mismatch(html):
    for href, inner in ANCHOR_RE.findall(html or ""):
        host = _hostname(href)
        text = TAG_RE.sub(" ", inner).lower()
        mentioned = DOMAIN_IN_TEXT_RE.findall(text)
        if host and mentioned and not any(_same_site(host, item) for item in mentioned):
            return True
    return False


def tokenize(html):
    """Visible words, link domains, and a few pattern flags."""
    text = TAG_RE.sub(" ", html or "").lower()
    words = [
        token for token in WORD_RE.findall(text)
        if len(token) >= 3 and token not in STOPWORDS
    ]
    for host in _link_hosts(html):
        words.append(host)
        for label in host.split("."):
            if len(label) >= 3 and label not in STOPWORDS:
                words.append(label)

    if URGENCY_RE.search(text):
        words.append("feat_urgency")
    if CREDENTIAL_RE.search(text):
        words.append("feat_credential_ask")
    if any(_suspicious_host(host) for host in _link_hosts(html)):
        words.append("feat_suspicious_domain")
    if _has_link_mismatch(html):
        words.append("feat_link_mismatch")
    return words


def fit(pairs):
    """pairs: iterable of (text, label) with label 'scam' or 'not_scam'."""
    spam_counts = defaultdict(int)
    ham_counts = defaultdict(int)
    spam_docs = 0
    ham_docs = 0
    for text, label in pairs:
        tokens = tokenize(text)
        target = spam_counts if label == "scam" else ham_counts
        if label == "scam":
            spam_docs += 1
        else:
            ham_docs += 1
        for token in tokens:
            target[token] += 1

    vocabulary = set(spam_counts) | set(ham_counts)
    return {
        "spam_counts": dict(spam_counts),
        "ham_counts": dict(ham_counts),
        "spam_total": int(sum(spam_counts.values())),
        "ham_total": int(sum(ham_counts.values())),
        "spam_docs": spam_docs,
        "ham_docs": ham_docs,
        "vocabulary_size": len(vocabulary),
    }


def _sigmoid(log_odds):
    if log_odds > 20:
        return 1.0
    if log_odds < -20:
        return 0.0
    return 1.0 / (1.0 + math.exp(-log_odds))


def score_email(html, model=None):
    model = model if model is not None else get_model()
    tokens = tokenize(html)
    spam_total = model.get("spam_total", 0)
    ham_total = model.get("ham_total", 0)
    vocab_size = model.get("vocabulary_size", 1) or 1
    spam_counts = model.get("spam_counts", {})
    ham_counts = model.get("ham_counts", {})
    spam_docs = model.get("spam_docs", 1)
    ham_docs = model.get("ham_docs", 1)

    log_odds = math.log((spam_docs + 1) / (ham_docs + 1))
    grouped = defaultdict(float)
    for token in tokens:
        spam_prob = (spam_counts.get(token, 0) + 1) / (spam_total + vocab_size)
        ham_prob = (ham_counts.get(token, 0) + 1) / (ham_total + vocab_size)
        grouped[token] += math.log(spam_prob) - math.log(ham_prob)

    log_odds += sum(grouped.values())
    # Average by length. The raw sum runs off to 0 or 1 on a normal email,
    # which collapses levels 2 and 3.
    token_count = max(1, len(tokens))
    ranked = sorted(grouped.items(), key=lambda item: item[1], reverse=True)
    visible = [(token, weight) for token, weight in ranked if not token.startswith("feat_")]

    return {
        "p_spam": _sigmoid(log_odds / token_count),
        "top_scam_words": [token for token, weight in visible if weight > 0][:5],
        "top_ham_words": [token for token, weight in reversed(visible) if weight < 0][:5],
        "features": [token for token in grouped if token.startswith("feat_")],
    }


def _band_interval(expected_label, level):
    """(low, high, low_inclusive, high_inclusive). None means no edge.

    Cutoffs come from the seed corpus after per-word averaging. Obvious scam
    wording sits near 0.80. Ordinary legitimate mail sits near 0.20.
    """
    if expected_label == "scam":
        return {
            1: (0.78, None, True, False),
            2: (0.68, 0.78, True, False),
            3: (0.58, 0.68, True, False),
            4: (0.45, 0.58, True, False),
        }[level]
    return {
        1: (None, 0.24, False, True),
        2: (0.24, 0.32, False, True),
        3: (0.32, 0.42, False, True),
        4: (0.42, 0.60, False, True),
    }[level]


def in_band(p_spam, expected_label, level):
    low, high, low_inclusive, high_inclusive = _band_interval(expected_label, clamp_level(level))
    if low is not None and (p_spam < low or (p_spam == low and not low_inclusive)):
        return False
    if high is not None and (p_spam > high or (p_spam == high and not high_inclusive)):
        return False
    return True


def band_distance(p_spam, expected_label, level):
    if in_band(p_spam, expected_label, level):
        return 0.0
    low, high, _low_inclusive, _high_inclusive = _band_interval(expected_label, clamp_level(level))
    if low is None:
        return max(0.0, p_spam - high)
    if high is None:
        return max(0.0, low - p_spam)
    if p_spam < low:
        return low - p_spam
    return p_spam - high


def level_for(p_spam, expected_label):
    for level in (1, 2, 3, 4):
        if in_band(p_spam, expected_label, level):
            return level
    nearest = min(
        (1, 2, 3, 4),
        key=lambda level: (band_distance(p_spam, expected_label, level), level),
    )
    return nearest


def get_model():
    global _model
    if _model is None:
        _model = json.loads(COUNTS_PATH.read_text(encoding="utf-8"))
    return _model


def reload_model():
    global _model
    _model = None
    return get_model()
