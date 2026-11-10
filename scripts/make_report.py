"""Monthly report: an interactive HTML page + a 16:9 PDF deck (dark + electric-violet "annual report" style).

Inputs
  1. reports/data-YYYY-MM-DD.json   ← from scripts/report_data.py (numbers)
  2. reports/narrative-YYYY-MM.json ← written by Claude (words), schema below
Output (both, every time)
  reports/report-YYYY-MM.html  ← INTERACTIVE report (click, filters, A/B replies, checklist). Open this one.
  reports/report-YYYY-MM.pdf   ← downloadable PDF, linked from the HTML's "Download PDF" button.

Narrative schema (write it in the creator's language; every claim backed by a number from the data file):
{
  "month": "Nov 2026",
  "headline": ["Beyond views,", "towards trust."],             # 2 short lines, the first is shown dimmed
  "summary": "1-2 lines: the single biggest truth of the month",
  "highlight": {"value": "1.6x", "title": "...", "text": "...", "foot": "how it was measured (sample size)"},
  "voices": [{"q": "a real comment (no name)", "cat": "Valid criticism", "foot": "12 similar comments"}],   # max 4
  "abi": {"ability": ["action", "..."], "integrity": ["..."], "benevolence": ["..."]},                    # 2-3 each
  "risk_notes": ["1 line each, max 4"],
  "video_ideas": ["a video idea from viewers' questions", "..."],                                       # max 8
  "keep": [{"t": "title", "d": "1 line", "e": "evidence"}], "improve": [...], "avoid": [...],            # 3 each
  "next": [{"k": "Week 1", "t": "title", "items": ["...", "..."]}],                                      # 4 blocks
  "cards": [...]            # optional: reply examples for the A/B demo (default: best drafts from the database)
}
Run: .venv/bin/python scripts/make_report.py reports/data-2026-11-30.json reports/narrative-2026-11.json [--open]
"""
import html
import json
import sqlite3
import sys
from pathlib import Path

from common import DB_PATH, REPORTS
from html_report import brand, open_file, print_pdf, render_html

E = html.escape
CAT_NAMES = {
    "praise": "Genuine praise", "generic_praise": "Quick praise", "superfan": "Superfans", "beginner_question": "Beginner questions",
    "advanced_question": "Advanced questions", "advice_request": "Asks for personal advice", "offer_question": "Questions about your offer",
    "wants_to_learn": "Wants to learn", "valid_criticism": "Valid criticism", "joke_but_valid": "Joke, but valid",
    "factual_correction": "Caught a mistake", "blame": "Blames you", "distress": "Distress", "selling_accusation": "\"Just selling\"",
    "fraud_claim": "Fraud claims", "troll": "Trolls", "competitor_comparison": "Comparisons", "success_story": "Success stories",
    "topic_request": "Topic requests", "outdated_info": "Outdated info", "customer_complaint": "Customer complaints",
    "legal_threat": "Legal threats", "scam": "Scam bots", "impersonation": "Fake accounts", "abuse": "Abuse", "spam": "Spam",
    "personal_info": "Personal info", "other": "Other"}
RISKS = [("Fraud claims", "fraud_claim"), ("Fake accounts", "impersonation"), ("Scam bots", "scam"),
         ("Legal threats", "legal_threat"), ("Distress", "distress"), ("Personal info", "personal_info")]
LANG_COLORS = ["#3D4BFF", "#8B5CFF", "#C9B8FF", "#5BC0FF", "#2ED4B8", "#D9D9E3"]

# Print-safe on purpose: no blurred box-shadows, no CSS filters, no opacity on gradients
# (Mac Preview / iPhone Files draw those as solid boxes). Glows are plain radial gradients.
CSS = """
@page{size:1920px 1080px;margin:0}*{box-sizing:border-box}html,body{margin:0;padding:0;background:#000}
body{font-family:"Helvetica Neue",Arial,"Kohinoor Devanagari","Nirmala UI","Noto Sans",sans-serif;-webkit-print-color-adjust:exact;print-color-adjust:exact}
.s{width:1920px;height:1080px;position:relative;overflow:hidden;break-after:page;padding:150px 120px 90px}
.dark{background:#07070B;color:#fff}.light{background:#F6F6F9;color:#0B0B12}
.glow{position:absolute;left:-10%;right:-10%;bottom:-420px;height:640px;background:radial-gradient(50% 55% at 30% 50%,rgba(61,75,255,.76),rgba(61,75,255,0) 70%),radial-gradient(45% 55% at 72% 55%,rgba(123,60,255,.72),rgba(123,60,255,0) 70%)}
.light .glow{background:radial-gradient(50% 55% at 30% 50%,rgba(61,75,255,.29),rgba(61,75,255,0) 70%),radial-gradient(45% 55% at 72% 55%,rgba(123,60,255,.27),rgba(123,60,255,0) 70%)}
.top{position:absolute;left:120px;right:120px;top:52px;display:flex;justify-content:space-between;align-items:center;font-size:20px;z-index:2}
.brand{display:flex;align-items:center;gap:14px;font-weight:600}.top img{width:44px;height:44px;border-radius:10px;object-fit:cover}
.dark .top{color:#B9B9C8}.light .top{color:#55556A}.pg{padding:6px 14px;border-radius:99px;border:1px solid currentColor;margin-left:18px}
.pill{display:inline-block;background:#3D4BFF;color:#fff;font-weight:600;font-size:20px;padding:9px 18px;border-radius:8px}
.mega{font-size:140px;line-height:.93;letter-spacing:-.045em;font-weight:700;margin:34px 0 0}
.h2{font-size:80px;line-height:1;letter-spacing:-.04em;font-weight:700;margin:16px 0 0;position:relative;z-index:1}
.dim{color:#5D5D6E}.diml{color:#B4B4C3}.blue{color:#5B57FF}
.lead{font-size:30px;line-height:1.4;color:#A9A9BC;max-width:900px;margin:30px 0 0}
.body{font-size:24px;line-height:1.5;color:#45455A;margin:16px 0 0;position:relative;z-index:1}.dark .body{color:#A9A9BC}
.giant{font-size:240px;line-height:.9;font-weight:800;letter-spacing:-.06em;color:#5B57FF;margin-top:30px}
.cov-l{position:absolute;left:120px;top:200px;width:1000px;z-index:2}
.meta{display:flex;gap:30px;align-items:center;margin-top:60px}.meta .k{font-size:17px;color:#7A7A8E;text-transform:uppercase;letter-spacing:.12em}.meta .v{font-size:26px;font-weight:650;margin-top:4px}
.meta img{width:84px;height:84px;border-radius:18px;object-fit:cover}.vr{width:1px;height:56px;background:#2E2E3A}
.cov-g{position:absolute;right:20px;top:50px;width:800px;height:1000px;background:radial-gradient(closest-side,rgba(91,70,255,.45),rgba(91,70,255,0))}
.cov-r{position:absolute;right:120px;top:150px;width:600px;height:800px;border-radius:30px;overflow:hidden}
.cov-r img{width:100%;height:100%;object-fit:cover;object-position:50% 20%}
.cov-mark{position:absolute;right:220px;top:300px;width:400px;height:400px;border-radius:90px;object-fit:cover;z-index:1}
.tag{position:absolute;left:24px;right:24px;bottom:24px;background:rgba(8,8,14,.8);border-radius:18px;padding:18px 22px}.tag b{font-size:30px;display:block}.tag span{font-size:18px;color:#B9B9C8}
.kpis{display:grid;grid-template-columns:repeat(5,1fr);gap:24px;margin-top:50px;position:relative;z-index:1}
.kpi{background:#111118;border:1px solid #23232E;border-radius:22px;padding:30px}.kpi .n{font-size:66px;font-weight:800;letter-spacing:-.045em;line-height:1}.kpi .l{font-size:20px;color:#9A9AAF;margin-top:10px}
.two{display:grid;grid-template-columns:1fr 1fr;gap:100px;position:relative;z-index:1}
.hb{display:grid;grid-template-columns:330px 1fr 70px;align-items:center;gap:16px;font-size:21px;margin-bottom:11px}
.ht{height:16px;background:#E4E4EE;border-radius:5px;overflow:hidden}.dark .ht{background:#1B1B26}
.hf{height:100%;background:#0B0B12;border-radius:5px}.dark .hf{background:#4A4A5E}.hf.on{background:linear-gradient(90deg,#3D4BFF,#8B5CFF)}.hv{text-align:right;font-weight:700}
.card{background:#fff;border:1px solid #E1E1EA;border-radius:24px;padding:26px 30px;margin-bottom:24px}.ck{font-size:20px;text-transform:uppercase;letter-spacing:.1em;color:#6A6A80;font-weight:600;margin-bottom:14px}
.seg{display:flex;gap:4px;height:76px;border-radius:12px;overflow:hidden}.seg div{display:flex;flex-direction:column;justify-content:center;padding:0 14px;min-width:0}.seg b{font-size:26px}.seg span{font-size:15px;white-space:nowrap;overflow:hidden}
.voices{display:grid;grid-template-columns:repeat(4,1fr);gap:26px;margin-top:60px;position:relative;z-index:1}
.vc{background:#111118;border:1px solid #23232E;border-radius:26px;padding:30px;min-height:460px;display:flex;flex-direction:column}
.vc .cat{align-self:flex-start;font-size:18px;background:#3D4BFF;padding:6px 12px;border-radius:8px;font-weight:600}.vc .q{font-size:30px;line-height:1.3;margin-top:28px;flex:1}.vc .f{font-size:19px;color:#8A8AA0;border-top:1px solid #23232E;padding-top:16px}
.abi{display:grid;grid-template-columns:repeat(3,1fr);gap:30px;margin-top:46px}.ab{background:#fff;border:1px solid #E1E1EA;border-radius:26px;padding:34px 36px}
.ab.mid{background:#0B0B12;color:#fff;border:none}.ab .n{font-size:110px;font-weight:800;letter-spacing:-.06em;line-height:1;color:#3D4BFF}.ab.mid .n{color:#8B8BFF}
.ab .t{font-size:40px;font-weight:700;margin-top:6px}.ab .q{font-size:24px;color:#6A6A80;margin-top:6px}.ab ul{margin:22px 0 0;padding-left:24px;font-size:23px;line-height:1.55}
.risks{display:grid;grid-template-columns:repeat(3,1fr);gap:24px;margin-top:44px;position:relative;z-index:1}.rk{background:#111118;border:1px solid #23232E;border-radius:22px;padding:28px}
.rk .n{font-size:84px;font-weight:800;letter-spacing:-.05em;line-height:1}.rk .l{font-size:22px;color:#A9A9BC;margin-top:8px}
.notes{margin-top:30px;font-size:24px;line-height:1.5;color:#C9C9D6;position:relative;z-index:1}.notes div{padding:10px 0;border-top:1px solid #23232E}
.ideas{columns:2;column-gap:60px;margin-top:40px;font-size:28px;line-height:1.4}.ideas div{break-inside:avoid;padding:14px 0;border-bottom:1px solid #DCDCE6;display:flex;gap:18px}
.ideas b{color:transparent;-webkit-text-stroke:1.5px #3D4BFF;font-size:40px;font-weight:800;min-width:70px;line-height:1}
.kia{display:grid;grid-template-columns:repeat(3,1fr);gap:30px;margin-top:44px}.kc{background:#fff;border:1px solid #E1E1EA;border-radius:26px;padding:28px 32px}
.kc h4{font-size:40px;margin:0;border-bottom:4px solid;padding-bottom:12px;letter-spacing:-.03em}.ki{padding:16px 0;border-bottom:1px solid #EDEDF3}.ki:last-child{border:none}
.ki b{font-size:25px}.ki p{font-size:20px;line-height:1.45;color:#45455A;margin:6px 0}.ki em{font-style:normal;font-size:17px;color:#7A7A8E}
.rbar{display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin-top:50px}.rbar div{height:14px;border-radius:7px}
.road{display:grid;grid-template-columns:repeat(4,1fr);gap:28px;margin-top:22px;position:relative;z-index:1}.rd{background:#111118;border:1px solid #23232E;border-radius:24px;padding:34px;min-height:420px}
.rd .k{font-size:22px;color:#8B8BFF;font-weight:600;text-transform:uppercase}.rd .t{font-size:42px;font-weight:700;margin-top:6px;letter-spacing:-.03em}.rd ul{margin:22px 0 0;padding-left:24px;font-size:25px;line-height:1.6;color:#C9C9D6}
.close{display:flex;flex-direction:column;align-items:center;justify-content:center;height:100%;position:relative;z-index:1;margin-top:-40px;text-align:center}
.close img{width:170px;height:170px;border-radius:36px;object-fit:cover}
.made{position:absolute;right:120px;bottom:40px;font-size:18px;color:#6E6E82;z-index:2}
"""


def compact(n):
    n = float(n or 0)
    for div, suf in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
        if n >= div:
            return f"{n / div:.1f}".rstrip("0").rstrip(".") + suf
    return f"{n:.0f}"


def lang_parts(lang):
    """Top 5 named languages + one "Other" bucket (unknown / emoji-only / the long tail)."""
    named = sorted(((k, v) for k, v in lang.items() if k and k != "other"), key=lambda x: -x[1])
    top = named[:5]
    rest = sum(v for _, v in named[5:]) + sum(v for k, v in lang.items() if not k or k == "other")
    parts = [(k.capitalize(), v, LANG_COLORS[i]) for i, (k, v) in enumerate(top)]
    if rest:
        parts.append(("Other", rest, LANG_COLORS[5]))
    return parts


def build(data, nar):
    b = brand()
    has_m = bool((data.get("mentions") or {}).get("videos"))
    N = 12 if has_m else 11
    logo = f'<img src="{b["logo"]}">' if b["logo"] else ""

    def top(i, sec):
        return (f'<div class="top"><div class="brand">{logo}{E(b["brand"])} · Monthly Report · {E(nar["month"])}</div>'
                f'<div>{E(sec)}<span class="pg">{i:02d} / {N:02d}</span></div></div>')

    def slide(i, sec, body, dark=True):
        return f'<section class="s {"dark" if dark else "light"}"><div class="glow"></div>{top(i, sec)}{body}</section>'

    def hbar(label, v, mx, on=False):
        return (f'<div class="hb"><div>{E(label)}</div><div class="ht"><div class="hf{" on" if on else ""}" '
                f'style="width:{v / max(mx, 1) * 100:.1f}%"></div></div><div class="hv">{v}</div></div>')

    def seg(parts):
        t = sum(v for _, v, _ in parts) or 1
        return '<div class="seg">' + "".join(f'<div style="flex:{max(v, 1)};background:{c}"><b>{v / t * 100:.0f}%</b><span>{E(lbl)}</span></div>'
                                             for lbl, v, c in parts) + "</div>"

    total = data["total_comments"]
    cats = sorted(((CAT_NAMES.get(k, k), v) for k, v in data["by_category"].items()), key=lambda x: -x[1])[:13]
    mx = max([v for _, v in cats] or [1])
    tone, abi, risks = data["by_tone"], data["by_abi"], data["risks"]
    S = []
    right = (f'<div class="cov-g"></div><div class="cov-r"><img src="{b["photo"]}"><div class="tag"><b>{E(b["creator"])}</b>'
             f'<span>{E(b["role"])} · {E(b["handle"])}</span></div></div>') if b["photo"] else \
            (f'<div class="cov-g"></div><img class="cov-mark" src="{b["logo"]}">' if b["logo"] else "")
    S.append(slide(1, "Cover", f'''<div class="cov-l"><div class="pill">Monthly Channel Report · {E(nar["month"])}</div>
      <div class="mega"><span class="dim">{E(nar["headline"][0])}</span><br>{E(nar["headline"][1])}</div><p class="lead">{E(nar["summary"])}</p>
      <div class="meta">{logo}<div><div class="k">Prepared for</div><div class="v">{E(b["creator"] or b["brand"])}</div></div><div class="vr"></div>
      <div><div class="k">Edition</div><div class="v">{E(nar["month"])}</div></div></div></div>{right}'''))
    S.append(slide(2, "At a glance", f'''<div class="h2"><span class="dim">This month</span> at a glance</div><div class="kpis">
      <div class="kpi"><div class="n">{total}</div><div class="l">Comments read</div></div><div class="kpi"><div class="n">{data["questions"]}</div><div class="l">Questions</div></div>
      <div class="kpi"><div class="n">{data["unanswered_questions"]}</div><div class="l">Unanswered</div></div><div class="kpi"><div class="n">{data["owner_replies"]}</div><div class="l">Your replies</div></div>
      <div class="kpi"><div class="n">{data["like_weighted_sentiment"]:+.2f}</div><div class="l">Mood (like-weighted)</div></div></div>
      <p class="body" style="margin-top:40px;max-width:1300px">Negative comments: {data["negative_share"] * 100:.0f}% (at least {data["negative_share_wilson_lower"] * 100:.0f}%, statistically).
      The mood score runs from -1 to +1, and comments with more likes count more.</p>'''))
    h = nar["highlight"]
    S.append(slide(3, "Highlight", f'''<div class="pill">Highlight of the month</div><div class="giant">{E(h["value"])}</div>
      <div class="h2" style="font-size:56px">{E(h["title"])}</div><p class="body" style="max-width:1300px">{E(h["text"])}</p>
      <p class="body" style="font-size:18px;color:#6E6E82">{E(h["foot"])}</p>'''))
    S.append(slide(4, "Audience", f'''<div class="two"><div><div class="h2"><span class="diml">What your</span><br>audience says</div>
      <div style="margin-top:30px">{"".join(hbar(lbl, v, mx, i == 0) for i, (lbl, v) in enumerate(cats))}</div></div>
      <div style="padding-top:20px"><div class="card"><div class="ck">Language</div>{seg(lang_parts(data["by_language"]))}</div>
      <div class="card"><div class="ck">Mood</div>{seg([("Positive", tone.get("positive", 0), "#2ED47A"), ("Neutral", tone.get("neutral", 0), "#C7C7D2"),
                                                       ("Negative", tone.get("negative", 0), "#FF4D5E")])}</div></div></div>''', dark=False))
    S.append(slide(5, "Voices", f'''<div class="h2"><span class="dim">Comments that</span> say it all</div><div class="voices">
      {"".join(f'<div class="vc"><div class="cat">{E(v["cat"])}</div><div class="q">"{E(v["q"])}"</div><div class="f">{E(v["foot"])}</div></div>'
               for v in nar.get("voices", [])[:4])}</div>'''))
    S.append(slide(6, "Trust scorecard", f'''<div class="h2">The <span class="blue">3 pillars</span> of trust</div><div class="abi">
      <div class="ab"><div class="n">{abi.get("ability", 0)}</div><div class="t">Ability</div><div class="q">"Do they know their stuff?"</div><ul>{"".join(f"<li>{E(x)}</li>" for x in nar["abi"]["ability"])}</ul></div>
      <div class="ab mid"><div class="n">{abi.get("integrity", 0)}</div><div class="t">Integrity</div><div class="q">"Are they honest?"</div><ul>{"".join(f"<li>{E(x)}</li>" for x in nar["abi"]["integrity"])}</ul></div>
      <div class="ab"><div class="n">{abi.get("benevolence", 0)}</div><div class="t">Benevolence</div><div class="q">"Do they care about me?"</div><ul>{"".join(f"<li>{E(x)}</li>" for x in nar["abi"]["benevolence"])}</ul></div></div>''', dark=False))
    S.append(slide(7, "Risk radar", f'''<div class="h2"><span class="dim">What's happening</span> around your name</div><div class="risks">
      {"".join(f'<div class="rk"><div class="n">{risks.get(k, 0)}</div><div class="l">{E(lbl)}</div></div>' for lbl, k in RISKS)}</div>
      <div class="notes">{"".join(f"<div>{E(x)}</div>" for x in nar.get("risk_notes", [])[:4])}</div>'''))
    S.append(slide(8, "Video ideas", f'''<div class="h2"><span class="diml">Viewers' questions =</span><br>your next videos</div><div class="ideas">
      {"".join(f"<div><b>{i + 1:02d}</b><span>{E(x)}</span></div>" for i, x in enumerate(nar.get("video_ideas", [])[:8]))}</div>''', dark=False))

    def kcol(t, c, items):
        return (f'<div class="kc"><h4 style="border-color:{c}"><span style="color:{c}">●</span> {t}</h4>' +
                "".join(f'<div class="ki"><b>{E(i["t"])}</b><p>{E(i["d"])}</p><em>{E(i["e"])}</em></div>' for i in items[:3]) + "</div>")
    S.append(slide(9, "Verdict", f'''<div class="h2">Keep <span class="diml">·</span> Improve <span class="diml">·</span> Avoid</div><div class="kia">
      {kcol("Keep", "#2ED47A", nar["keep"])}{kcol("Improve", "#7B3CFF", nar["improve"])}{kcol("Avoid", "#FF4D5E", nar["avoid"])}</div>''', dark=False))
    S.append(slide(10, "Next month", f'''<div class="h2"><span class="dim">Next month's</span> plan</div>
      <div class="rbar"><div style="background:#3D4BFF"></div><div style="background:#5A46FF"></div><div style="background:#7B3CFF"></div><div style="background:#A17BFF"></div></div>
      <div class="road">{"".join(f'<div class="rd"><div class="k">{E(x["k"])}</div><div class="t">{E(x["t"])}</div><ul>{"".join(f"<li>{E(i)}</li>" for i in x["items"])}</ul></div>'
                                  for x in nar.get("next", [])[:4])}</div>'''))
    m = data.get("mentions") or {}
    if has_m:
        mtop = sorted(m["list"], key=lambda v: (-(v["about"] > 0), -v["views"]))[:8]
        rows = "".join(f'<div class="hb" style="grid-template-columns:110px 1fr 150px;color:#D0D0DC"><b style="color:{"#FF7A88" if v["alert"] else "#fff"}">{compact(v["views"])}</b>'
                       f'<span>{E(v["channel"])} · {E(v["title"][:70])}</span><span style="text-align:right">{v["pos"]}+ / {v["neg"]}−</span></div>' for v in mtop)
        S.append(slide(11, "Mentions radar", f'''<div class="h2"><span class="dim">You, on</span> other channels</div>
          <div class="kpis"><div class="kpi"><div class="n">{m["videos"]}</div><div class="l">Videos</div></div><div class="kpi"><div class="n">{compact(m["views"])}</div><div class="l">Views</div></div>
          <div class="kpi"><div class="n">{m["about"]}</div><div class="l">Comments about you</div></div><div class="kpi"><div class="n">{round(m.get("reach_pos", 0) * 100)}%</div><div class="l">For you (reach-weighted)</div></div>
          <div class="kpi"><div class="n">{round(m.get("reach_neg", 0) * 100)}%</div><div class="l">Against (reach-weighted)</div></div></div><div style="margin-top:34px;position:relative;z-index:1">{rows}</div>'''))
    S.append(slide(N, "Thank you", f'''<div class="close">{logo}<div class="mega" style="text-align:center">See you<br><span class="blue">next month.</span></div>
      <p class="lead" style="text-align:center">{E(b["brand"])} · {E(nar["month"])}</p></div><div class="made">Made with ReplyDNA</div>'''))
    return (f'<!doctype html><html><head><meta charset="utf-8"><title>{E(b["brand"])} Report {E(nar["month"])}</title>'
            f'<style>{CSS}</style></head><body>{"".join(S)}</body></html>')


def cards_from_db(limit=6):
    """Best reply drafts of the month (anonymised) for the interactive A/B demo."""
    try:
        con = sqlite3.connect(DB_PATH)
        con.row_factory = sqlite3.Row
        rows = con.execute("""SELECT c.id, c.text, c.like_count, c.published_at, l.category, l.language,
                                     MAX(CASE WHEN d.option='A' THEN d.text END) AS a, MAX(CASE WHEN d.option='B' THEN d.text END) AS b
                              FROM drafts d JOIN comments c ON c.id=d.comment_id JOIN labels l ON l.comment_id=c.id
                              WHERE l.action IN ('reply','alert') AND d.status IN ('pending','approved','posted') AND COALESCE(c.scope,'own')='own'
                              GROUP BY c.id ORDER BY (b IS NOT NULL) DESC, c.like_count DESC LIMIT ?""", (limit,)).fetchall()
        return [{"comment_quote": r["text"][:220], "draft_reply": r["a"] or r["b"], "option_b": r["b"] if r["a"] else None,
                 "language": r["language"], "likes": r["like_count"], "category_label": CAT_NAMES.get(r["category"], r["category"]),
                 "handle": f"@viewer_{11 + i * 7}", "initial": "ARSKMP"[i % 6], "when": (r["published_at"] or "")[:10]}
                for i, r in enumerate(rows)]
    except Exception:
        return []


def interactive_data(data, nar, pdf_name):
    b = brand()
    total = data["total_comments"]
    tone, risks = data["by_tone"], data["risks"]
    cats = sorted(((CAT_NAMES.get(k, k), v) for k, v in data["by_category"].items()), key=lambda x: -x[1])[:14]
    return {
        "kind": "monthly", "id": "report-" + nar["month"], "title": "Monthly Report · " + nar["month"], "date": nar["month"],
        "pill": "Monthly Channel Report · " + nar["month"], "headline": nar["headline"], "summary": nar["summary"],
        "meta": [{"k": "Prepared for", "v": b["creator"] or b["brand"]}, {"k": "Edition", "v": nar["month"]}],
        "hero_stat": nar.get("hero_stat") or {"n": str(total), "l": "comments read"},
        "kpis": [{"n": str(total), "l": "Comments read"}, {"n": str(data["questions"]), "l": "Questions"},
                 {"n": str(data["unanswered_questions"]), "l": "Unanswered"}, {"n": str(data["owner_replies"]), "l": "Your replies"},
                 {"n": f'{data["like_weighted_sentiment"]:+.2f}', "l": "Mood (like-weighted)"}],
        "highlight": nar["highlight"], "total": total, "categories": [list(c) for c in cats],
        "hl_category": nar.get("hl_category") or CAT_NAMES["offer_question"],
        "language": [list(p) for p in lang_parts(data["by_language"])],
        "tone": [["Positive", tone.get("positive", 0), "#2ED47A"], ["Neutral", tone.get("neutral", 0), "#C7C7D2"],
                 ["Negative", tone.get("negative", 0), "#FF4D5E"]],
        "cards": nar.get("cards") or cards_from_db(), "voices": nar.get("voices", []),
        "abi_counts": data["by_abi"], "abi": nar.get("abi", {}),
        "risks": [[lbl, risks.get(k, 0)] for lbl, k in RISKS],
        "risk_notes": nar.get("risk_notes", []), "video_ideas": nar.get("video_ideas", []),
        "keep": nar.get("keep", []), "improve": nar.get("improve", []), "avoid": nar.get("avoid", []),
        "next_title": "Next month's plan", "next_items": [f'{x["k"]}: {i}' for x in nar.get("next", []) for i in x["items"]],
        "pdf": pdf_name, "mentions": data.get("mentions") or {}, "mentions_note": nar.get("mentions_note", []),
    }


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    data, nar = json.load(open(args[0])), json.load(open(args[1]))
    stem = "report-" + Path(args[1]).stem.replace("narrative-", "")
    deck = REPORTS / f".{stem}-deck.html"
    deck.write_text(build(data, nar))
    out_pdf = REPORTS / f"{stem}.pdf"
    has_pdf = print_pdf(deck, out_pdf)
    deck.unlink(missing_ok=True)
    out_html = render_html(interactive_data(data, nar, out_pdf.name if has_pdf else ""), REPORTS / f"{stem}.html")
    print(f"Interactive report: {out_html}")
    print(f"PDF: {out_pdf}" if has_pdf else "No PDF (Chrome / Edge not found). Open the HTML and use Print → Save as PDF.")
    if "--open" in sys.argv:
        open_file(out_html)
