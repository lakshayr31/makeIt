"""One HTML page listing every alarm from the last eval + flat runs, with the flagged element boxed."""
import glob
import html
import json
from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path("review/out")
EQUIV = __import__("review.run_eval", fromlist=["EQUIV"]).EQUIV


def mark(img_path, bbox, name):
    im = Image.open(img_path).convert("RGB")
    d = ImageDraw.Draw(im)
    x, y, w, h = bbox
    lw = max(4, im.width // 150)
    d.rectangle([x, y, x + w, y + h], outline="#ff2d55", width=lw)
    im.thumbnail((520, 700))
    im.save(OUT / "alarms" / name)
    return f"alarms/{name}"


def rows():
    (OUT / "alarms").mkdir(parents=True, exist_ok=True)
    items = []
    for r in json.load(open(OUT / "results.json")):
        d, s = r["design"], r["score"]
        els = {e["id"]: e for e in d["elements"]}
        fa_keys = {(f["check"], f["element_id"]) for f in s["false_alarms"]}
        for f in r["final"]:
            kind = "False alarm" if (f["check"], f["element_id"]) in fa_keys else "Correct catch"
            items.append((d["id"], f"{OUT}/{d['id']}.png", els.get(f["element_id"]), f, kind, d["expected"]))
        for f in r["vision_verified"]:
            if f["verified"] != "true":
                items.append((d["id"], f"{OUT}/{d['id']}.png", els.get(f["element_id"]), f, "Dropped by verifier", d["expected"]))
        for chk, el in s["missed"]:
            items.append((d["id"], f"{OUT}/{d['id']}.png", els.get(el), {"check": chk, "element_id": el, "message": "Not found by any check", "source": "-"}, "Missed", d["expected"]))
    for p in glob.glob(str(OUT / "flat_*.json")):
        r = json.load(open(p))
        d = r["design"]
        src = glob.glob(f"assets/references/{d['id']}*.png")[0]
        els = {e["id"]: e for e in d["elements"]}
        for f in r["findings"]:
            kind = "False alarm (good ad)" if f["verified"] == "true" else "Dropped by verifier"
            items.append((d["id"] + " (real Xero ad)", src, els.get(f["element_id"]), f, kind, []))
    return items


def page(items):
    order = {"False alarm": 0, "False alarm (good ad)": 0, "Missed": 1, "Dropped by verifier": 2, "Correct catch": 3}
    items.sort(key=lambda i: (order[i[4]], i[0]))
    cls = {"False alarm": "fa", "False alarm (good ad)": "fa", "Missed": "miss", "Dropped by verifier": "drop", "Correct catch": "ok"}
    counts = {}
    cards = []
    for n, (design, img, el, f, kind, exp) in enumerate(items):
        counts[kind] = counts.get(kind, 0) + 1
        pic = mark(img, el["bbox"], f"{n}.png") if el else ""
        exp_txt = ", ".join(f"{c} on {e}" for c, e in exp) or "nothing — this design should be clean"
        ver = f"<p><b>Verifier said {html.escape(str(f['verified']))}:</b> {html.escape(str(f.get('verify_evidence') or ''))}</p>" if f.get("verified") else ""
        obs = f.get("observations")
        obs_html = f"<details><summary>What the checker looked at</summary><ul>{''.join('<li>'+html.escape(str(o))+'</li>' for o in obs)}</ul></details>" if obs else ""
        cards.append(f"""<article class="{cls[kind]}"><div class="pic">{f'<img src="{pic}">' if pic else ''}</div><div class="txt">
<span class="tag">{kind}</span><h3>{html.escape(str(f['check']))} <small>on {f['element_id']}{' ('+el['type']+')' if el else ''} · {design}</small></h3>
<p class="msg">“{html.escape(str(f['message']))}”</p>
<p><b>Raised by:</b> {'code check (measured)' if f.get('source') == 'code' else html.escape(str(f.get('source')))}</p>
{f"<p><b>Evidence:</b> {html.escape(str(f.get('evidence')))}</p>" if f.get('evidence') else ''}{ver}
<p class="exp"><b>This design was supposed to have:</b> {exp_txt}</p>{obs_html}</div></article>""")
    summary = " · ".join(f"<b>{v}</b> {k.lower()}" for k, v in sorted(counts.items(), key=lambda kv: order[kv[0]]))
    return f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Review Alarms</title>
<style>:root{{--bg:#f6f6f4;--fg:#1d1d1f;--mut:#6b6b70;--line:#e2e2df;--card:#fff}}
@media(prefers-color-scheme:dark){{:root{{--bg:#141416;--fg:#ededed;--mut:#9a9aa0;--line:#2f2f34;--card:#1e1e21}}}}
body{{margin:0 auto;max-width:1000px;padding:20px 16px;background:var(--bg);color:var(--fg);font:14px/1.5 system-ui,sans-serif}}
article{{display:flex;gap:16px;flex-wrap:wrap;background:var(--card);border:1px solid var(--line);border-left:6px solid;border-radius:10px;padding:14px;margin:14px 0}}
.fa{{border-left-color:#f59e0b}}.miss{{border-left-color:#dc2626}}.drop{{border-left-color:#9ca3af}}.ok{{border-left-color:#16a34a}}
.pic img{{width:240px;border-radius:6px;border:1px solid var(--line)}}.txt{{flex:1;min-width:260px}}
h3{{margin:6px 0}}h3 small{{color:var(--mut);font-weight:400}}.msg{{font-size:15px}}.exp{{color:var(--mut)}}
.tag{{font-size:11px;text-transform:uppercase;letter-spacing:.05em;padding:2px 8px;border-radius:99px;background:var(--bg);border:1px solid var(--line)}}
</style></head><body><h1>Every alarm the reviewers raised</h1><p>{summary}</p>
<p style="color:var(--mut)">Red box = the element the alarm is about. Order: false alarms → missed → dropped by verifier → correct catches.</p>
{''.join(cards)}</body></html>"""


if __name__ == "__main__":
    it = rows()
    (OUT / "alarms.html").write_text(page(it))
    print(len(it), "alarms")
