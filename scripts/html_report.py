"""Shared helpers: render the interactive HTML report and print the PDF version.

Every report = one self-contained interactive .html (click, filter, A/B replies, checklist; images embedded,
works offline and on a phone) + a downloadable .pdf (16:9 deck) linked from the HTML's "Download PDF" button.
"""
import base64
import json
import shutil
import subprocess
from pathlib import Path

from common import ROOT, WORK, asset, profile

TEMPLATE = ROOT / "templates" / "report.html"


def data_uri(path):
    if not path or not Path(path).exists():
        return ""
    ext = Path(path).suffix.lower()
    mime = {".png": "image/png", ".webp": "image/webp", ".svg": "image/svg+xml"}.get(ext, "image/jpeg")
    return f"data:{mime};base64," + base64.b64encode(Path(path).read_bytes()).decode()


def brand():
    """Name, handle and images used on every report."""
    try:
        p = profile()
    except SystemExit:
        p = {}
    ch = (p.get("channels") or [{}])[0]
    return {"brand": p.get("brand_name") or p.get("creator_name") or "Your channel",
            "creator": p.get("creator_name") or "", "role": p.get("creator_role") or "Creator",
            "handle": ch.get("handle") or "@channel",
            "logo": data_uri(asset("logo")), "photo": data_uri(asset("creator"))}


def render_html(data, out_html):
    b = brand()
    data = dict(data)
    data.setdefault("brand", b["brand"])
    data.setdefault("handle", b["handle"])
    data.setdefault("creator", {"name": b["creator"], "role": b["role"]})
    data["images"] = {"logo": b["logo"], "photo": b["photo"]}
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    out_html.write_text(TEMPLATE.read_text().replace("/*__DATA__*/", payload))
    return out_html


def find_browser():
    for c in ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
              "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
              "/Applications/Chromium.app/Contents/MacOS/Chromium",
              r"C:\Program Files\Google\Chrome\Application\chrome.exe",
              r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
              shutil.which("google-chrome") or "", shutil.which("chromium") or "", shutil.which("chromium-browser") or ""]:
        if c and Path(c).exists():
            return c
    return None


def print_pdf(html_file, pdf_file, browser=None):
    """Print a (deck) HTML file to PDF with headless Chrome / Edge. Returns True if the PDF exists."""
    browser = browser or find_browser()
    if not browser:
        return False
    subprocess.run([browser, "--headless=new", "--disable-gpu", f"--user-data-dir={WORK / '.chrome'}", "--no-first-run",
                    "--no-pdf-header-footer", "--virtual-time-budget=4000", f"--print-to-pdf={pdf_file}", html_file.as_uri()],
                   capture_output=True, timeout=240)
    return pdf_file.exists()


def open_file(path):
    """Open the report in the default browser (macOS: open, Windows: start, Linux: xdg-open)."""
    import os
    import sys
    try:
        if sys.platform == "darwin":
            subprocess.run(["open", str(path)])
        elif os.name == "nt":
            os.startfile(str(path))  # noqa: S606 - a local file ReplyDNA just created
        else:
            subprocess.run(["xdg-open", str(path)])
    except Exception:
        pass
