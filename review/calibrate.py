"""Calibration: review all 20 good Xero reference ads. Every fail there is a false alarm by definition.

Writes review/calibration.json (per check, per ad: evaluated / failed) and review/out/calibration.html.
Usage: python -m review.calibrate
"""

import asyncio
import html
import json
import time
from pathlib import Path

from PIL import Image

from review.escalation import CALIBRATION, RULE_STRENGTH, escalate, false_alarm_rate
from review.run_flat import split_elements
from review.stages import verify, vision_checks

REFS = sorted(Path("assets/references").glob("*.png"))
OUT = Path("review/out/calib")
_ads_at_once = asyncio.Semaphore(4)


async def review_ad(path):
    async with _ads_at_once:
        t0 = time.time()
        img = Image.open(path).convert("RGB")
        design = {
            "id": path.stem[:12],
            "canvas": {"w": img.width, "h": img.height, "format": "feed"},
            "elements": await split_elements(img),
        }
        replies = []
        fails = await vision_checks(design, img, tags={}, raw_replies=replies)
        checked = await verify(fails, design, img)
        r = {
            "ad": path.stem[:12],
            "file": str(path),
            "design": design,
            "replies": replies,
            "findings": checked,
            "seconds": round(time.time() - t0, 1),
        }
        (OUT / f"{r['ad']}.json").write_text(json.dumps(r, indent=1, default=str))
        print(f"{r['ad']}  {len(fails)} raw fails  {r['seconds']}s", flush=True)
        return r


def tally(results):
    cal = {}
    for r in results:
        for rep in r["replies"]:
            for item in rep["reply"].get("items", []):
                for chk in item.get("checks", []):
                    v = chk.get("verdict")
                    if v in ("n/a", None):
                        continue
                    c = cal.setdefault(chk.get("check"), {}).setdefault(
                        r["ad"], {"evaluated": 0, "failed": 0}
                    )
                    c["evaluated"] += 1
                    c["failed"] += v == "fail"
    return cal


def page(results, cal):
    rule_rows = []
    for check in sorted(cal, key=lambda c: -(false_alarm_rate(cal, c) or 0)):
        ev = sum(v["evaluated"] for v in cal[check].values())
        fl = sum(v["failed"] for v in cal[check].values())
        ads = sum(1 for v in cal[check].values() if v["failed"])
        rate = false_alarm_rate(cal, check)
        bar = f"<div class='bar'><span style='width:{rate * 100:.0f}%'></span></div>"
        rule_rows.append(
            f"<tr><td><b>{check}</b></td><td>{RULE_STRENGTH.get(check, 0.5)}</td><td>{fl}/{ev}</td>"
            f"<td>{ads}/{len(results)}</td><td>{bar} {rate:.0%}</td></tr>"
        )
    tiers = {"issue": 0, "suggestion": 0, "hidden": 0}
    ad_rows = []
    for r in results:
        scored = escalate([f for f in r["findings"]], cal, exclude_ad=r["ad"])
        for f in scored:
            tiers[f["tier"]] += 1
        shown = [f for f in scored if f["tier"] != "hidden"]
        items = "".join(
            f"<li class='{f['tier']}'><b>{f['tier']}</b> {html.escape(str(f['check']))} on "
            f"{f['element_id']} — {html.escape(str(f['message']))}<br><small>score {f['score']} = {f['why']}</small></li>"
            for f in scored
        )
        status = (
            "✅"
            if not shown
            else ("⚠️" if all(f["tier"] == "suggestion" for f in shown) else "❌")
        )
        ad_rows.append(
            f"<details><summary>{status} {r['ad']} — {sum(f['tier'] == 'issue' for f in scored)} issues, "
            f"{sum(f['tier'] == 'suggestion' for f in scored)} suggestions, {sum(f['tier'] == 'hidden' for f in scored)} hidden</summary>"
            f"<ul>{items or '<li>no fails</li>'}</ul></details>"
        )
    return f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Rule Calibration</title><style>:root{{--bg:#f6f6f4;--fg:#1d1d1f;--mut:#6b6b70;--line:#e2e2df;--card:#fff}}
@media(prefers-color-scheme:dark){{:root{{--bg:#141416;--fg:#ededed;--mut:#9a9aa0;--line:#2f2f34;--card:#1e1e21}}}}
body{{margin:0 auto;max-width:1000px;padding:20px 16px;background:var(--bg);color:var(--fg);font:14px/1.5 system-ui,sans-serif}}
table{{border-collapse:collapse;width:100%;background:var(--card)}}td,th{{border:1px solid var(--line);padding:6px 10px;text-align:left}}
.bar{{display:inline-block;width:120px;height:8px;background:var(--line);border-radius:4px;vertical-align:middle}}.bar span{{display:block;height:8px;background:#f59e0b;border-radius:4px}}
details{{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:8px 12px;margin:8px 0}}
li.issue{{color:#dc2626}}li.suggestion{{color:#b45309}}li.hidden{{color:var(--mut)}}small{{color:var(--mut)}}
.wrap{{overflow-x:auto}}</style></head><body>
<h1>Rule calibration on 20 good Xero ads</h1>
<p>Every fail on a good ad is a false alarm. <b>After escalation:</b> {tiers["issue"]} issues · {tiers["suggestion"]} suggestions · {tiers["hidden"]} hidden
(each ad scored leave-one-out — never on its own calibration).</p>
<h2>False-alarm rate per rule</h2><div class="wrap"><table><tr><th>Rule</th><th>Strength</th><th>Fails / checks</th><th>Ads hit</th><th>False-alarm rate (smoothed)</th></tr>
{"".join(rule_rows)}</table></div>
<h2>Each ad after escalation</h2>{"".join(ad_rows)}</body></html>"""


async def main():
    OUT.mkdir(parents=True, exist_ok=True)
    results = await asyncio.gather(*[review_ad(p) for p in REFS])
    cal = tally(results)
    CALIBRATION.write_text(json.dumps(cal, indent=1))
    Path("review/out/calibration.html").write_text(page(results, cal))
    print("wrote", CALIBRATION, "and review/out/calibration.html")


if __name__ == "__main__":
    asyncio.run(main())
