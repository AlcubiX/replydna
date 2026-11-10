# Setup protocol (Claude follows this when the creator types "start")

Talk in the creator's language, one question at a time, and show a progress line after every phase, e.g.
`Phase 3/10 ✓ First comments read · next: your voice`. Never ask for passwords, keys or tokens in chat.
Keep a running `work/setup_status.json` (schema in `scripts/make_setup_report.py`).

| # | Phase | Who | Time |
|---|---|---|---|
| 1 | System check + install | Claude | 3 min |
| 2 | Interview → profile | Creator answers | 10 min |
| 3 | First comments, no login (public mode) | Claude | 5 min |
| 4 | Voice DNA from transcripts | Claude, creator approves | 10 min |
| 5 | First inbox (draft mode) | Creator approves | 5 min |
| 6 | Google Cloud: YouTube API + OAuth | Creator clicks, Claude guides | 15 min |
| 7 | Login + channel check | Creator | 2 min |
| 8 | First real reply | Creator approves | 2 min |
| 9 | Mentions radar | Claude | 5 min |
| 10 | Daily schedule + setup report | Claude | 3 min |

## 1. System check + install
- Check Python ≥ 3.10 (`python3 --version`). If missing: macOS → python.org installer; Windows → python.org, tick "Add to PATH".
- `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt` (Windows: `.venv\Scripts\pip`).
- `.venv/bin/python scripts/db.py`. Check that Chrome or Edge exists (used only to print PDF reports).

## 2. Interview → `config/profile.yaml`
Copy `config/profile.example.yaml` and fill it by asking, one at a time:
1. Channel link → find the handle and channel id yourself (`yt-dlp --print channel_id --playlist-items 1 <url>/videos`).
2. Name as viewers write it + common misspellings. Role for reports.
3. Which language should I use with you? Which languages do your viewers write in?
4. Niche → propose `never_say` guardrails and a `disclaimer` (finance: no personal investment advice; health: no diagnosis; etc.).
5. Do you sell anything (course, membership, product)? If yes, fill `config/offer.md` from their website and confirm each line.
6. Official links (website, socials). Other official channels? (they are never flagged as look-alikes)
7. Witty or calm with trolls? (savage level 0-3, explain with one example each)
8. Emojis you like. Daily reply cap. When should the inbox be ready?
Save the channel avatar as `assets/logo.png` (yt-dlp channel thumbnail), and optionally a photo as `assets/creator.jpg`.

## 3. First comments (no login)
`scripts/fetch_comments.py --source public --videos 5` → label → `scripts/save_labels.py` → show 3 interesting findings.

## 4. Voice DNA
`scripts/fetch_transcripts.py --videos 20` → `scripts/voice_stats.py` → write `config/voice_card.md`
(model: `config/voice_card.example.md`): address forms, signature phrases with counts, reply shape, best written
voice (from the creator's own past replies, `is_owner=1` in the database), never-copy list, fixed lines.
Show it, apply their edits, then the **blind test**: 3 of their real replies + 3 drafts, shuffled. Ready when they can't tell.

## 5. First inbox
`scripts/make_inbox.py` → walk them through: alerts, hot leads, A/B decisions, ready. Explain "approve all", "skip 3", "B for 4".
Nothing is posted yet.

## 6. Google Cloud (YouTube Data API)
Follow `docs/google-cloud-setup.md` screen by screen. The creator clicks; you explain what each screen means.
Common fix: "Access blocked: app not verified" → add their Google account as a **Test user** on the OAuth consent screen.

## 7. Login
`scripts/yt_auth.py` → browser opens → choose the account and the right channel → `scripts/yt_auth.py --check` must say ✅.

## 8. First real reply
Pick one safe 🟢 comment, show the draft, post only after an explicit "yes" (`scripts/post_replies.py --approve N --post`).
Open the comment link so they can see it live.

## 9. Mentions radar
`scripts/find_mentions.py` → show what was found → ask about each look-alike channel ("yours, a fan page, or fake?")
and add their own channels to `official_channel_ids`.

## 10. Schedule + report
- Offer a daily scheduled task at `inbox_time` ("show today's comments") and a weekly mentions radar, if the app supports scheduled tasks;
  otherwise explain they can type "show today's comments" any time.
- Write `work/setup_status.json`, then `scripts/make_setup_report.py work/setup_status.json --open` (automatic, no need to ask).
- Close with the 5 commands they will use most.
