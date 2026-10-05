"""Fit spam/ham word counts and write data/email_token_counts.json.

Reads data/seed_emails.jsonl plus the email items in the assessment bank.
Run from the repo root: python scripts/fit_email_difficulty.py
"""

import ast
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from email_difficulty import fit

SEED_PATH = ROOT / "data" / "seed_emails.jsonl"
COUNTS_PATH = ROOT / "data" / "email_token_counts.json"
APP_PATH = ROOT / "app.py"


def load_seed_pairs():
    pairs = []
    for line in SEED_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        pairs.append((row["text"], row["label"]))
    return pairs


def load_bank_pairs():
    tree = ast.parse(APP_PATH.read_text(encoding="utf-8"))
    banks = None
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == "MODULE_ASSESSMENT_QUESTION_BANKS":
                banks = ast.literal_eval(node.value)
    if not banks:
        return []

    pairs = []
    for questions in banks.values():
        for question in questions:
            if question.get("channel") != "email":
                continue
            label = "scam" if question.get("correct") == "fake" else "not_scam"
            text = "\n".join(
                part for part in (
                    question.get("email_from", ""),
                    question.get("email_subject", ""),
                    question.get("email_html", ""),
                ) if part
            )
            pairs.append((text, label))
    return pairs


def main():
    pairs = load_seed_pairs() + load_bank_pairs()
    model = fit(pairs)
    COUNTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    COUNTS_PATH.write_text(json.dumps(model, indent=2, sort_keys=True), encoding="utf-8")

    spam_total = model["spam_total"] or 1
    ham_total = model["ham_total"] or 1
    vocabulary = set(model["spam_counts"]) | set(model["ham_counts"])
    ranked = []
    for token in vocabulary:
        if token.startswith("feat_"):
            continue
        spam_rate = model["spam_counts"].get(token, 0) / spam_total
        ham_rate = model["ham_counts"].get(token, 0) / ham_total
        ranked.append((spam_rate - ham_rate, token))
    ranked.sort(reverse=True)

    print(f"Wrote {COUNTS_PATH}")
    print(f"Emails: {model['spam_docs']} scam, {model['ham_docs']} legitimate")
    print("Most scam-leaning words:")
    for _gap, token in ranked[:12]:
        print(f"  {token}")


if __name__ == "__main__":
    main()
