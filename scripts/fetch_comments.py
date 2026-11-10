"""Fetch new comments into the database and write the unlabelled ones to work/to_label.jsonl.

Sources:
  --source api     (default) official YouTube Data API with your saved login; all channel videos, newest first
  --source public  no login needed (yt-dlp); latest N videos only. Great for trying ReplyDNA before the Google setup.
Options:
  --days N         first run: how far back to go (default 30)
  --videos N       public mode: how many latest videos (default 5)
  --mentions       also read comments on OTHER channels' videos that feature you (see find_mentions.py). Read-only.
Free pre-filter: emoji-only comments, very short generic praise and phone/link spam are labelled here by rules,
so Claude never spends effort on them.
"""
import argparse
import datetime as dt
import re

from common import WORK, db, log_action, now_iso, profile, quota_spend, write_jsonl, youtube

PHONE = re.compile(r"\+?\d[\d\s().-]{8,}\d")
LINK = re.compile(r"(https?://|www\.|t\.me/|wa\.me/|bit\.ly|tinyurl)", re.I)
GENERIC = re.compile(
    r"^(nice|good|great|super|superb|awesome|amazing|first|1st|wow|thanks?|thank you|thx|ty|op|love (it|this|you)|"
    r"good (morning|afternoon|evening|night)|thanks? for (the )?(info(rmation)?|video|sharing)|"
    r"mast|badhiya|bahut (badhiya|accha|achha)|gracias|genial|excelente|obrigad[oa]|merci|danke|grazie|"
    r"(nice|good|great|awesome|amazing|superb|excellent|helpful) (video|content|work|job|one|explanation|info)( (thanks?|thank you))?)"
    r"[\s!.🙏❤️👍🔥💯😍]*(sir|ji|bro|bhai|man|guys|team)?[\s!.🙏❤️👍🔥💯😍]*$", re.I)


def upsert_comment(con, c):
    c.setdefault("scope", "own")
    con.execute(
        """INSERT INTO comments(id, video_id, parent_id, author_name, author_channel_id, text, like_count,
                                published_at, is_owner, fetched_at, source, scope)
           VALUES (:id,:video_id,:parent_id,:author_name,:author_channel_id,:text,:like_count,:published_at,:is_owner,:fetched_at,:source,:scope)
           ON CONFLICT(id) DO UPDATE SET like_count=excluded.like_count, text=excluded.text, fetched_at=excluded.fetched_at""",
        c)


def from_api(con, channel_id, days):
    yt = youtube()
    last = con.execute("SELECT value FROM state WHERE key='last_seen_api'").fetchone()
    since = last["value"] if last else (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    newest, n, token, video_ids = since, 0, None, set()
    while True:
        quota_spend(con, "list")
        r = yt.commentThreads().list(part="snippet,replies", allThreadsRelatedToChannelId=channel_id, order="time",
                                     maxResults=100, textFormat="plainText", pageToken=token).execute()
        stop = False
        for th in r.get("items", []):
            top = th["snippet"]["topLevelComment"]
            s = top["snippet"]
            if s["publishedAt"] <= since and s.get("updatedAt", s["publishedAt"]) <= since:
                stop = True
                break
            vid = th["snippet"].get("videoId") or s.get("videoId")
            video_ids.add(vid)
            rows = [(top, None)]
            replies = th.get("replies", {}).get("comments", [])
            if th["snippet"].get("totalReplyCount", 0) > len(replies):
                replies, ptoken = [], None
                while True:
                    quota_spend(con, "list")
                    rr = yt.comments().list(part="snippet", parentId=top["id"], maxResults=100, textFormat="plainText",
                                            pageToken=ptoken).execute()
                    replies += rr.get("items", [])
                    ptoken = rr.get("nextPageToken")
                    if not ptoken:
                        break
            rows += [(rc, top["id"]) for rc in replies]
            for item, parent in rows:
                sn = item["snippet"]
                author_id = (sn.get("authorChannelId") or {}).get("value", "")
                upsert_comment(con, {
                    "id": item["id"], "video_id": vid, "parent_id": parent, "author_name": sn.get("authorDisplayName", ""),
                    "author_channel_id": author_id, "text": sn.get("textDisplay", ""), "like_count": sn.get("likeCount", 0),
                    "published_at": sn["publishedAt"], "is_owner": int(author_id == channel_id), "fetched_at": now_iso(),
                    "source": "api"})
                n += 1
            newest = max(newest, s["publishedAt"])
        token = r.get("nextPageToken")
        if stop or not token:
            break
    # video titles (50 per call)
    ids = [v for v in video_ids if v and not con.execute("SELECT 1 FROM videos WHERE id=?", (v,)).fetchone()]
    for i in range(0, len(ids), 50):
        quota_spend(con, "list")
        vr = yt.videos().list(part="snippet", id=",".join(ids[i:i + 50])).execute()
        for v in vr.get("items", []):
            con.execute("INSERT OR REPLACE INTO videos(id, title, published_at) VALUES (?,?,?)",
                        (v["id"], v["snippet"]["title"], v["snippet"]["publishedAt"]))
    con.execute("INSERT OR REPLACE INTO state(key, value) VALUES ('last_seen_api', ?)", (newest,))
    return n


def _ytdlp_comments(con, info, channel_id, scope):
    n = 0
    for c in info.get("comments") or []:
        ts = dt.datetime.fromtimestamp(c.get("timestamp") or 0, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        upsert_comment(con, {
            "id": c["id"], "video_id": info["id"],
            # YouTube has one reply level: a reply-to-a-reply still belongs to the top-level thread
            "parent_id": None if c.get("parent") in (None, "root") else c["parent"].split(".")[0],
            "author_name": c.get("author", ""), "author_channel_id": c.get("author_id", ""), "text": c.get("text", ""),
            "like_count": c.get("like_count") or 0, "published_at": ts,
            "is_owner": int(bool(c.get("author_is_uploader") and scope == "own") or c.get("author_id") == channel_id),
            "fetched_at": now_iso(), "source": "public", "scope": scope})
        n += 1
    return n


def from_public(con, channel_handle, channel_id, n_videos):
    import yt_dlp

    with yt_dlp.YoutubeDL({"extract_flat": True, "playlistend": n_videos, "quiet": True, "no_warnings": True}) as y:
        pl = y.extract_info(f"https://www.youtube.com/{channel_handle}/videos", download=False)
    opts = {"skip_download": True, "getcomments": True, "quiet": True, "no_warnings": True,
            "extractor_args": {"youtube": {"max_comments": ["300", "all", "all", "10"], "comment_sort": ["top"]}}}
    n = 0
    with yt_dlp.YoutubeDL(opts) as y:
        for e in pl.get("entries", [])[:n_videos]:
            info = y.extract_info(f"https://www.youtube.com/watch?v={e['id']}", download=False)
            con.execute("INSERT OR REPLACE INTO videos(id, title, published_at) VALUES (?,?,?)",
                        (info["id"], info.get("title"), info.get("upload_date")))
            n += _ytdlp_comments(con, info, channel_id, "own")
    return n


def from_mentions(con, channel_id, per_video=150, max_videos=10, use_api=True):
    """Top comments of tracked OTHER-channel videos (scope='mention'). Read-only: we never post there."""
    week_ago = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
    # Balanced sample: half "risk" videos (negative title / look-alike channel), half the biggest-reach videos.
    # Reading only risk videos would make the mood look worse than it really is (selection bias).
    risk = con.execute("""SELECT * FROM mention_videos WHERE status='tracked' AND (last_fetch IS NULL OR last_fetch < ?)
                          AND (alert=1 OR lookalike=1) ORDER BY alert DESC, views DESC LIMIT ?""", (week_ago, max_videos // 2)).fetchall()
    reach = con.execute("""SELECT * FROM mention_videos WHERE status='tracked' AND (last_fetch IS NULL OR last_fetch < ?)
                           AND alert=0 AND lookalike=0 ORDER BY views DESC LIMIT ?""", (week_ago, max_videos - len(risk))).fetchall()
    vids = list(risk) + list(reach)
    yt = youtube() if use_api else None
    n = 0
    for v in vids:
        con.execute("INSERT OR REPLACE INTO videos(id, title, published_at) VALUES (?,?,?)",
                    (v["id"], f"[{v['channel']}] {v['title']}", v["published"]))
        if yt:
            token, got = None, 0
            while got < per_video:
                quota_spend(con, "list")
                r = yt.commentThreads().list(part="snippet", videoId=v["id"], order="relevance", maxResults=100,
                                             textFormat="plainText", pageToken=token).execute()
                for th in r.get("items", []):
                    s = th["snippet"]["topLevelComment"]["snippet"]
                    aid = (s.get("authorChannelId") or {}).get("value", "")
                    upsert_comment(con, {"id": th["snippet"]["topLevelComment"]["id"], "video_id": v["id"], "parent_id": None,
                                         "author_name": s.get("authorDisplayName", ""), "author_channel_id": aid,
                                         "text": s.get("textDisplay", ""), "like_count": s.get("likeCount", 0),
                                         "published_at": s["publishedAt"], "is_owner": int(aid == channel_id),
                                         "fetched_at": now_iso(), "source": "api", "scope": "mention"})
                    got += 1
                    n += 1
                token = r.get("nextPageToken")
                if not token:
                    break
        else:
            import yt_dlp
            opts = {"skip_download": True, "getcomments": True, "quiet": True, "no_warnings": True,
                    "extractor_args": {"youtube": {"max_comments": [str(per_video), str(per_video), "0", "0"], "comment_sort": ["top"]}}}
            try:
                with yt_dlp.YoutubeDL(opts) as y:
                    info = y.extract_info(v["url"], download=False)
            except Exception as e:
                print(f"skip {v['id']}: {str(e)[:80]}")
                continue
            n += _ytdlp_comments(con, info, channel_id, "mention")
            if info.get("view_count"):
                con.execute("UPDATE mention_videos SET views=? WHERE id=?", (info["view_count"], v["id"]))
        con.execute("UPDATE mention_videos SET last_fetch=? WHERE id=?", (now_iso(), v["id"]))
        con.commit()
    return n, len(vids)


def prefilter(con):
    """Free rule-based labels. Returns how many comments were handled without Claude."""
    rows = con.execute("""SELECT c.* FROM comments c LEFT JOIN labels l ON l.comment_id=c.id
                          WHERE l.comment_id IS NULL AND c.is_owner=0""").fetchall()
    handled = 0
    for c in rows:
        t = (c["text"] or "").strip()
        norm = re.sub(r"\s+", " ", t.lower())
        label = None
        if not re.search(r"\w", t):
            label = ("generic_praise", "positive", "ignore", "emoji-only")
        elif PHONE.search(t) or LINK.search(t):
            label = ("spam", "neutral", "hold", "phone number / link from a viewer (rule: you review it, never auto-hidden)")
        elif len(norm) <= 40 and GENERIC.match(norm):
            label = ("generic_praise", "positive", "ignore", "short generic praise / greeting")
        # Exact duplicates are NOT auto-labelled: a copy-pasted fraud claim must reach Claude (and you),
        # never get hidden as "spam" by a rule. make_inbox.py groups duplicates instead.
        if label:
            cat, tone, action, why = label
            con.execute("""INSERT OR REPLACE INTO labels(comment_id, category, tone, validity, abi_pillar, severity, urgency, action,
                           evidence, reason, confidence, language, labeled_by, labeled_at)
                           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (c["id"], cat, tone, "vague", "none", "low", "monitor", action, t[:60], why, 0.95, "", "rule", now_iso()))
            handled += 1
    return handled


def export_unlabeled(con):
    rows = con.execute("""SELECT c.id, c.video_id, v.title AS video_title, c.parent_id, c.like_count, c.text,
                                 COALESCE(c.scope,'own') AS scope, (SELECT text FROM comments p WHERE p.id=c.parent_id) AS parent_text
                          FROM comments c LEFT JOIN labels l ON l.comment_id=c.id LEFT JOIN videos v ON v.id=c.video_id
                          WHERE l.comment_id IS NULL AND c.is_owner=0 ORDER BY c.like_count DESC, c.published_at DESC""").fetchall()
    out = WORK / "to_label.jsonl"
    write_jsonl(out, [dict(r) for r in rows])
    return out, len(rows)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=["api", "public"], default="api")
    ap.add_argument("--mentions", action="store_true", help="also fetch comments of tracked other-channel videos")
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--videos", type=int, default=5)
    a = ap.parse_args()
    p = profile()
    ch = p["channels"][0]
    con = db()
    n = from_api(con, ch["channel_id"], a.days) if a.source == "api" else from_public(con, ch["handle"], ch["channel_id"], a.videos)
    if a.mentions:
        m, mv = from_mentions(con, ch["channel_id"], use_api=(a.source == "api"))
        print(f"Mentions radar: {m} comments from {mv} other videos")
    pre = prefilter(con)
    out, todo = export_unlabeled(con)
    owners = con.execute("SELECT COUNT(*) FROM comments WHERE is_owner=1").fetchone()[0]
    log_action(con, "fetch", "-", f"{a.source}: {n} comments, prefilter {pre}, to_label {todo}")
    con.commit()
    print(f"{n} comments fetched · {pre} handled by the free filter · {todo} for Claude ({out}) · your own replies: {owners}")
