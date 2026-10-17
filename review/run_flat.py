"""Review a FLAT finished ad (no element data): Flash lists the elements, then vision + verify.

Code checks are skipped: they need exact element boxes, and Flash's boxes are only rough.
Usage: python -m review.run_flat <image> [<image> ...]
"""

import asyncio
import json
import sys
import time
from pathlib import Path

from PIL import Image

from review.design import crop_with_margin
from review.stages import PROMPTS, ask, verify, vision_checks

TYPES = "text | button | logo | photo | product | bloom | charm | illustration | card | icon | decoration | background"
SPLIT_PROMPT = f"""You list the design elements of a finished ad image so each can be reviewed.
Return ONLY JSON: {{"elements": [{{"id": "e1", "type": "{TYPES}", "box": [x1, y1, x2, y2], "text": "exact text or null"}}]}}
Coordinates normalised 0-1000 (x across, y down). Boxes generous: include the whole element.
One element per headline, button, logo, photo, UI card, charm/sticker, bloom shape, icon/badge, decoration. Skip plain background fills."""


async def split_elements(img):
    """Flash lists the elements, then a second pass confirms each element's type on its crop."""
    w, h = img.size
    split = await ask(SPLIT_PROMPT, [("ad", img)])
    els = []
    for i, e in enumerate(split.get("elements", []), 1):
        x1, y1, x2, y2 = e["box"]
        els.append({"id": e.get("id") or f"e{i}", "type": e.get("type", "background"), "text": e.get("text"),
                    "bbox": [x1 * w / 1000, y1 * h / 1000, (x2 - x1) * w / 1000, (y2 - y1) * h / 1000]})
    parts = []
    for e in els:
        parts += [json.dumps({"id": e["id"], "guessed_type": e["type"], "text": e["text"]}),
                  (f"crop_{e['id']}", crop_with_margin(img, e["bbox"]))]
    confirmed = await ask((PROMPTS / "type_check.md").read_text(), parts)
    fixed = {str(t["id"]): t for t in confirmed.get("types", [])}
    for e in els:
        t = fixed.get(e["id"])
        if t and t.get("type") and t["type"] != e["type"]:
            e["type_was"], e["type"], e["type_reason"] = e["type"], t["type"], t.get("reason")
    return els


async def review_flat(path):
    t0 = time.time()
    img = Image.open(path).convert("RGB")
    w, h = img.size
    design = {"id": Path(path).stem[:12], "canvas": {"w": w, "h": h, "format": "feed"},
              "elements": await split_elements(img)}
    raw = await vision_checks(design, img, tags={})
    checked = await verify(raw, design, img)
    return design, raw, checked, round(time.time() - t0, 1)


async def main(paths):
    for p in paths:
        design, raw, checked, secs = await review_flat(p)
        kept = [f for f in checked if f["verified"] == "true"]
        print(
            f"\n=== {design['id']}  {secs}s  elements={len(design['elements'])}  "
            f"vision flagged={len(raw)}  after verifier={len(kept)}"
        )
        print(
            "   elements:",
            ", ".join(f"{e['id']}:{e['type']}" for e in design["elements"]),
        )
        for f in checked:
            mark = "KEPT   " if f["verified"] == "true" else f"dropped({f['verified']})"
            print(
                f"   {mark} {f['source']}/{f['check']} on {f['element_id']}: {f['message']}"
            )
            print(f"           verifier: {f.get('verify_evidence')}")
        Path("review/out").mkdir(parents=True, exist_ok=True)
        Path(f"review/out/flat_{design['id']}.json").write_text(
            json.dumps(
                {"design": design, "findings": checked, "seconds": secs},
                indent=1,
                default=str,
            )
        )


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:]))
