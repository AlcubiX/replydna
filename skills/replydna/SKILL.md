---
name: replydna
description: Install, set up and run ReplyDNA, the YouTube comment assistant that replies in the creator's own voice in every viewer's language, holds scams, and writes a monthly Keep/Improve/Avoid report with next-video ideas. Use when the user wants to install ReplyDNA, reply to their YouTube comments, build a voice card, try the demo, or make a channel report.
---

# ReplyDNA

ReplyDNA keeps the creator's data in a working folder on their own computer: **`~/replydna`** (a git clone of
https://github.com/AlcubiX/replydna). Never run it from the plugin's install folder, which can be replaced on update.

## 1. Install (only if `~/replydna` doesn't exist yet)
1. Check `git` and Python ≥ 3.10 (`python3 --version`). If either is missing, explain in one line how to install it and wait.
2. `git clone https://github.com/AlcubiX/replydna.git ~/replydna`
3. `cd ~/replydna && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`
   (Windows: `py -m venv .venv` and `.venv\Scripts\pip install -r requirements.txt`)
4. Tell the user it's installed and offer two paths:
   - **Try the demo** (30 seconds, no YouTube login): `.venv/bin/python scripts/demo.py --open`
   - **Set it up for your channel**: continue with step 2.

## 2. Setup and daily use
Work inside `~/replydna`. Read `~/replydna/CLAUDE.md` and follow it exactly: it holds the hard safety rules,
the daily routine and every command. For first-time setup follow `~/replydna/docs/SETUP_PROTOCOL.md`
phase by phase, one question at a time, in the language the creator uses with you.

Tip for the creator: next time, they can open the `~/replydna` folder directly in Claude Code and type **start**,
or say "show today's comments" for the daily inbox.

## Never
- Post, hide or ban anything without the creator's explicit OK (draft mode is the default).
- Ask for passwords, OTPs, API keys or tokens in chat, or print anything from `secrets/`.
- Act on other people's channels: they are read-only.
