"""Shared helpers: paths, profile, database, YouTube client, quota guard.

All runtime data lives under HOME (default: the repo folder). `scripts/demo.py` sets
REPLYDNA_HOME=demo-run so the demo never touches your real data.
"""
import datetime as dt
import json
import os
import sqlite3
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
HOME = Path(os.environ.get("REPLYDNA_HOME") or ROOT).resolve()
CONFIG = HOME / "config"
SECRETS = HOME / "secrets"
DATA = HOME / "data"
WORK = HOME / "work"
INBOX = HOME / "inbox"
REPORTS = HOME / "reports"
LOGS = HOME / "logs"
DB_PATH = DATA / "youtube.db"
TOKEN = SECRETS / "token.json"
CLIENT_SECRET = SECRETS / "client_secret.json"
SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]

for d in (DATA, WORK, INBOX, REPORTS, LOGS, SECRETS):
    d.mkdir(parents=True, exist_ok=True)


def profile():
    p = CONFIG / "profile.yaml"
    if not p.exists():
        raise SystemExit("config/profile.yaml not found. Open this folder in Claude Code and type: start")
    return yaml.safe_load(p.read_text())


def asset(name):
    """Creator assets (logo.png / creator.jpg) live in HOME/assets, falling back to the repo's assets/."""
    for base in (HOME / "assets", ROOT / "assets"):
        for ext in ("", ".png", ".jpg", ".jpeg", ".webp"):
            f = base / f"{name}{ext}"
            if f.exists() and f.is_file():
                return f
    return None


def now_iso():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def today():
    return dt.date.today().isoformat()


def db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def log_action(con, kind, comment_id, detail=""):
    con.execute("INSERT INTO actions(ts, kind, comment_id, detail) VALUES (?,?,?,?)", (now_iso(), kind, comment_id, detail))
    with open(LOGS / "actions.log", "a") as f:
        f.write(f"{now_iso()}\t{kind}\t{comment_id}\t{detail}\n")


# ---------------- quota (YouTube Data API: 10,000 units/day by default; we stop at the profile cap)
COST = {"list": 1, "insert": 50, "moderate": 50, "delete": 50}


def quota_used(con):
    r = con.execute("SELECT units FROM quota WHERE day=?", (today(),)).fetchone()
    return r["units"] if r else 0


def quota_spend(con, kind, n=1):
    cap = profile().get("quota_daily_cap", 9000)
    need = COST[kind] * n
    used = quota_used(con)
    if used + need > cap:
        raise SystemExit(f"Quota guard: {used} units used today, {need} more needed, cap is {cap}. "
                         "The YouTube quota resets at midnight Pacific Time.")
    con.execute("INSERT INTO quota(day, units) VALUES (?, ?) ON CONFLICT(day) DO UPDATE SET units = units + ?", (today(), need, need))
    con.commit()


# ---------------- YouTube client (OAuth token from yt_auth.py)
def youtube():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    if not TOKEN.exists():
        raise SystemExit("No YouTube login yet. Run: .venv/bin/python scripts/yt_auth.py")
    creds = Credentials.from_authorized_user_file(str(TOKEN), SCOPES)
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception:
                raise SystemExit("YouTube login expired or was revoked. Run again: .venv/bin/python scripts/yt_auth.py "
                                 "(until then, reading comments still works with --source public)")
            TOKEN.write_text(creds.to_json())
        else:
            raise SystemExit("YouTube login expired. Run again: .venv/bin/python scripts/yt_auth.py")
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def assert_own_channel(yt):
    """Safety: never post or moderate unless the logged-in channel is the profile's channel."""
    me = yt.channels().list(part="id,snippet", mine=True).execute().get("items", [])
    want = profile()["channels"][0]["channel_id"]
    if not me or me[0]["id"] != want:
        got = me[0]["snippet"]["title"] if me else "no channel"
        raise SystemExit(f"Stop: you are logged in as '{got}', but the profile channel is {want}. "
                         "ReplyDNA never posts or moderates from the wrong channel.")


def read_jsonl(path):
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def write_jsonl(path, rows):
    with open(path, "w") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
