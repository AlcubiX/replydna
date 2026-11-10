"""Mentions radar: find OTHER channels' videos that feature you (podcasts, interviews, reviews, reactions, exposés).

  .venv/bin/python scripts/find_mentions.py              # free search via yt-dlp (no quota)
  .venv/bin/python scripts/find_mentions.py --api        # also YouTube search API (100 units per query)
  .venv/bin/python scripts/find_mentions.py --list       # show tracked videos

Flags each video:
  depth      main_guest (your name / @handle in the title) | mention (only in the description)
  alert      negative-sounding title (scam, exposed, fake, truth, beware, ...) -> 🔴 alert for you
  lookalike  the channel name looks like yours but is not one of your official channels
             -> you confirm: your own second channel, a fan page, or an impersonator?
Run weekly. ReplyDNA never posts, hides or bans anything on other people's channels.
"""
import argparse
import re

from common import db, now_iso, profile, quota_spend

NEG = re.compile(r"proof against|fraud|scam|expos|fake|cheat|truth about|the truth|reality of|warning|beware|controversy|"
                 r"drama|apolog|lies|lying|called out|dhokha|sach(ai|chai)?|chor|estafa|fraude|"
                 r"धोखा|फ्रॉड|सच|चोर|स्कैम", re.I)
EXTRA_Q = ["podcast", "interview", "review", "reaction", "ft."]


def variants(p):
    names = list(dict.fromkeys(p.get("name_variants", []) + [p.get("creator_name", "")]))
    handles = [c["handle"].lstrip("@") for c in p["channels"]]
    # only full names count (a first name alone would match thousands of other people)
    return [n for n in names if n and " " in n.strip()], handles


def matches(text, names, handles):
    t = (text or "").lower()
    return any(n.lower() in t for n in names) or any(h.lower() in t for h in handles)


def search_ytdlp(queries, per_query=15):
    import yt_dlp
    found = {}
    with yt_dlp.YoutubeDL({"extract_flat": True, "quiet": True, "no_warnings": True}) as y:
        for q in queries:
            try:
                r = y.extract_info(f"ytsearch{per_query}:{q}", download=False)
            except Exception:
                continue
            for e in r.get("entries", []) or []:
                found[e["id"]] = {"id": e["id"], "channel": e.get("channel") or e.get("uploader") or "", "channel_id": e.get("channel_id"),
                                  "title": e.get("title") or "", "views": e.get("view_count") or 0, "published": "",
                                  "description": e.get("description") or "", "source": "ytdlp"}
    return found


def search_api(con, queries):
    from common import youtube
    yt, found = youtube(), {}
    for q in queries:
        quota_spend(con, "list", 100)  # search.list = 100 units
        r = yt.search().list(part="snippet", q=q, type="video", order="date", maxResults=25).execute()
        for it in r.get("items", []):
            s = it["snippet"]
            found[it["id"]["videoId"]] = {"id": it["id"]["videoId"], "channel": s["channelTitle"], "channel_id": s["channelId"],
                                         "title": s["title"], "views": 0, "published": s["publishedAt"],
                                         "description": s.get("description", ""), "source": "api"}
    return found


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", action="store_true")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()
    con, p = db(), profile()
    if not a.list:
        names, handles = variants(p)
        if not names and not handles:
            raise SystemExit("Add your full name to name_variants in config/profile.yaml first.")
        official = {c["channel_id"] for c in p["channels"]} | set(p.get("official_channel_ids") or [])
        main = names[0] if names else f"@{handles[0]}"
        queries = [main] + [f"{main} {x}" for x in EXTRA_Q] + [f"@{h}" for h in handles]
        found = search_ytdlp(queries)
        if a.api:
            found.update(search_api(con, queries[:2]))
        new = alerts = looks = 0
        for v in found.values():
            if v["channel_id"] in official:
                continue
            in_title = matches(v["title"], names, handles)
            if not (in_title or matches(v["description"], names, handles)):
                continue
            look = int(matches(v["channel"], names, handles))
            neg = int(bool(NEG.search(v["title"])) and in_title)  # a hint only: Claude reads the comments before calling it negative
            existed = con.execute("SELECT 1 FROM mention_videos WHERE id=?", (v["id"],)).fetchone()
            con.execute("""INSERT INTO mention_videos(id, channel, channel_id, title, views, published, url, depth, alert, lookalike, source, first_seen)
                           VALUES (?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET views=MAX(views, excluded.views), title=excluded.title""",
                        (v["id"], v["channel"], v["channel_id"], v["title"], v["views"], v["published"],
                         f"https://www.youtube.com/watch?v={v['id']}", "main_guest" if in_title else "mention", neg, look, v["source"], now_iso()))
            new += 0 if existed else 1
            alerts += neg
            looks += look
        con.commit()
        print(f"{len(found)} search results · {new} new mention videos · {alerts} negative-title alerts · {looks} look-alike channels")
    rows = con.execute("SELECT * FROM mention_videos ORDER BY alert DESC, lookalike DESC, views DESC").fetchall()
    tot = sum(r["views"] or 0 for r in rows)
    print(f"Tracked: {len(rows)} videos · ~{tot:,} views")
    for r in rows[:30]:
        flag = "🔴 " if r["alert"] else ("⚠️ " if r["lookalike"] else "   ")
        print(f"{flag}{r['views'] or 0:>11,} | {(r['channel'] or '')[:26]:<26} | {r['depth']:<10} | {r['title'][:70]}")
