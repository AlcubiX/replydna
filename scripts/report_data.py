"""Numbers for the monthly report (Claude writes the narrative on top of these).
Run: .venv/bin/python scripts/report_data.py [--days 30]   → reports/data-YYYY-MM-DD.json
"""
import argparse
import datetime as dt
import json
import math

from common import REPORTS, db, today


def wilson_lower(k, n, z=1.96):
    """Lower bound of the 95% confidence interval for a share k/n (honest with small samples)."""
    if n == 0:
        return 0.0
    p = k / n
    return (p + z * z / (2 * n) - z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n)) / (1 + z * z / n)


def mentions_block(con):
    vids = con.execute("SELECT * FROM mention_videos WHERE status='tracked' ORDER BY views DESC").fetchall()
    lst = []
    for v in vids:
        st = con.execute("""SELECT COUNT(*), SUM(l.about_creator=1), SUM(l.about_creator=1 AND l.tone='positive'),
                                   SUM(l.about_creator=1 AND l.tone='neutral'), SUM(l.about_creator=1 AND l.tone='negative'),
                                   SUM(l.category='fraud_claim')
                            FROM comments c JOIN labels l ON l.comment_id=c.id WHERE c.video_id=?""", (v["id"],)).fetchone()
        lst.append({"title": v["title"], "channel": v["channel"], "views": v["views"] or 0, "url": v["url"], "alert": v["alert"],
                    "lookalike": v["lookalike"], "depth": v["depth"], "labelled": st[0] or 0, "about": st[1] or 0,
                    "pos": st[2] or 0, "neu": st[3] or 0, "neg": st[4] or 0, "fraud": st[5] or 0})
    look = {}
    for v in lst:
        if v["lookalike"]:
            look.setdefault(v["channel"], {"channel": v["channel"], "videos": 0, "views": 0})
            look[v["channel"]]["videos"] += 1
            look[v["channel"]]["views"] += v["views"]
    # reach-weighted: a podcast seen by 3M people counts more than a rant seen by 50K
    read = [v for v in lst if v["about"]]
    w = sum(v["views"] for v in read) or 1
    return {"videos": len(lst), "views": sum(v["views"] for v in lst), "about": sum(v["about"] for v in lst),
            "videos_read": len(read),
            "reach_pos": round(sum(v["views"] * v["pos"] / v["about"] for v in read) / w, 3),
            "reach_neg": round(sum(v["views"] * v["neg"] / v["about"] for v in read) / w, 3),
            "pos": sum(v["pos"] for v in lst), "neu": sum(v["neu"] for v in lst), "neg": sum(v["neg"] for v in lst),
            "fraud": sum(v["fraud"] for v in lst), "alerts": sum(1 for v in lst if v["alert"]),
            "list": lst[:40], "lookalikes": sorted(look.values(), key=lambda x: -x["views"])}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=30)
    a = ap.parse_args()
    since = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=a.days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    con = db()
    rows = con.execute("""SELECT c.*, l.category, l.tone, l.language, l.abi_pillar, l.action FROM comments c
                          JOIN labels l ON l.comment_id=c.id
                          WHERE c.is_owner=0 AND c.published_at>=? AND COALESCE(c.scope,'own')='own'""", (since,)).fetchall()
    total = len(rows)

    def count(key):
        return dict(sorted(((k, sum(1 for r in rows if r[key] == k)) for k in {r[key] for r in rows}), key=lambda x: -x[1]))

    w = lambda r: math.log1p(r["like_count"] or 0) + 1  # noqa: E731  like-weighted: likes = the silent majority's vote
    sent = {"positive": 1, "neutral": 0, "negative": -1}
    lw = sum(sent.get(r["tone"], 0) * w(r) for r in rows) / max(1, sum(w(r) for r in rows))
    owner_threads = {r[0] for r in con.execute("SELECT COALESCE(parent_id, id) FROM comments WHERE is_owner=1")}
    qcats = ("beginner_question", "advanced_question", "offer_question", "wants_to_learn", "advice_request", "topic_request")
    questions = sorted([r for r in rows if r["category"] in qcats], key=lambda r: -(r["like_count"] or 0))
    unanswered = [r for r in questions if (r["parent_id"] or r["id"]) not in owner_threads]
    neg = sum(1 for r in rows if r["tone"] == "negative")
    out = {
        "window_days": a.days, "total_comments": total,
        "by_category": count("category"), "by_language": count("language"), "by_tone": count("tone"), "by_abi": count("abi_pillar"),
        "like_weighted_sentiment": round(lw, 3),
        "negative_share": round(neg / max(1, total), 3), "negative_share_wilson_lower": round(wilson_lower(neg, total), 3),
        "questions": len(questions), "unanswered_questions": len(unanswered),
        "top_questions": [{"likes": r["like_count"], "text": r["text"][:160]} for r in questions[:15]],
        "owner_replies": con.execute("SELECT COUNT(*) FROM comments WHERE is_owner=1 AND published_at>=?", (since,)).fetchone()[0],
        "risks": {k: sum(1 for r in rows if r["category"] == k)
                  for k in ("fraud_claim", "scam", "impersonation", "legal_threat", "distress", "personal_info")},
    }
    try:
        out["mentions"] = mentions_block(con)
    except Exception:
        out["mentions"] = {}
    path = REPORTS / f"data-{today()}.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(f"{path}: {total} comments, {len(questions)} questions ({len(unanswered)} unanswered), like-weighted mood {lw:+.2f}")
