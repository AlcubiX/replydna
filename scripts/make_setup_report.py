"""Setup report: interactive HTML + PDF, same style as the monthly report.

Claude runs this AUTOMATICALLY at the end of setup (and after any dry run). No need to ask.
Input : work/setup_status.json (Claude writes it during setup), schema:
{
  "title": "Setup report",
  "date": "10 Nov 2026",
  "machine": "macOS 15 · Python 3.12",
  "summary": "1-2 lines",
  "phases": [{"n": 1, "name": "System check", "status": "done|skipped|pending", "note": "short"}],
  "numbers": [{"n": "170", "l": "comments fetched"}],                                  # 4-10 KPIs
  "checks": [{"name": "Posted to YouTube by mistake", "value": "0", "ok": true, "why": "optional"}],
  "issues": [{"t": "what broke", "fix": "how it was fixed"}],
  "next": ["next step", "..."]
}
Output: reports/<title>-<date>.html (INTERACTIVE, open this) + .pdf (download button inside)
Run   : .venv/bin/python scripts/make_setup_report.py work/setup_status.json [--open]
"""
import datetime as dt
import html
import json
import sys

from common import REPORTS
from html_report import brand, open_file, print_pdf, render_html
from make_report import CSS

E = html.escape
EXTRA = """
.ph{display:grid;grid-template-columns:repeat(5,1fr);gap:20px;margin-top:44px;position:relative;z-index:1}
.p{background:#111118;border:1px solid #23232E;border-radius:22px;padding:24px 24px 22px;min-height:230px}
.p .n{font-size:20px;color:#8B8BFF;font-weight:700}.p .t{font-size:27px;font-weight:700;letter-spacing:-.02em;margin-top:8px;line-height:1.15}
.p .st{display:inline-block;margin-top:14px;font-size:16px;font-weight:700;padding:5px 10px;border-radius:6px}
.p .st.done{background:#163A2A;color:#4BE39A}.p .st.skipped{background:#2A2A38;color:#B9B9C8}.p .st.pending{background:#3A2A10;color:#FFB547}
.p .x{font-size:17px;color:#9A9AAF;margin-top:10px;line-height:1.35}
.checks{display:grid;grid-template-columns:repeat(2,1fr);gap:22px;margin-top:44px}
.ck2{background:#fff;border:1px solid #E1E1EA;border-radius:22px;padding:24px 28px;display:flex;justify-content:space-between;align-items:center}
.ck2 .nm{font-size:25px;font-weight:600}.ck2 .v{font-size:46px;font-weight:800;letter-spacing:-.04em}.ck2 .ok{color:#14A05A}.ck2 .bad{color:#E5484D}
.iss{margin-top:40px;display:grid;grid-template-columns:1fr 1fr;gap:20px 40px;position:relative;z-index:1}
.is{border-top:1px solid #2A2A38;padding-top:16px}.is b{font-size:24px;display:block}.is span{font-size:20px;color:#A9A9BC;line-height:1.45}
.is span:before{content:"Fix: ";color:#8B8BFF;font-weight:700}
.nx{margin-top:40px;font-size:30px;line-height:1.5}.nx div{padding:16px 0;border-bottom:1px solid #DCDCE6;display:flex;gap:22px}
.nx b{color:transparent;-webkit-text-stroke:1.5px #3D4BFF;font-size:44px;font-weight:800;min-width:76px;line-height:1}
"""
STATUS = {"done": "✓ Done", "skipped": "Skipped", "pending": "Pending"}


def build(st):
    b = brand()
    N = 6
    logo = f'<img src="{b["logo"]}">' if b["logo"] else ""

    def slide(i, sec, body, dark=True):
        top = (f'<div class="top"><div class="brand">{logo}{E(b["brand"])} · {E(st["title"])} · {E(st["date"])}</div>'
               f'<div>{E(sec)}<span class="pg">{i:02d} / {N:02d}</span></div></div>')
        return f'<section class="s {"dark" if dark else "light"}"><div class="glow"></div>{top}{body}</section>'

    done = sum(1 for p in st["phases"] if p["status"] == "done")
    right = (f'<div class="cov-g"></div><div class="cov-r"><img src="{b["photo"]}"><div class="tag"><b>{E(b["creator"])}</b>'
             f'<span>{E(b["role"])} · {E(b["handle"])}</span></div></div>') if b["photo"] else \
            (f'<div class="cov-g"></div><img class="cov-mark" src="{b["logo"]}">' if b["logo"] else "")
    S = [slide(1, "Cover", f'''<div class="cov-l"><div class="pill">{E(st["title"])} · {E(st["date"])}</div>
      <div class="mega"><span class="dim">{done} / {len(st["phases"])} phases,</span><br>all checked.</div><p class="lead">{E(st["summary"])}</p>
      <div class="meta">{logo}<div><div class="k">System</div><div class="v">ReplyDNA · {E(b["handle"])}</div></div><div class="vr"></div>
      <div><div class="k">Machine</div><div class="v">{E(st["machine"])}</div></div></div></div>{right}''')]
    S.append(slide(2, "Phases", f'''<div class="h2"><span class="dim">Setup in</span> {len(st["phases"])} phases</div><div class="ph">
      {"".join(f'<div class="p"><div class="n">PHASE {p["n"]:02d}</div><div class="t">{E(p["name"])}</div><span class="st {p["status"]}">{STATUS[p["status"]]}</span>'
               f'<div class="x">{E(p.get("note", ""))}</div></div>' for p in st["phases"])}</div>'''))
    kp = lambda ks: "".join(f'<div class="kpi"><div class="n">{E(k["n"])}</div><div class="l">{E(k["l"])}</div></div>' for k in ks)  # noqa: E731
    S.append(slide(3, "Numbers", f'''<div class="h2"><span class="dim">The real</span> numbers</div>
      <div class="kpis" style="grid-template-columns:repeat({min(5, len(st["numbers"]))},1fr)">{kp(st["numbers"][:5])}</div>
      {"" if len(st["numbers"]) <= 5 else '<div class="kpis" style="grid-template-columns:repeat(5,1fr)">' + kp(st["numbers"][5:10]) + "</div>"}'''))
    S.append(slide(4, "Safety checks", f'''<div class="h2">Safety <span class="blue">checks</span></div><div class="checks">
      {"".join(f'<div class="ck2"><div class="nm">{E(c["name"])}</div><div class="v {"ok" if c["ok"] else "bad"}">{E(c["value"])}</div></div>' for c in st["checks"])}</div>''',
                   dark=False))
    S.append(slide(5, "Found & fixed", f'''<div class="h2"><span class="dim">What we found,</span> what we fixed</div><div class="iss">
      {"".join(f'<div class="is"><b>{E(x["t"])}</b><span>{E(x["fix"])}</span></div>' for x in st["issues"][:8])}</div>'''))
    S.append(slide(6, "Next", f'''<div class="h2"><span class="diml">What's</span> next</div><div class="nx">
      {"".join(f"<div><b>{i + 1:02d}</b><span>{E(x)}</span></div>" for i, x in enumerate(st["next"][:5]))}</div>''', dark=False))
    return (f'<!doctype html><html><head><meta charset="utf-8"><title>{E(b["brand"])} {E(st["title"])}</title>'
            f'<style>{CSS}{EXTRA}</style></head><body>{"".join(S)}</body></html>')


if __name__ == "__main__":
    st = json.load(open([a for a in sys.argv[1:] if not a.startswith("--")][0]))
    stem = f'{st["title"].lower().replace(" ", "-")}-{dt.date.today().isoformat()}'
    deck = REPORTS / f".{stem}-deck.html"
    deck.write_text(build(st))
    out_pdf = REPORTS / f"{stem}.pdf"
    has_pdf = print_pdf(deck, out_pdf)
    deck.unlink(missing_ok=True)
    done = sum(1 for p in st["phases"] if p["status"] == "done")
    data = {"kind": "setup", "id": stem, "title": st["title"], "date": st["date"], "pill": f'{st["title"]} · {st["date"]}',
            "headline": [f'{done} / {len(st["phases"])} phases,', "all checked."], "summary": st["summary"],
            "meta": [{"k": "System", "v": "ReplyDNA"}, {"k": "Machine", "v": st["machine"]}],
            "hero_stat": {"n": f'{done}/{len(st["phases"])}', "l": "phases done"},
            "kpis": st["numbers"][:5], "phases": st["phases"], "numbers": st["numbers"], "checks": st["checks"],
            "issues": st["issues"], "next_title": "What's next", "next_items": st["next"], "pdf": out_pdf.name if has_pdf else ""}
    out_html = render_html(data, REPORTS / f"{stem}.html")
    print(f"Interactive report: {out_html}")
    print(f"PDF: {out_pdf}" if has_pdf else "No PDF (Chrome / Edge not found). Open the HTML and use Print → Save as PDF.")
    if "--open" in sys.argv:
        open_file(out_html)
