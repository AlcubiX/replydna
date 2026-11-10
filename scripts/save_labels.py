"""Validate and store the labels + reply drafts that Claude wrote (JSONL).

One line per comment:
{"comment_id": "...", "category": "...", "tone": "...", "validity": "...", "abi_pillar": "...",
 "severity": "...", "urgency": "...", "action": "...", "evidence": "...", "reason": "...",
 "confidence": 0.9, "language": "english",
 "drafts": [{"option": "A", "text": "...", "offer_mention": false}, {"option": "B", "text": "..."}],
 "about_creator": true,              # REQUIRED for mention comments (other channels): is this comment about you?
 "thread_status": "hot_lead"}        # optional: active | hot_lead | closed | handed_to_creator
Run: .venv/bin/python scripts/save_labels.py work/labels.jsonl
"""
import sys

from common import db, now_iso, read_jsonl

ENUM = {
    "category": {"praise", "generic_praise", "superfan", "beginner_question", "advanced_question", "advice_request",
                 "offer_question", "wants_to_learn", "valid_criticism", "joke_but_valid", "factual_correction", "blame",
                 "distress", "selling_accusation", "fraud_claim", "troll", "competitor_comparison", "success_story",
                 "topic_request", "outdated_info", "customer_complaint", "legal_threat", "scam", "impersonation",
                 "abuse", "spam", "personal_info", "other"},
    "tone": {"positive", "neutral", "negative"},
    "validity": {"specific", "vague"},
    "abi_pillar": {"ability", "benevolence", "integrity", "none"},
    "severity": {"high", "medium", "low"},
    "urgency": {"now", "24h", "monitor"},
    "action": {"reply", "hold", "hide_ban", "alert", "ignore"},
}
# your product / course / membership is never mentioned on these
NEVER_OFFER = {"blame", "distress", "troll", "valid_criticism", "success_story", "customer_complaint", "advice_request", "fraud_claim"}
# these always go to you as 🔴 alerts, never an automatic reply
ALERT_ONLY = {"distress", "legal_threat", "customer_complaint", "fraud_claim"}


def check(r):
    errs = [f"{k}={r.get(k)!r}" for k, allowed in ENUM.items() if r.get(k) not in allowed]
    if not r.get("language"):
        errs.append("language missing (use a plain name: english, hinglish, hindi, spanish, ...)")
    try:
        if not 0 <= float(r.get("confidence", -1)) <= 1:
            errs.append("confidence")
    except (TypeError, ValueError):
        errs.append("confidence")
    for d in r.get("drafts", []):
        if d.get("offer_mention") and r.get("category") in NEVER_OFFER:
            errs.append(f"offer mention not allowed on {r['category']}")
        if len(d.get("text", "")) > 500:
            errs.append("draft longer than 500 chars")
    if r.get("category") in ALERT_ONLY and r.get("action") != "alert":
        errs.append(f"{r['category']} must have action=alert")
    return errs


if __name__ == "__main__":
    rows = read_jsonl(sys.argv[1])
    con = db()
    ok = bad = 0
    for r in rows:
        errs = check(r)
        if errs:
            bad += 1
            print("SKIP", r.get("comment_id"), "→", "; ".join(errs))
            continue
        con.execute("""INSERT OR REPLACE INTO labels(comment_id, category, tone, validity, abi_pillar, severity, urgency, action,
                       evidence, reason, confidence, language, labeled_by, labeled_at, about_creator) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (r["comment_id"], r["category"], r["tone"], r["validity"], r["abi_pillar"], r["severity"], r["urgency"],
                     r["action"], r.get("evidence", "")[:60], r.get("reason", ""), float(r["confidence"]), r["language"].lower(),
                     "claude", now_iso(), None if r.get("about_creator") is None else int(bool(r["about_creator"]))))
        for d in r.get("drafts", []):
            con.execute("""INSERT INTO drafts(comment_id, option, text, offer_mention, status) VALUES (?,?,?,?, 'pending')
                           ON CONFLICT(comment_id, option) DO UPDATE SET text=excluded.text, offer_mention=excluded.offer_mention
                           WHERE drafts.status='pending'""",
                        (r["comment_id"], d["option"], d["text"], int(bool(d.get("offer_mention")))))
        if r.get("thread_status"):
            top = con.execute("SELECT COALESCE(parent_id, id) AS t FROM comments WHERE id=?", (r["comment_id"],)).fetchone()
            if top:
                con.execute("""INSERT INTO threads(thread_id, status, last_reason) VALUES (?,?,?)
                               ON CONFLICT(thread_id) DO UPDATE SET status=excluded.status, last_reason=excluded.last_reason""",
                            (top["t"], r["thread_status"], r.get("reason", "")))
        ok += 1
    con.commit()
    print(f"{ok} labels saved, {bad} skipped")
