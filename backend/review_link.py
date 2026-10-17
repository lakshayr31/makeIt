"""Brand review + one fix pass for a solved layout, using the review/ pipeline.

layout_i.json → reviewer design → (tag, code checks, vision, verify, escalate)
→ Flash fixer edits the layout → code checks again → what got fixed / what is left.
"""

import asyncio
import json
import sys
import time
from pathlib import Path

from PIL import Image, ImageFont

from agent import complete_json
from brand_tools import with_playbook
from build import _local, open_image
from config import GENERATED_DIR, ROOT
from layout import FONT_BOLD, FONT_MEDIUM, LINE_HEIGHT, _wrap

sys.path.insert(0, str(ROOT))  # review/ lives at the repo root
from review.code_checks import check_design  # noqa: E402
from review.design import render  # noqa: E402
from review.escalation import (  # noqa: E402
    DEFAULT_STRENGTH, RULE_STRENGTH, SUGGESTION, escalate, false_alarm_rate, load_calibration,
)
from review.stages import tag_asset, verify, vision_checks  # noqa: E402

CATALOG = ROOT / "assets/brand-kit/catalog.json"
FIXER_PROMPT = ROOT / "prompts/fixer.md"
SVG_CACHE = GENERATED_DIR / "svg_png"
LOGOS = {
    "white": "/assets/brand-kit/10_Logo/10_Logo/01_0f4c5387-a60d-4a27-93e8-9f5223676154.png",
    "navy": "/assets/brand-kit/10_Logo/10_Logo/02_2f020a69-e294-4971-b448-760f8b1827ad.png",
    "cyan": "/assets/brand-kit/10_Logo/10_Logo/03_a6d69555-61d3-43ba-a7ab-e38d56a3805c.png",
}
# Catalog kind → reviewer element type (picks which vision prompt judges it).
KIND_TYPE = {"charm": "charm", "illustration": "illustration", "bloom": "bloom",
             "product_ui": "product", "logo": "logo", "background_template": "background"}
FIX_ROUNDS = 2  # round 2 only chases what the code checks still measure
LOGO_PILL_PAD = 0.35  # same as the editor's importLayout.ts
EDITABLE = {"x", "y", "w", "h", "text", "font_size", "colour", "fill", "src"}


def _kinds() -> dict[str, str]:
    return {e["url"]: e["kind"] for e in json.loads(CATALOG.read_text())}


def _asset_path(src: str) -> str:
    """Layout URL → path relative to the repo root (what review/ expects). SVGs become PNGs."""
    path = _local(src)
    if path.suffix == ".svg":
        SVG_CACHE.mkdir(exist_ok=True)
        png = SVG_CACHE / f"{path.stem}.png"
        if not png.exists():
            open_image(src).save(png)
        path = png
    return str(path.relative_to(ROOT))


def _element_type(layer: dict, kinds: dict[str, str]) -> str:
    role, src = layer["role"], layer["props"].get("src", "")
    if role == "background":
        return "background"
    if role == "logo":
        return "logo"
    if layer["type"] == "text":
        return "button" if layer["props"].get("pill") else "text"
    if layer["type"] == "rect":
        return "shape"  # cards sit behind text on purpose; not a foreground overlap
    if "/parts/blooms/" in src:
        return "bloom"
    if "/parts/charms/" in src:
        return "charm"
    return KIND_TYPE.get(kinds.get(src), "illustration")  # generated art is Xero-style illustration


def to_design(layout: dict, fmt: str, kinds: dict[str, str]) -> dict:
    """Solved layout → the reviewer's design JSON (see review/design.py)."""
    els = []
    for l in layout["layers"]:
        p = l["props"]
        el = {"id": l["id"], "type": _element_type(l, kinds), "z": l["z"],
              "bbox": [l["x"], l["y"], l["w"], l["h"]]}
        if l["type"] == "image" and p.get("src"):
            el["asset"] = _asset_path(p["src"])
            if p.get("clip"):
                cx, cy, cw, ch = p["clip"]
                nw, nh = Image.open(ROOT / el["asset"]).size
                sx, sy = nw / l["w"], nh / l["h"]
                el["bbox"] = [cx, cy, cw, ch]
                el["crop"] = [(cx - l["x"]) * sx, (cy - l["y"]) * sy, cw * sx, ch * sy]
            if p.get("pill"):
                pad = l["h"] * LOGO_PILL_PAD
                els.append({"id": f"{l['id']}_pill", "type": "shape", "z": l["z"] - 0.01,
                            "bbox": [l["x"] - pad, l["y"] - pad, l["w"] + 2 * pad, l["h"] + 2 * pad],
                            "fill": "#FFFFFF", "radius": l["h"]})
        elif l["type"] == "text":
            el["text"] = "\n".join(p.get("lines") or [p.get("text", "")])
            el["font"] = {"size": p.get("font_size", 40), "color": p.get("colour", "#000856"),
                          "bold": p.get("weight") == "bold"}
            if p.get("pill"):
                el["fill"], el["radius"] = p.get("fill"), l["h"] / 2
        elif l["type"] == "rect":
            el["fill"], el["radius"] = p.get("fill"), p.get("radius", 0)
        els.append(el)
    return {"id": "variant", "elements": els,
            "canvas": {"w": 1080, "h": 1350, "format": "story" if fmt == "9:16" else "feed",
                       "bg": layout.get("background_colour") or "#FFFFFF"}}


_pending_tags: dict[str, asyncio.Task] = {}


def pretag(url: str) -> None:
    """Start tagging a picture now (e.g. as soon as it's generated) so the review doesn't wait."""
    path = _asset_path(url)
    if path not in _pending_tags:
        _pending_tags[path] = asyncio.create_task(tag_asset(path))


async def _tag(asset: str) -> dict:
    task = _pending_tags.get(asset)
    if task is None or (task.done() and task.exception()):  # retry a failed early tag
        task = _pending_tags[asset] = asyncio.create_task(tag_asset(asset))
    return await task


NO_REGIONS = {"bloom", "background", "charm"}  # decorative: bleeding off canvas or under text is by design


async def _tags(design: dict) -> dict:
    assets = sorted({e["asset"] for e in design["elements"] if e.get("asset")})
    tags = dict(zip(assets, await asyncio.gather(*[_tag(a) for a in assets])))
    for e in design["elements"]:
        if e["type"] in NO_REGIONS and e.get("asset"):
            tags[e["asset"]] = {**tags[e["asset"]], "regions": []}
    return tags


class Timer:
    """Seconds per stage, so we cut the real bottleneck."""

    def __init__(self):
        self.secs, self._t = {}, time.time()

    def lap(self, stage: str) -> None:
        now = time.time()
        self.secs[stage] = round(self.secs.get(stage, 0) + now - self._t, 1)
        self._t = now


def _could_show(finding: dict, cal: dict) -> bool:
    """False when even a fully-agreed verify could not lift this finding above Hidden."""
    strength = RULE_STRENGTH.get(finding["check"], DEFAULT_STRENGTH)
    return strength * (1 - (false_alarm_rate(cal, finding["check"]) or 0)) >= SUGGESTION


async def review_design(design: dict, timer: Timer) -> list[dict]:
    """Full review → escalated findings (tier issue / suggestion / hidden)."""
    tags = await _tags(design)
    timer.lap("tag")
    img = render(design)
    code = check_design(design, tags)
    timer.lap("code")
    vision = await vision_checks(design, img, tags)
    timer.lap("vision")
    cal = load_calibration()
    worth = [f for f in vision if _could_show(f, cal)]
    verified = await verify(worth, design, img, max_rounds=1)
    timer.lap("verify")
    found = escalate(code + [f for f in verified if f.get("verified") == "true"], cal)
    # Brand-kit background templates only ship at ~580 px; flagging them as blurry is noise.
    bg = {e["id"] for e in design["elements"] if e["type"] == "background"}
    return [f for f in found if not (f["check"] == "low_resolution" and f["element_id"] in bg)]


def _dedupe(findings: list[dict]) -> list[dict]:
    seen, out = set(), []
    for f in findings:
        key = (f["element_id"], f["check"])
        if key not in seen:
            seen.add(key)
            out.append(f)
    return out


def _relayout_text(layer: dict) -> None:
    """Re-wrap a text layer after its text/size/width changed, so lines and height stay true."""
    p = layer["props"]
    if p.get("pill"):
        p["lines"] = [p["text"]]
        return
    font = ImageFont.truetype(FONT_BOLD if p.get("weight") == "bold" else FONT_MEDIUM, p["font_size"])
    p["lines"] = _wrap(p["text"], font, layer["w"])
    layer["h"] = len(p["lines"]) * p["font_size"] * LINE_HEIGHT


def apply_edits(layout: dict, edits: list[dict]) -> int:
    by_id = {l["id"]: l for l in layout["layers"]}
    applied = 0
    for e in edits:
        layer = by_id.get(str(e.get("id", "")).removesuffix("_pill"))
        changes = {k: v for k, v in (e.get("set") or {}).items() if k in EDITABLE and v is not None}
        if not layer or not changes:
            continue
        for k, v in changes.items():
            if k in {"x", "y", "w", "h", "font_size"}:
                v = float(v)
            if k == "src" and v in LOGOS:
                v = LOGOS[v]
            if k in {"x", "y", "w", "h"}:
                layer[k] = v
            else:
                layer["props"][k] = v
        if layer["type"] == "text" and changes.keys() & {"text", "font_size", "w"}:
            _relayout_text(layer)
        applied += 1
    return applied


def _layer_brief(layout: dict) -> list[dict]:
    keep = ("text", "font_size", "weight", "colour", "fill", "pill", "src")
    return [{"id": l["id"], "role": l["role"], "type": l["type"], "z": l["z"],
             "x": round(l["x"]), "y": round(l["y"]), "w": round(l["w"]), "h": round(l["h"]),
             "visible_box": _visible(l),
             **{k: l["props"][k] for k in keep if k in l["props"]}} for l in layout["layers"]]


def _visible(l: dict) -> list[int]:
    """What the layer actually covers on the 1080×1350 canvas: its clip, cut to the canvas."""
    x, y, w, h = l["props"].get("clip") or [l["x"], l["y"], l["w"], l["h"]]
    x2, y2 = min(x + w, 1080), min(y + h, 1350)
    x, y = max(x, 0), max(y, 0)
    return [round(x), round(y), round(max(x2 - x, 0)), round(max(y2 - y, 0))]


async def fix(layout: dict, issues: list[dict]) -> list[dict]:
    """One Flash call: layout + issues → small edits."""
    findings = [{"n": i, "element_id": f["element_id"], "check": f["check"], "message": f["message"]}
                for i, f in enumerate(issues)]
    reply = await complete_json("flash", [
        {"role": "system", "content": with_playbook(FIXER_PROMPT.read_text())},
        {"role": "user", "content": json.dumps({
            "canvas": {"w": 1080, "h": 1350, "background_colour": layout.get("background_colour")},
            "logo_variants": list(LOGOS), "layers": _layer_brief(layout), "issues": findings})},
    ], timeout=20)
    return reply.get("edits", [])


async def review_and_fix(layout_path: Path, fmt: str) -> dict:
    """Review a layout, fix its issues once, re-check with code. Rewrites the layout file."""
    kinds = _kinds()
    layout = json.loads(layout_path.read_text())
    timer = Timer()
    findings = _dedupe(await review_design(to_design(layout, fmt, kinds), timer))
    issues = [f for f in findings if f["tier"] == "issue"]
    suggestions = [f["message"] for f in findings if f["tier"] == "suggestion"]
    if not issues:
        print(f"review {layout_path.name}: {timer.secs}", flush=True)
        return {"fixed": [], "issues": [], "suggestions": suggestions, "secs": timer.secs}

    claimed, todo = set(), issues
    for _ in range(FIX_ROUNDS):
        edits = await fix(layout, todo)
        timer.lap("fix")
        apply_edits(layout, edits)
        claimed |= {(todo[int(n)]["element_id"], todo[int(n)]["check"])
                    for e in edits for n in (e.get("fixes") or [])
                    if str(n).isdigit() and int(n) < len(todo)}
        after = to_design(layout, fmt, kinds)
        remaining = check_design(after, await _tags(after))
        still = {(f["element_id"], f["check"]) for f in remaining}
        todo = _dedupe([f for f in remaining if (f["element_id"], f["check"]) in
                        {(i["element_id"], i["check"]) for i in issues}])
        if not todo:
            break
    layout_path.write_text(json.dumps(layout, indent=1))

    # Code issues are re-measured. A vision issue counts as fixed when the fixer says it handled it
    # and code no longer measures a problem on that element (so "fixed" never contradicts a check).
    measured = {el for el, _ in still}
    fixed, open_ = [], []
    for f in issues:
        key = (f["element_id"], f["check"])
        gone = key not in still if f["source"] == "code" else key in claimed and f["element_id"] not in measured
        (fixed if gone else open_).append(f["message"])
    timer.lap("recheck")
    print(f"review {layout_path.name}: {timer.secs}", flush=True)
    return {"fixed": fixed, "issues": open_, "suggestions": suggestions, "secs": timer.secs}
