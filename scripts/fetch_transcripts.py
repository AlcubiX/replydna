"""Voice DNA, step 1: download the auto-captions of your latest videos (no login, no quota).

  .venv/bin/python scripts/fetch_transcripts.py                  # latest 20 videos
  .venv/bin/python scripts/fetch_transcripts.py --videos 40 --langs en,hi
Files go to data/transcripts/<video_id>.<lang>.json3. Already-downloaded videos are skipped.
Then run scripts/voice_stats.py.
"""
import argparse
import random
import time

from common import DATA, profile

OUT = DATA / "transcripts"


def main():
    import yt_dlp

    p = profile()
    ap = argparse.ArgumentParser()
    ap.add_argument("--videos", type=int, default=20)
    ap.add_argument("--langs", default=",".join(p.get("transcript_langs") or ["en"]))
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    langs = [x.strip() for x in a.langs.split(",") if x.strip()]
    handle = p["channels"][0]["handle"]
    with yt_dlp.YoutubeDL({"extract_flat": True, "playlistend": a.videos, "quiet": True, "no_warnings": True}) as y:
        entries = (y.extract_info(f"https://www.youtube.com/{handle}/videos", download=False).get("entries") or [])[:a.videos]
    opts = {"skip_download": True, "writeautomaticsub": True, "writesubtitles": True, "subtitleslangs": langs + [f"{x}-orig" for x in langs],
            "subtitlesformat": "json3", "outtmpl": str(OUT / "%(id)s.%(ext)s"), "quiet": True, "no_warnings": True, "ignoreerrors": True}
    got = skipped = 0
    with yt_dlp.YoutubeDL(opts) as y:
        for e in entries:
            if list(OUT.glob(f"{e['id']}.*json3")):
                skipped += 1
                continue
            try:
                y.download([f"https://www.youtube.com/watch?v={e['id']}"])
            except Exception as ex:  # 429 = YouTube asks us to slow down
                print(f"skip {e['id']}: {str(ex)[:90]}")
                if "429" in str(ex):
                    print("YouTube asked to slow down. Waiting 60 s ...")
                    time.sleep(60)
                continue
            if list(OUT.glob(f"{e['id']}.*json3")):
                got += 1
            time.sleep(random.uniform(3, 6))  # polite pace
    total = len(list(OUT.glob("*.json3")))
    print(f"{got} new transcripts · {skipped} already there · {total} in {OUT}")
    if not total:
        print("No captions found. Try another language code, e.g. --langs hi or --langs es")


if __name__ == "__main__":
    main()
