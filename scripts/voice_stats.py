"""Voice DNA, step 2: measure how you actually talk, from your own transcripts.

  .venv/bin/python scripts/voice_stats.py            → work/voice_stats.json + a short summary
Finds: speaking pace, how you address viewers (you / aap / tum / usted ...), your signature phrases
(said in many different videos, not just one), how you open and close videos, and your most-used words.
Claude turns this into config/voice_card.md, which you approve. Every reply is written from that card.
"""
import json
import re
from collections import Counter

from common import DATA, WORK, profile

# letters + combining marks (Devanagari and other Indic scripts keep their vowel signs)
TOKEN = re.compile(r"(?:[^\W\d_]|[\u0900-\u0963\u0966-\u0dff])(?:[^\W_]|[\u0300-\u036f\u0900-\u0963\u0966-\u0dff]|'(?=\w))*")
STOP = set("""
a an the and or but if so to of in on at by for with from as is are was were be been being it its this that these those
i me my we our you your he she they them his her their what which who whom how why when where there here not no yes do does
did done have has had will would can could should just very really also then than too more most some any all about into out
up down over again once only own same such both each few other off now ok okay like get got go going gonna one two
hai hain ho hota hoti hote tha thi the ka ki ke ko se me mein par pe aur ya bhi to toh yeh ye woh wo is us isko usko kya
jo ki na nahi nhi hi ek do koi kuch bahut abhi ab phir fir karna karte kar kiya diya liya raha rahe rahi wala wali wale
है हैं हो था थी थे का की के को से में पर और या भी तो यह ये वह वो इस उस क्या जो कि ना नहीं ही एक दो कोई कुछ बहुत अभी अब फिर करना करते कर किया
el la los las de que y en un una es por con para no se lo al del le su
""".split())
ADDRESS = ["you", "your", "guys", "aap", "aapko", "aapke", "aapka", "tum", "tumhe", "tumhara", "tu", "आप", "आपको", "आपके", "तुम", "तू",
           "usted", "ustedes", "tú", "vous", "tu", "du", "sie"]


def load(path):
    d = json.loads(path.read_text())
    words, end = [], 0
    for ev in d.get("events", []):
        if "segs" in ev:
            words += TOKEN.findall("".join(s.get("utf8", "") for s in ev["segs"]).lower())
            end = max(end, ev.get("tStartMs", 0) + ev.get("dDurationMs", 0))
    return words, end / 60000


def ngrams(words, n):
    return [" ".join(words[i:i + n]) for i in range(len(words) - n + 1)]


def main():
    files = sorted((DATA / "transcripts").glob("*.json3"))
    if not files:
        raise SystemExit("No transcripts yet. Run: .venv/bin/python scripts/fetch_transcripts.py")
    track = (profile().get("voice_track") or []) + ADDRESS
    vids, total_words, total_min = [], Counter(), 0.0
    df, count, flat = Counter(), Counter(), Counter()
    openings, closings = [], []
    for f in files:
        words, minutes = load(f)
        if len(words) < 50:
            continue
        vids.append({"video": f.name.split(".")[0], "words": len(words), "minutes": round(minutes, 1)})
        total_min += minutes
        flat.update(words)
        total_words.update(w for w in words if w not in STOP and len(w) > 2)
        seen = set()
        for n in (2, 3, 4):
            for g in ngrams(words, n):
                if all(t in STOP for t in g.split()):
                    continue
                count[g] += 1
                seen.add(g)
        df.update(seen)
        openings.append(" ".join(words[:14]))
        closings.append(" ".join(words[-16:]))
    nv = len(vids)
    if not nv:
        raise SystemExit("Transcripts were empty.")
    # signature = said in many different videos (not one long rant), ranked by spread x frequency
    min_df = max(2, round(nv * 0.3))
    cand = sorted(((g, count[g], df[g]) for g in count if df[g] >= min_df and count[g] >= 5), key=lambda x: -(x[1] * x[2] / nv))
    sig = []
    for g, c, d in cand:
        if any(g in s["phrase"] or s["phrase"] in g for s in sig):
            continue
        sig.append({"phrase": g, "count": c, "videos": d})
        if len(sig) >= 25:
            break
    words_total = sum(v["words"] for v in vids)
    out = {
        "videos": nv, "minutes": round(total_min, 1), "words": words_total,
        "words_per_minute": round(words_total / max(total_min, 1), 1),
        "address_forms": {w: flat[w] for w in dict.fromkeys(track) if flat[w]},
        "signature_candidates": sig,
        "top_words": total_words.most_common(40),
        "openings": openings[:12], "closings": closings[:12],
        "per_video": vids,
    }
    path = WORK / "voice_stats.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(f"Voice DNA from {nv} videos · {out['minutes']} min · {words_total:,} words · {out['words_per_minute']} words/min")
    print("How you address viewers:", ", ".join(f"{k} {v}" for k, v in sorted(out["address_forms"].items(), key=lambda x: -x[1])[:8]) or "-")
    print("Signature candidates:")
    for s in sig[:12]:
        print(f"  {s['count']:>4}x in {s['videos']:>2}/{nv} videos · {s['phrase']}")
    print(f"Saved: {path}  → now ask Claude: \"build my voice card\"")


if __name__ == "__main__":
    main()
