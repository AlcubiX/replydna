"""Hold / publish / reject comments on YOUR channel (never on anyone else's).

  --auto-hold [--dry-run]     hold (reversible) only high-confidence scam / impersonation / personal-info comments
  --hold 3,8 | --publish 3 | --reject 3 [--ban]    by inbox number (reject / ban only after your OK)
"""
import argparse
import json

from common import WORK, assert_own_channel, db, log_action, quota_spend, youtube

AUTO_HOLD = ("scam", "impersonation", "personal_info")  # Claude-labelled only; never fraud claims, never rule labels


def apply(con, ids, status, ban, dry):
    yt = None if dry else youtube()
    if yt:
        quota_spend(con, "list")
        assert_own_channel(yt)
    for cid in ids:
        if dry:
            print(f"[dry-run] {status}{' + ban' if ban else ''}: {cid}")
            continue
        quota_spend(con, "moderate")
        kw = {"banAuthor": True} if (ban and status == "rejected") else {}
        yt.comments().setModerationStatus(id=cid, moderationStatus=status, **kw).execute()
        log_action(con, f"moderate_{status}", cid, "ban" if ban else "")
        con.commit()
    print(f"{len(ids)} comments → {status}{' (dry-run)' if dry else ''}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--auto-hold", action="store_true")
    ap.add_argument("--hold")
    ap.add_argument("--publish")
    ap.add_argument("--reject")
    ap.add_argument("--ban", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    con = db()
    mp = json.loads((WORK / "inbox_map.json").read_text()) if (WORK / "inbox_map.json").exists() else {}
    pick = lambda s: [mp[x.strip()] for x in s.split(",")]  # noqa: E731
    if a.auto_hold:
        rows = con.execute(f"""SELECT l.comment_id FROM labels l WHERE l.category IN ({",".join("?" * len(AUTO_HOLD))})
                               AND l.action IN ('hold','hide_ban') AND l.confidence >= 0.95 AND l.labeled_by='claude'
                               AND l.comment_id NOT IN (SELECT comment_id FROM actions WHERE kind LIKE 'moderate%')
                               AND l.comment_id IN (SELECT id FROM comments WHERE COALESCE(scope,'own')='own')""", AUTO_HOLD).fetchall()
        apply(con, [r[0] for r in rows], "heldForReview", False, a.dry_run)
    if a.hold:
        apply(con, pick(a.hold), "heldForReview", False, a.dry_run)
    if a.publish:
        apply(con, pick(a.publish), "published", False, a.dry_run)
    if a.reject:
        apply(con, pick(a.reject), "rejected", a.ban, a.dry_run)
