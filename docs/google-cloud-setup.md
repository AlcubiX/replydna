# Google Cloud setup (YouTube Data API) · ~15 minutes, free

You need this only to **post replies** and **moderate** on your channel. Reading comments works without it
(`--source public`). No credit card or billing is needed.

1. **Create a project.** Open <https://console.cloud.google.com/> with the Google account that owns your channel →
   project picker (top bar) → **New project** → name it `ReplyDNA` → **Create** → make sure it is selected.
2. **Turn on the API.** **APIs & Services → Library** → search **YouTube Data API v3** → **Enable**.
3. **Consent screen.** **APIs & Services → OAuth consent screen** (or **Google Auth Platform → Branding**):
   - App name `ReplyDNA`, your email as support and developer contact → Save.
   - **Audience**: User type **External**, keep it in **Testing**.
   - **Test users → Add users** → add the Google account that owns your channel. *(Skipping this causes "Access blocked".)*
4. **Credentials.** **APIs & Services → Credentials** (or **Clients**) → **Create credentials → OAuth client ID** →
   Application type **Desktop app** → name `ReplyDNA desktop` → **Create** → **Download JSON**.
5. **Put the file in place.** Rename it to `client_secret.json` and move it to the `secrets/` folder of ReplyDNA.
   It stays on your computer. Never share it or paste it into a chat.
6. **Log in.** `.venv/bin/python scripts/yt_auth.py` → a browser opens → pick your account → if Google says
   "Google hasn't verified this app", click **Continue** (it's your own app) → allow access → pick your **channel**
   (brand accounts show a channel picker).
7. **Check.** `.venv/bin/python scripts/yt_auth.py --check` should print `✅ Correct channel`.

## Quota
The free quota is 10,000 units per day. Reading 100 comments costs 1 unit; posting a reply costs 50 units
(~180 replies/day max). ReplyDNA stops at 9,000 on purpose (`quota_daily_cap` in the profile).
The quota resets at midnight Pacific Time.

## Undo everything
Google Account → Security → **Third-party apps with account access** → ReplyDNA → **Remove access**.
Then delete the `secrets/` folder.
