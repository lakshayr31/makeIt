"""Run the full review pipeline over the test set and score it.

Usage: python -m review.run_eval
"""
import asyncio
import html
import json
import time

from review.code_checks import check_design
from review.design import ROOT, render
from review.stages import tag_asset, verify, vision_checks
from review.testset import build

# Which reported check names count as catching each expected defect.
EQUIV = {
    "cut_off_subject": {"cut_off_subject", "awkward_crop"},
    "covers_content": {"covers_content"},
    "off_canvas": {"off_canvas", "wordmark_integrity"},
    "logo_colour_pair": {"logo_colour_pair", "wordmark_integrity"},
    "stretched": {"stretched", "asset_quality", "bloom_shape_style"},
    "text_overflow": {"text_overflow", "text_rendering"},
    "low_contrast": {"low_contrast", "readable_on_background"},
    "off_palette": {"off_palette"},
    "card_content_broken": {"card_content_broken"},
    "stray_artefact": {"stray_artefact"},
    "safe_zone": {"safe_zone"},
}
OUT = ROOT / "review" / "out"


def matches(finding, exp):
    check, el = exp
    return finding["check"] in EQUIV[check] and (el == "*" or finding["element_id"] == el)


async def review(design):
    t0 = time.time()
    assets = {e["asset"] for e in design["elements"] if e.get("asset")}
    tag_list = await asyncio.gather(*[tag_asset(a) for a in assets])
    tags = dict(zip(assets, tag_list))
    img = render(design)
    code = check_design(design, tags)
    t_code = time.time()
    raw_vision = await vision_checks(design, img, tags)
    verified = await verify(raw_vision, design, img)
    final = code + [f for f in verified if f["verified"] == "true"]
    return {"design": design, "img": img, "tags": tags, "code": code, "vision_raw": raw_vision,
            "vision_verified": verified, "final": final, "seconds": round(time.time() - t0, 1),
            "code_seconds": round(t_code - t0, 1)}


def score(r):
    exp = r["design"]["expected"]
    caught = [e for e in exp if any(matches(f, e) for f in r["final"])]
    extra = [f for f in r["final"] if not any(matches(f, e) for e in exp)]
    raw_extra = [f for f in r["code"] + r["vision_raw"] if not any(matches(f, e) for e in exp)]
    return {"expected": len(exp), "caught": len(caught), "missed": [e for e in exp if e not in caught],
            "false_alarms": extra, "false_alarms_before_verify": len(raw_extra)}


def report(results):
    OUT.mkdir(parents=True, exist_ok=True)
    rows, cards = [], []
    tot = {"expected": 0, "caught": 0, "fa": 0, "fa_raw": 0}
    for r in results:
        s = r["score"]
        d = r["design"]
        tot["expected"] += s["expected"]; tot["caught"] += s["caught"]
        tot["fa"] += len(s["false_alarms"]); tot["fa_raw"] += s["false_alarms_before_verify"]
        r["img"].convert("RGB").save(OUT / f"{d['id']}.png")
        status = "✅" if not s["missed"] and not s["false_alarms"] else ("❌" if s["missed"] else "⚠️")
        rows.append(f"<tr><td>{status}</td><td>{d['id']}</td><td>{s['caught']}/{s['expected']}</td>"
                    f"<td>{len(s['false_alarms'])}</td><td>{s['false_alarms_before_verify']}</td><td>{r['seconds']}s</td></tr>")

        def li(f, cls):
            ver = f" · verifier: {f['verified']} — {html.escape(str(f.get('verify_evidence') or ''))}" if "verified" in f else ""
            return (f"<li class='{cls}'><b>{html.escape(str(f['check']))}</b> on {f['element_id']} "
                    f"<span class='src'>{f['source']}</span> — {html.escape(str(f['message']))}{ver}</li>")
        found = "".join(li(f, "fa" if f in s["false_alarms"] else "ok") for f in r["final"])
        dropped = "".join(li(f, "drop") for f in r["vision_verified"] if f["verified"] != "true")
        missed = "".join(f"<li class='miss'>MISSED: {m[0]} on {m[1]}</li>" for m in s["missed"])
        expect = ", ".join(f"{c} on {e}" for c, e in d["expected"]) or "nothing (clean design)"
        cards.append(f"<section><h2>{status} {d['id']}</h2><div class='row'><img src='{d['id']}.png'>"
                     f"<div><p><b>Expected:</b> {expect}</p><h3>Reported to designer</h3><ul>{found or '<li>none</li>'}{missed}</ul>"
                     f"<details><summary>Dropped by verifier ({len(dropped and r['vision_verified']) and sum(1 for f in r['vision_verified'] if f['verified'] != 'true')})</summary><ul>{dropped}</ul></details>"
                     f"</div></div></section>")
    summary = (f"Caught <b>{tot['caught']}/{tot['expected']}</b> planted defects · "
               f"<b>{tot['fa']}</b> false alarms after verify (were {tot['fa_raw']} before)")
    page = f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Review Eval</title><style>
:root{{--bg:#f7f7f5;--fg:#1d1d1f;--mut:#6b6b70;--line:#e2e2df;--card:#fff}}
@media(prefers-color-scheme:dark){{:root{{--bg:#141416;--fg:#ededed;--mut:#9a9aa0;--line:#2f2f34;--card:#1e1e21}}}}
body{{margin:0;padding:20px 16px;background:var(--bg);color:var(--fg);font:14px/1.5 system-ui,sans-serif;max-width:1100px;margin:auto}}
table{{border-collapse:collapse;background:var(--card);width:100%}}td,th{{border:1px solid var(--line);padding:6px 10px;text-align:left}}
section{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 16px;margin:16px 0}}
.row{{display:flex;gap:16px;flex-wrap:wrap}}.row img{{width:260px;border-radius:6px;border:1px solid var(--line)}}.row>div{{flex:1;min-width:280px}}
li.ok{{color:#1f9d55}}li.fa{{color:#d97706}}li.miss{{color:#dc2626;font-weight:600}}li.drop{{color:var(--mut)}}
.src{{font-size:11px;color:var(--mut);border:1px solid var(--line);border-radius:99px;padding:0 6px}}
</style></head><body><h1>Review pipeline eval</h1><p>{summary}</p>
<table><tr><th></th><th>Design</th><th>Caught</th><th>False alarms</th><th>Before verify</th><th>Time</th></tr>{''.join(rows)}</table>
<p style="color:var(--mut)">Green = correct finding · orange = false alarm · red = missed · grey = dropped by verifier</p>
{''.join(cards)}</body></html>"""
    (OUT / "report.html").write_text(page)
    return tot


async def main():
    designs = build()
    results = []
    for d in designs:  # sequential: keeps the shared endpoint happy and timings honest
        r = await review(d)
        r["score"] = score(r)
        s = r["score"]
        print(f"{d['id']:24} caught {s['caught']}/{s['expected']}  false alarms {len(s['false_alarms'])} "
              f"(raw {s['false_alarms_before_verify']})  {r['seconds']}s", flush=True)
        results.append(r)
    tot = report(results)
    (OUT / "results.json").write_text(json.dumps(
        [{k: v for k, v in r.items() if k not in ("img",)} for r in results], indent=1, default=str))
    print(f"\nTOTAL caught {tot['caught']}/{tot['expected']} · false alarms {tot['fa']} (raw {tot['fa_raw']})")
    print(f"report: {OUT / 'report.html'}")


if __name__ == "__main__":
    asyncio.run(main())
