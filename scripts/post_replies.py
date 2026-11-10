"""Approve / edit / skip drafts from the inbox, then post the approved replies.

  --approve all | 1,2,5        approve option A of these inbox numbers
  --choose 4=B,6=A             approve a specific option
  --edit "5=your own reply"    approve with your own text
  --skip 3,7
  --post [--dry-run] [--gap 20]   post approved replies (respects the daily cap, 4-per-thread limit and quota)
"""
import argparse
import json
import random
import re
import time

from common import WORK, assert_own_channel, db, log_action, now_iso, profile, quota_spend, today, youtube


def nums(s, mp, con=None):
    """Inbox numbers → comment ids. "all" means every 🟢/🟡/🔥 reply item: never 🔴 alerts or ⏸ holds,
    which can only be approved one by one, by number, after the creator has read them."""
    if s == "all":
        ids = list(mp.values())
        if con is None:
            return ids
        ok = {r[0] for r in con.execute(f"SELECT comment_id FROM labels WHERE action='reply' AND comment_id IN ({','.join('?' * len(ids))})", ids)}
        return [i for i in ids if i in ok]
    return [mp[str(int(x))] for x in s.split(",") if x.strip()]


def set_status(con, cid, option, status, text=None):
    con.execute("UPDATE drafts SET status='skipped', decided_at=? WHERE comment_id=? AND option<>? AND status='pending'",
                (now_iso(), cid, option))
    con.execute("UPDATE drafts SET status=?, final_text=COALESCE(?, final_text), decided_at=? WHERE comment_id=? AND option=?",
                (status, text, now_iso(), cid, option))


def post(con, dry, gap):
    p = profile()
    cap = p.get("max_replies_per_day", 100)
    posted_today = con.execute("SELECT COUNT(*) FROM actions WHERE kind='reply' AND ts LIKE ?", (today() + "%",)).fetchone()[0]
    room = cap - posted_today
    # other channels' videos (scope='mention') are never posted to: suggestions only
    rows = con.execute("""SELECT d.*, c.parent_id, c.author_name, c.id AS cid FROM drafts d JOIN comments c ON c.id=d.comment_id
                          WHERE d.status='approved' AND d.posted_reply_id IS NULL AND COALESCE(c.scope,'own')='own'""").fetchall()
    yt = None if dry else youtube()
    if yt:
        quota_spend(con, "list")
        assert_own_channel(yt)
    done = 0
    for r in rows:
        if done >= room:
            print(f"Daily limit ({cap}) reached. The rest goes tomorrow.")
            break
        thread = (r["parent_id"] or r["cid"]).split(".")[0]  # the API needs the top-level comment id
        th = con.execute("SELECT * FROM threads WHERE thread_id=?", (thread,)).fetchone()
        if th and th["status"] in ("closed", "handed_to_creator"):
            print(f"skip {r['cid']}: thread is {th['status']}")
            continue
        if th and th["assistant_reply_count"] >= 4:
            con.execute("UPDATE threads SET status='handed_to_creator' WHERE thread_id=?", (thread,))
            print(f"skip {r['cid']}: 4 replies in this thread already, handed over to you")
            continue
        text = r["final_text"] or r["text"]
        blank = re.search(r"\[[^\]]+\]", text)
        if blank:
            print(f"skip {r['cid']}: the reply still has a blank {blank.group(0)}. Fill it first.")
            continue
        if r["parent_id"] and r["author_name"]:
            text = f"{r['author_name']} {text}"  # replying inside a thread: tag the person
        if dry:
            print(f"[dry-run] reply to {thread}: {text}")
            done += 1
            continue
        quota_spend(con, "insert")
        res = yt.comments().insert(part="snippet", body={"snippet": {"parentId": thread, "textOriginal": text}}).execute()
        con.execute("UPDATE drafts SET posted_reply_id=?, status='posted' WHERE comment_id=? AND option=?",
                    (res["id"], r["comment_id"], r["option"]))
        con.execute("""INSERT INTO threads(thread_id, assistant_reply_count) VALUES (?,1)
                       ON CONFLICT(thread_id) DO UPDATE SET assistant_reply_count=assistant_reply_count+1""", (thread,))
        log_action(con, "reply", r["comment_id"], res["id"])
        con.commit()
        done += 1
        time.sleep(gap + random.uniform(0, gap / 2))  # human pace, never a burst
    print(f"{done} replies {'(dry-run, nothing was posted)' if dry else 'posted'}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--approve")
    ap.add_argument("--choose")
    ap.add_argument("--edit", action="append")
    ap.add_argument("--skip")
    ap.add_argument("--post", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--gap", type=int, default=20)
    a = ap.parse_args()
    con = db()
    mp = json.loads((WORK / "inbox_map.json").read_text()) if (WORK / "inbox_map.json").exists() else {}
    if a.approve:
        for cid in nums(a.approve, mp, con):
            if con.execute("SELECT 1 FROM drafts WHERE comment_id=? AND option='A' AND status='pending'", (cid,)).fetchone():
                set_status(con, cid, "A", "approved")
    if a.choose:
        for pair in a.choose.split(","):
            k, opt = pair.split("=")
            set_status(con, mp[k.strip()], opt.strip().upper(), "approved")
    for e in a.edit or []:
        k, txt = e.split("=", 1)
        set_status(con, mp[k.strip()], "A", "approved", txt.strip())
    if a.skip:
        for cid in nums(a.skip, mp):
            con.execute("UPDATE drafts SET status='skipped', decided_at=? WHERE comment_id=? AND status IN ('pending','approved')",
                        (now_iso(), cid))
    con.commit()
    if a.post:
        post(con, a.dry_run, a.gap)
    st = dict(con.execute("SELECT status, COUNT(*) FROM drafts GROUP BY status").fetchall())
    print("drafts:", st)
