"""Create / upgrade the SQLite database.  Run: .venv/bin/python scripts/db.py"""
from common import DB_PATH, db

SCHEMA = """
CREATE TABLE IF NOT EXISTS videos(
  id TEXT PRIMARY KEY, title TEXT, published_at TEXT);
CREATE TABLE IF NOT EXISTS comments(
  id TEXT PRIMARY KEY, video_id TEXT, parent_id TEXT, author_name TEXT, author_channel_id TEXT,
  text TEXT, like_count INTEGER, published_at TEXT, is_owner INTEGER DEFAULT 0, fetched_at TEXT,
  source TEXT, scope TEXT DEFAULT 'own');                       -- scope: own | mention (other channels, read-only)
CREATE TABLE IF NOT EXISTS labels(
  comment_id TEXT PRIMARY KEY, category TEXT, tone TEXT, validity TEXT, abi_pillar TEXT,
  severity TEXT, urgency TEXT, action TEXT, evidence TEXT, reason TEXT, confidence REAL,
  language TEXT, labeled_by TEXT, labeled_at TEXT, about_creator INTEGER);
CREATE TABLE IF NOT EXISTS drafts(
  comment_id TEXT, option TEXT, text TEXT, offer_mention INTEGER DEFAULT 0,
  status TEXT DEFAULT 'pending', final_text TEXT, posted_reply_id TEXT, decided_at TEXT,
  PRIMARY KEY(comment_id, option));
CREATE TABLE IF NOT EXISTS threads(
  thread_id TEXT PRIMARY KEY, status TEXT DEFAULT 'active', assistant_reply_count INTEGER DEFAULT 0,
  last_reason TEXT);                                             -- status: active | hot_lead | closed | handed_to_creator
CREATE TABLE IF NOT EXISTS mention_videos(
  id TEXT PRIMARY KEY, channel TEXT, channel_id TEXT, title TEXT, views INTEGER, published TEXT, url TEXT,
  depth TEXT, alert INTEGER DEFAULT 0, lookalike INTEGER DEFAULT 0, status TEXT DEFAULT 'tracked',
  source TEXT, first_seen TEXT, last_fetch TEXT);
CREATE TABLE IF NOT EXISTS actions(ts TEXT, kind TEXT, comment_id TEXT, detail TEXT);
CREATE TABLE IF NOT EXISTS quota(day TEXT PRIMARY KEY, units INTEGER);
CREATE TABLE IF NOT EXISTS state(key TEXT PRIMARY KEY, value TEXT);
CREATE INDEX IF NOT EXISTS ix_comments_video ON comments(video_id);
CREATE INDEX IF NOT EXISTS ix_comments_parent ON comments(parent_id);
"""

if __name__ == "__main__":
    con = db()
    con.executescript(SCHEMA)
    con.commit()
    print(f"Database ready: {DB_PATH}")
