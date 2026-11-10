"""Try ReplyDNA in 30 seconds, without a YouTube login.

Builds a full run on fictional comments ("Maya Builds", a DIY channel, in 5 languages):
database → rule filter → Claude-style labels and drafts → daily inbox → interactive report + PDF.
Everything goes into demo-run/ and never touches your real data.

Run: .venv/bin/python scripts/demo.py [--open]
"""
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEMO = ROOT / "examples" / "demo"
RUN = ROOT / "demo-run"


def run(script, *args):
    env = dict(os.environ, REPLYDNA_HOME=str(RUN))
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / script), *args], env=env, capture_output=True, text=True)
    print(f"  $ {script} {' '.join(args)}".rstrip())
    out = (r.stdout + r.stderr).strip()
    if out:
        print("    " + out.replace("\n", "\n    "))
    if r.returncode:
        raise SystemExit(f"{script} failed")
    return r.stdout


def main():
    shutil.rmtree(RUN, ignore_errors=True)
    (RUN / "config").mkdir(parents=True)
    shutil.copy(DEMO / "profile.yaml", RUN / "config" / "profile.yaml")
    os.environ["REPLYDNA_HOME"] = str(RUN)
    sys.path.insert(0, str(ROOT / "scripts"))
    print("ReplyDNA demo · fictional channel 'Maya Builds' · 5 languages\n")
    run("db.py")

    from common import db, now_iso  # noqa: E402  (after REPLYDNA_HOME is set)
    from fetch_comments import prefilter, upsert_comment  # noqa: E402

    con = db()
    now = dt.datetime.now(dt.timezone.utc)
    for vid, title in json.loads((DEMO / "videos.json").read_text()).items():
        con.execute("INSERT OR REPLACE INTO videos(id, title, published_at) VALUES (?,?,?)", (vid, title, now.isoformat()))
    rows = [json.loads(line) for line in (DEMO / "comments.jsonl").read_text().splitlines() if line.strip()]
    for c in rows:
        upsert_comment(con, {"id": c["id"], "video_id": c["video_id"], "parent_id": c.get("parent_id"), "author_name": c["author"],
                             "author_channel_id": "UC_DEMO_CHANNEL_000000000" if c.get("is_owner") else f"UC_viewer_{c['id']}",
                             "text": c["text"], "like_count": c["likes"],
                             "published_at": (now - dt.timedelta(days=c["days_ago"])).strftime("%Y-%m-%dT%H:%M:%SZ"),
                             "is_owner": c.get("is_owner", 0), "fetched_at": now_iso(), "source": "demo"})
    handled = prefilter(con)
    con.commit()
    print(f"  loaded {len(rows)} fictional comments · {handled} handled by the free rule filter (emoji, 'nice', phone/link spam)")

    run("save_labels.py", str(DEMO / "labels.jsonl"))   # in real use, Claude writes these labels + drafts
    run("make_inbox.py")
    run("report_data.py")
    data = sorted((RUN / "reports").glob("data-*.json"))[-1]
    nar = json.loads((DEMO / "narrative.json").read_text())
    nar["month"] = dt.date.today().strftime("%b %Y")
    nar_path = RUN / "reports" / f"narrative-{dt.date.today():%Y-%m}.json"
    nar_path.write_text(json.dumps(nar, ensure_ascii=False, indent=1))
    run("make_report.py", str(data), str(nar_path), *(["--open"] if "--open" in sys.argv else []))
    inbox = sorted((RUN / "inbox").glob("*.md"))[-1]
    print(f"\nDone. Open these:\n  inbox  → {inbox}\n  report → {sorted((RUN / 'reports').glob('report-*.html'))[-1]}")
    print("Nothing was posted anywhere. To use it on your own channel: open this folder in Claude Code and type: start")


if __name__ == "__main__":
    main()
