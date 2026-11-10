"""Build today's approval inbox: inbox/YYYY-MM-DD.md (+ work/inbox_map.json, so you can say "skip 3 and 7").
Run: .venv/bin/python scripts/make_inbox.py
"""
import json
from difflib import SequenceMatcher

from common import INBOX, WORK, db, today


def short(t, n=220):
    t = " ".join((t or "").split())
    return t if len(t) <= n else t[: n - 1] + "…"


def main():
    con = db()
    q = lambda sql, *a: con.execute(sql, a).fetchall()  # noqa: E731
    base = """SELECT c.id, c.text, c.like_count, c.parent_id, v.title, l.category, l.language, l.confidence, l.reason, l.action,
                     COALESCE(c.scope,'own') AS scope, c.video_id
              FROM comments c JOIN labels l ON l.comment_id=c.id LEFT JOIN videos v ON v.id=c.video_id"""
    own = " AND COALESCE(c.scope,'own')='own'"
    lines, mp, n = [f"# Inbox · {today()}", ""], {}, 0
    dup_note = {}

    def item(r, drafts):
        nonlocal n
        n += 1
        mp[n] = r["id"]
        note = f" · 🔁 same text in {dup_note[r['id']]} places" if r["id"] in dup_note else ""
        out = [f"**{n}.** _{short(r['title'], 60)}_ · 👍 {r['like_count']} · {r['category']} · {r['language']} · conf {r['confidence']:.2f}{note}",
               f"> {short(r['text'])}"]
        for d in drafts:
            tag = " · 🎓 offer" if d["offer_mention"] else ""
            warn = " · ⚠️ fill the [blank] first" if "[" in d["text"] else ""
            out.append(f"- **{d['option']}:** {d['text']}{tag}{warn}")
        return out + [""]

    raw_alerts = q(base + " WHERE l.action='alert' AND c.id NOT IN (SELECT comment_id FROM actions WHERE kind='alert_seen')" + own +
                   " ORDER BY c.like_count DESC")
    # group copy-paste alerts (near-identical text) so you see one item with a count
    groups = []
    for r in raw_alerts:
        t = " ".join((r["text"] or "").lower().split())
        for g in groups:
            if len(t) > 40 and SequenceMatcher(None, t, g["t"]).ratio() > 0.8:
                g["rows"].append(r)
                break
        else:
            groups.append({"t": t, "rows": [r]})
    alerts = [g["rows"][0] for g in groups]
    dup_note = {g["rows"][0]["id"]: len(g["rows"]) for g in groups if len(g["rows"]) > 1}
    leads = q(base + """ WHERE (l.category IN ('offer_question','wants_to_learn') OR COALESCE(c.parent_id,c.id) IN
                         (SELECT thread_id FROM threads WHERE status='hot_lead'))
                         AND l.action='reply' AND c.id IN (SELECT comment_id FROM drafts WHERE status='pending')""" + own +
              " ORDER BY c.like_count DESC")
    lead_ids = {r["id"] for r in leads}
    pend = q(base + " WHERE l.action='reply' AND c.id IN (SELECT comment_id FROM drafts WHERE status='pending')" + own +
             " ORDER BY c.like_count DESC")
    sugg = q(base + """ WHERE l.action='reply' AND COALESCE(c.scope,'own')='mention' AND c.id IN (SELECT comment_id FROM drafts)
                        ORDER BY c.like_count DESC LIMIT 15""")
    two = [r for r in pend if r["id"] not in lead_ids and len(q("SELECT 1 FROM drafts WHERE comment_id=?", r["id"])) > 1]
    two_ids = {r["id"] for r in two}
    one = [r for r in pend if r["id"] not in lead_ids and r["id"] not in two_ids]
    hold = q(base + " WHERE l.action IN ('hold','hide_ban') AND c.id NOT IN (SELECT comment_id FROM actions WHERE kind LIKE 'moderate%')" +
             own + " ORDER BY c.like_count DESC")
    heart = q(base + " WHERE l.category IN ('praise','superfan','success_story')" + own + " ORDER BY c.like_count DESC LIMIT 5")
    D = lambda cid: q("SELECT * FROM drafts WHERE comment_id=? ORDER BY option", cid)  # noqa: E731

    lines += [f"Alerts {len(alerts)} · Hot leads {len(leads)} · Decide {len(two)} · Ready {len(one)} · Hold {len(hold)}", ""]
    sections = [("🔴 Alerts: please look yourself (never auto-replied)", alerts),
                ("🔥 Hot leads: asking about your course / product / membership", leads),
                ("🟡 Decide: A (calm) or B (witty)", two),
                ("🟢 Ready: say \"approve all\" or give numbers", one)]
    for title, rows in sections:
        lines += [f"## {title}", ""]
        if not rows:
            lines += ["_Nothing_", ""]
        for r in rows:
            lines += item(r, D(r["id"]))
    lines += ["## ⏸ Hold list (scam / spam / personal info) · reversible", ""]
    for r in hold:
        n += 1
        mp[n] = r["id"]
        lines.append(f"- **{n}.** {short(r['text'], 120)}  · _{r['reason']}_")
    lines += ["", "## 🌐 Other channels: suggestions only (ReplyDNA never posts there)", ""]
    try:
        radar = q("SELECT * FROM mention_videos WHERE alert=1 OR lookalike=1 ORDER BY alert DESC, views DESC LIMIT 8")
    except Exception:
        radar = []
    for v in radar:
        tag = "🔴 negative title" if v["alert"] else "⚠️ channel name looks like yours: yours or fake?"
        st = con.execute("""SELECT SUM(l.about_creator=1), SUM(l.about_creator=1 AND l.tone='negative'), SUM(l.category='fraud_claim'),
                                   SUM(l.about_creator=1 AND l.tone='positive')
                            FROM comments c JOIN labels l ON l.comment_id=c.id WHERE c.video_id=?""", (v["id"],)).fetchone()
        extra = f" · {st[0]} comments about you ({st[3] or 0} for, {st[1] or 0} against, {st[2] or 0} fraud claims)" if st and st[0] else ""
        lines.append(f"- {tag} · {v['channel']} · {v['views'] or 0:,} views · {short(v['title'], 70)}{extra} · {v['url']}")
    for r in sugg:
        d = D(r["id"])
        lines.append(f"- 👍 {r['like_count']} · _{short(r['title'], 50)}_ · https://www.youtube.com/watch?v={r['video_id']}")
        lines.append(f"  > {short(r['text'], 160)}")
        if d:
            lines.append(f"  - suggestion (post it yourself if you like): {d[0]['text']}")
    if not radar and not sugg:
        lines.append("_Nothing_")
    lines += ["", "## ❤️ Heart / pin these (one tap in the YouTube app; the API can't do it)", ""]
    lines += [f"- 👍 {r['like_count']} · {short(r['text'], 120)}" for r in heart] or ["_Nothing_"]
    path = INBOX / f"{today()}.md"
    path.write_text("\n".join(lines) + "\n")
    (WORK / "inbox_map.json").write_text(json.dumps(mp, indent=1))
    print(f"Inbox ready: {path}  (alerts {len(alerts)}, leads {len(leads)}, decide {len(two)}, ready {len(one)}, hold {len(hold)})")


if __name__ == "__main__":
    main()
