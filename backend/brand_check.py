"""Brand check after every chat edit: measured code checks + one Flash brand-guardian call.

Also checks each generated image before it is offered (regenerated once if it fails).
"""

import asyncio
import base64
import json
import sys

from agent import complete_json
from build import _generate
from config import GENERATED_DIR, ROOT

sys.path.insert(0, str(ROOT))  # review/ lives at the repo root
from review.code_checks import PALETTE, _nearest, _rgb  # noqa: E402

PROMPTS = ROOT / "prompts"
EDGE_MARGIN = 72  # px kept clear for text, logo and buttons (fixer.md)
EDGE_SLACK = 2  # Fabric text boxes round by a pixel or so; don't flag that
MIN_TEXT = 30
MIN_HEADLINE = 48
OVERLAP_SHARE = 0.02
PALETTE_DISTANCE = 12


def _is_foreground(el: dict) -> bool:
    name = f"{el.get('id', '')} {el.get('name', '')}".lower()
    return el.get("type") == "text" or "logo" in name or "cta" in name


def _box(el: dict) -> list[float]:
    return [el["x"], el["y"], el["width"], el["height"]]


def _overlap(a: list[float], b: list[float]) -> float:
    w = min(a[0] + a[2], b[0] + b[2]) - max(a[0], b[0])
    h = min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1])
    return max(w, 0) * max(h, 0)


def _same_group(a: str, b: str) -> bool:
    return a.split("_")[0] == b.split("_")[0]  # a button and its own pill


def code_issues(canvas: dict, changed: set[str]) -> list[dict]:
    """Measured problems on the changed elements (all elements when nothing is marked changed)."""
    W, H = canvas.get("width", 1080), canvas.get("height", 1350)
    els = [e for e in canvas.get("elements", []) if e.get("visible", True)]
    judged = [e for e in els if not changed or e["id"] in changed]
    fg = [e for e in els if _is_foreground(e)]
    out = []

    def issue(el, check, message):
        out.append(
            {
                "element_id": el["id"],
                "check": check,
                "message": message,
                "fixable": True,
            }
        )

    for el in judged:
        x, y, w, h = _box(el)
        if _is_foreground(el):
            edges = [
                text
                for text, bad in (
                    (f"left edge at x={round(x)} (needs >= {EDGE_MARGIN})", x < EDGE_MARGIN - EDGE_SLACK),
                    (f"top edge at y={round(y)} (needs >= {EDGE_MARGIN})", y < EDGE_MARGIN - EDGE_SLACK),
                    (f"right edge at {round(x + w)} (needs <= {W - EDGE_MARGIN}; shrink width or move left)", x + w > W - EDGE_MARGIN + EDGE_SLACK),
                    (f"bottom edge at {round(y + h)} (needs <= {H - EDGE_MARGIN})", y + h > H - EDGE_MARGIN + EDGE_SLACK),
                )
                if bad
            ]
            if edges:
                issue(el, "margin", f"{el.get('name') or el['id']} breaks the {EDGE_MARGIN}px margin: " + "; ".join(edges) + ".")
        if el.get("type") == "text" and el.get("fontSize"):
            floor = (
                MIN_HEADLINE
                if "headline" in f"{el['id']} {el.get('name', '')}".lower()
                else MIN_TEXT
            )
            if el["fontSize"] < floor:
                issue(
                    el,
                    "size",
                    f"Text is {round(el['fontSize'])}px; the brand minimum is {floor}px.",
                )
        fill = el.get("fill")
        if (
            isinstance(fill, str)
            and fill.startswith("#")
            and len(fill) == 7
            and not _nearest(_rgb(fill), PALETTE, max_dist=PALETTE_DISTANCE)
        ):
            issue(el, "colour", f"{fill} is not a Xero brand colour.")
        if _is_foreground(el):
            for other in fg:
                if other["id"] == el["id"] or _same_group(other["id"], el["id"]):
                    continue
                shared = _overlap(_box(el), _box(other))
                smaller = (
                    min(el["width"] * el["height"], other["width"] * other["height"])
                    or 1
                )
                if shared > OVERLAP_SHARE * smaller:
                    issue(
                        el,
                        "overlap",
                        f"{el.get('name') or el['id']} overlaps {other.get('name') or other['id']}.",
                    )
    return out


async def check(body: dict) -> dict:
    """Canvas after an edit → {passed, issues, ops, fixed}. vision=False runs the code checks only."""
    canvas = body.get("canvas") or {}
    changed = set(body.get("changed_ids") or [])
    measured = code_issues(canvas, changed)
    if not body.get("vision", True):
        return {"passed": not measured, "issues": measured, "ops": [], "fixed": []}

    payload = {
        "request": body.get("request", ""),
        "canvas": canvas,
        "changed_ids": sorted(changed),
        "code_issues": measured,
    }
    reply = await complete_json(
        "flash",
        [
            {"role": "system", "content": (PROMPTS / "brand_check.md").read_text()},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": json.dumps(payload)},
                    {
                        "type": "text",
                        "text": "Image `design` (the canvas after the change):",
                    },
                    {"type": "image_url", "image_url": {"url": body["screenshot"]}},
                ],
            },
        ],
    )
    issues = reply.get("issues") or []
    seen = {(i.get("element_id"), i.get("check")) for i in issues}
    issues += [m for m in measured if (m["element_id"], m["check"]) not in seen]
    return {
        "passed": not issues,
        "issues": issues,
        "ops": reply.get("ops") or [],
        "fixed": reply.get("fixed") or [],
    }


# ---- generated images ----


def _data_url(src: str) -> str:
    path = GENERATED_DIR / src.removeprefix("/generated/")
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode()


async def image_problems(src: str, prompt: str) -> list[str]:
    reply = await complete_json(
        "flash",
        [
            {"role": "system", "content": (PROMPTS / "image_check.md").read_text()},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": f"Prompt it was made from: {prompt}"},
                    {"type": "image_url", "image_url": {"url": _data_url(src)}},
                ],
            },
        ],
    )
    return (
        []
        if reply.get("ok", True)
        else (reply.get("problems") or ["Doesn't match the brand style"])
    )


async def checked_image(prompt: str, size: str, transparent: bool, tag: str) -> dict:
    """Generate, check, regenerate once if off-brand. Still failing → returned with a warning."""
    src = await _generate(f"{prompt} ({tag})", size, transparent)
    problems = await image_problems(src, prompt)
    if problems:
        src = await _generate(
            f"{prompt} ({tag}, retry: avoid {'; '.join(problems)})", size, transparent
        )
        problems = await image_problems(src, prompt)
    return {"src": src, "warning": ", ".join(problems) if problems else None}


async def checked_images(
    prompt: str, size: str, transparent: bool, n: int
) -> list[dict]:
    return await asyncio.gather(
        *[
            checked_image(prompt, size, transparent, f"variation {i + 1}")
            for i in range(n)
        ]
    )
