"""Review one flat ad and show EVERY check (pass, fail, unsure) on one HTML page.

Usage: python -m review.single_page <image>
"""
import asyncio
import base64
import html
import io
import sys
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from review.run_flat import split_elements
from review.escalation import escalate
from review.stages import verify, vision_checks

COLOURS = ["#ff2d55", "#0a84ff", "#34c759", "#ff9f0a", "#bf5af2", "#00c7be", "#ffd60a", "#ff6482", "#64d2ff", "#30d158"]
VERDICT = {"pass": ("✅", "pass"), "fail": ("❌", "fail"), "unsure": ("❔", "unsure")}  # n/a is hidden


def data_uri(im):
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


async def run(path):
    t0 = time.time()
    img = Image.open(path).convert("RGB")
    w, h = img.size
    els = await split_elements(img)
    design = {"id": Path(path).stem[:12], "canvas": {"w": w, "h": h, "format": "feed"}, "elements": els}
    replies = []
    fails = await vision_checks(design, img, tags={}, raw_replies=replies)
    checked = escalate(await verify(fails, design, img), exclude_ad=design["id"])
    return img, design, replies, checked, round(time.time() - t0, 1)


def page(img, design, replies, checked, secs):
    boxed = img.copy()
    d = ImageDraw.Draw(boxed)
    f = ImageFont.load_default(size=max(14, img.width // 28))
    colour = {}
    for n, e in enumerate(design["elements"]):
        c = colour[e["id"]] = COLOURS[n % len(COLOURS)]
        x, y, bw, bh = e["bbox"]
        d.rectangle([x, y, x + bw, y + bh], outline=c, width=max(2, img.width // 200))
        d.rectangle([x, y, x + f.size * 1.6, y + f.size * 1.2], fill=c)
        d.text((x + 3, y), e["id"].lstrip("e"), fill="white", font=f)

    by_el = {}
    for r in replies:
        for item in r["reply"].get("items", []):
            by_el.setdefault(str(item.get("element_id")), []).append((r["prompt"], item))
    verdicts = {(c["element_id"], c["check"]): c for c in checked}

    cards, n_pass, n_fail, n_unsure, n_na = [], 0, 0, 0, 0
    for e in design["elements"]:
        rows = []
        for prompt, item in by_el.get(e["id"], []):
            for chk in item.get("checks", []):
                v = chk.get("verdict", "unsure")
                if v == "n/a":
                    n_na += 1
                    continue
                n_pass += v == "pass"; n_fail += v == "fail"; n_unsure += v == "unsure"
                icon, cls = VERDICT.get(v, ("❔", "unsure"))
                ver = verdicts.get((e["id"], chk.get("check")))
                ver_txt = (f"<div class='ver'><span class='tier {ver['tier']}'>{ver['tier']}</span> score {ver['score']} = {ver['why']}<br>"
                           f"Verifier: <b>{ver['verified']}</b> — {html.escape(str(ver.get('verify_evidence') or ''))}</div>") if ver else ""
                rows.append(f"<li class='{cls}'>{icon} <b>{html.escape(str(chk.get('check')))}</b>"
                            f"{' — ' + html.escape(str(chk.get('message'))) if v != 'pass' and chk.get('message') else ''}{ver_txt}</li>")
            obs = "".join(f"<li>{html.escape(str(o))}</li>" for o in item.get("observations", []))
            rows.append(f"<details><summary>What {prompt.replace('vision_', '')} checker saw</summary><ul>{obs}</ul></details>")
        body = "".join(rows) or "<li class='skip'>No vision check for this type</li>"
        label = html.escape(e.get("text") or "")[:80]
        cards.append(f"<article><h3><span class='dot' style='background:{colour[e['id']]}'>{e['id'].lstrip('e')}</span>"
                     f"{e['type']}{' <s>' + e['type_was'] + '</s>' if e.get('type_was') else ''} <small>{label}</small></h3><ul>{body}</ul></article>")
    issues = sum(c["tier"] == "issue" for c in checked)
    tips = sum(c["tier"] == "suggestion" for c in checked)
    head = ("✅ No issues" if not issues else f"❌ {issues} issue(s)") + (f" · {tips} suggestion(s)" if tips else "")
    return f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Ad Review</title><style>:root{{--bg:#f6f6f4;--fg:#1d1d1f;--mut:#6b6b70;--line:#e2e2df;--card:#fff}}
@media(prefers-color-scheme:dark){{:root{{--bg:#141416;--fg:#ededed;--mut:#9a9aa0;--line:#2f2f34;--card:#1e1e21}}}}
body{{margin:0;background:var(--bg);color:var(--fg);font:14px/1.5 system-ui,sans-serif}}
.wrap{{display:flex;gap:20px;flex-wrap:wrap;max-width:1200px;margin:auto;padding:20px 16px}}
.left{{flex:0 1 460px;position:sticky;top:12px;align-self:flex-start}}.left img{{width:100%;border-radius:8px;border:1px solid var(--line)}}
.right{{flex:1;min-width:300px}}article{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px 14px;margin:0 0 12px}}
h3{{margin:2px 0 6px;display:flex;gap:8px;align-items:center}}h3 small{{color:var(--mut);font-weight:400}}
.dot{{color:#fff;border-radius:6px;padding:0 7px;font-size:13px}}ul{{margin:4px 0;padding-left:18px}}
li.fail{{color:#dc2626}}li.unsure{{color:#b45309}}li.skip{{color:var(--mut)}}.ver{{color:var(--mut);font-size:12px}}
summary{{color:var(--mut);cursor:pointer;font-size:12px}}.tier{{font-size:11px;text-transform:uppercase;padding:1px 6px;border-radius:99px;color:#fff}}.tier.issue{{background:#dc2626}}.tier.suggestion{{background:#b45309}}.tier.hidden{{background:#9ca3af}}.stat{{font-size:15px}}
@media(max-width:700px){{.left{{position:static}}}}</style></head><body><div class="wrap">
<div class="left"><h1>{head}</h1><p class="stat">{n_pass} checks passed · {n_fail} failed · {n_unsure} unsure · {n_na} not applicable (hidden) · {secs}s</p>
<img src="{data_uri(boxed)}"><p style="color:var(--mut)">Boxes = elements DeepSeek Flash found (rough). Numbers match the cards.</p></div>
<div class="right">{''.join(cards)}</div></div></body></html>"""


async def main(path):
    out = Path("review/out") / f"single_{Path(path).stem[:12]}.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page(*(await run(path))))
    print(out)


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1]))
