"""One-time YouTube login (OAuth, installed-app flow). Your token stays in secrets/ on your computer.

Needs secrets/client_secret.json (Google Cloud → APIs & Services → Credentials → OAuth client → Desktop app → Download JSON).
A browser opens: pick the Google account that owns your channel, then pick the channel itself.
Run:  .venv/bin/python scripts/yt_auth.py          (login + check)
      .venv/bin/python scripts/yt_auth.py --check  (only check the saved login)
"""
import sys

from common import CLIENT_SECRET, SCOPES, TOKEN, profile, youtube


def login():
    from google_auth_oauthlib.flow import InstalledAppFlow

    if not CLIENT_SECRET.exists():
        raise SystemExit("secrets/client_secret.json not found. Download the Desktop-app JSON from Google Cloud and put it there "
                         "(see docs/google-cloud-setup.md).")
    flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET), SCOPES)
    creds = flow.run_local_server(port=0, prompt="consent", access_type="offline")
    TOKEN.write_text(creds.to_json())
    TOKEN.chmod(0o600)


def check():
    yt = youtube()
    items = yt.channels().list(part="snippet", mine=True).execute().get("items", [])
    if not items:
        raise SystemExit("This login has no YouTube channel. Log in again and choose the right channel.")
    ch = items[0]
    expected = profile()["channels"][0]["channel_id"]
    ok = ch["id"] == expected
    print(f"Logged in as channel: {ch['snippet']['title']} ({ch['id']})")
    print("✅ Correct channel" if ok else f"⚠️ This is not the profile channel ({expected}). Replies and moderation will refuse to run.")
    return ok


if __name__ == "__main__":
    if "--check" not in sys.argv:
        login()
    check()
