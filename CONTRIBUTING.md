# Contributing to ReplyDNA

Thanks for helping creators spend less time in their comments! 🧬

## Quick start for contributors
```bash
git clone https://github.com/AlcubiX/replydna.git && cd replydna
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python scripts/demo.py --open     # full run on fictional data, no YouTube login
```

## Ground rules
- **Claude thinks, scripts move data.** Keep scripts small, readable and dependency-light.
- **Safety rules are not optional.** Draft mode by default; 🔴 alerts are never auto-answered; other channels are read-only;
  posting and moderation always check that the logged-in channel is the creator's own.
- **Privacy first.** Never commit real comments, viewer names, tokens, `client_secret.json` or anything from `secrets/`.
  Use the fictional demo data in `examples/demo/` for tests and screenshots.
- **English first** in code, docs and UI. Replies themselves always mirror the commenter's language.
- **Print-safe reports.** No blurred `box-shadow`, CSS `filter` or opacity on gradients in PDF styles
  (Mac Preview draws them as solid boxes). Check PDFs in Preview, not just Chrome.

## Pull requests
1. Open an issue first for anything bigger than a small fix.
2. Keep PRs focused; run `python scripts/demo.py` before pushing (CI runs it too).
3. Describe what changed and why; screenshots help for report or inbox changes.

By contributing you agree that your contribution is licensed under the MIT License and that you follow our [Code of Conduct](CODE_OF_CONDUCT.md).
