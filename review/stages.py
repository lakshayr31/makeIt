"""Stages 1, 3, 4 — the AI parts (DeepSeek-V4.1-Flash)."""

import asyncio
import base64
import hashlib
import io
import json
import os
import re

from openai import AsyncOpenAI
from PIL import Image, ImageDraw, ImageFont

from review.design import ROOT, crop_with_margin

PROMPTS = ROOT / "prompts" / "v2"
TAG_CACHE = ROOT / "assets" / "tags"
GRID = 8
VISION_PROMPT = {
    "text": "vision_text",
    "button": "vision_text",
    "logo": "vision_logo",
    "bloom": "vision_bloom",
    "charm": "vision_charm_illustration",
    "illustration": "vision_charm_illustration",
    "photo": "vision_photo",
    "product": "vision_photo",
    "card": "vision_photo",
}
RULE_SECTIONS = {
    "vision_text": ("typography", "colour", "layout"),
    "vision_logo": ("logo",),
    "vision_bloom": ("shapes",),
    "vision_charm_illustration": ("illustration", "charms"),
    "vision_photo": ("shapes", "product ui"),
}

_client = None
_sem = asyncio.Semaphore(12)


def client():
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            base_url=os.environ["DEEPSEEK_FLASH_BASE_URL"],
            api_key=os.environ["DEEPSEEK_FLASH_API_KEY"],
            timeout=20,  # a normal call is ~6s; a hung one is cut and retried by ask()
            max_retries=0,  # ask() retries itself
        )
    return _client


def b64(img, max_side=1280):
    img = img.convert("RGB")
    img.thumbnail((max_side, max_side))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


async def ask(system, parts):
    """One Flash call → parsed JSON. parts: list of str | (label, PIL.Image)."""
    content = []
    for p in parts:
        if isinstance(p, str):
            content.append({"type": "text", "text": p})
        else:
            content.append({"type": "text", "text": f"Image `{p[0]}`:"})
            content.append({"type": "image_url", "image_url": {"url": b64(p[1])}})
    async with _sem:
        for attempt in range(4):
            try:
                r = await client().chat.completions.create(
                    model=os.environ["DEEPSEEK_FLASH_MODEL"],
                    response_format={"type": "json_object"},
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": content},
                    ],
                )
                return json.loads(r.choices[0].message.content)
            except Exception as e:  # 429s on the shared endpoint, or bad JSON
                last = e
                await asyncio.sleep(2 * (attempt + 1))
    raise last


# --- Stage 1: tag ------------------------------------------------------------


def _grid(img):
    img = img.convert("RGBA")
    bg = Image.new("RGBA", img.size, "#ffffff")
    bg.alpha_composite(img)
    d = ImageDraw.Draw(bg)
    f = ImageFont.load_default(size=max(12, img.width // 40))
    cw, ch = img.width / GRID, img.height / GRID
    for i in range(1, GRID):
        d.line([(i * cw, 0), (i * cw, img.height)], fill="#ff2d55", width=2)
        d.line([(0, i * ch), (img.width, i * ch)], fill="#ff2d55", width=2)
    for c in range(GRID):
        for r in range(GRID):
            d.text(
                (c * cw + 4, r * ch + 2),
                f"{'ABCDEFGH'[c]}{r + 1}",
                fill="#ff2d55",
                font=f,
            )
    return bg


def _cells_to_box(cells):
    cols = [ord(c[0].upper()) - 65 for c in cells if re.fullmatch(r"[A-Ha-h][1-8]", c)]
    rows = [int(c[1]) - 1 for c in cells if re.fullmatch(r"[A-Ha-h][1-8]", c)]
    if not cols:
        return None
    return [
        min(cols) / GRID,
        min(rows) / GRID,
        (max(cols) - min(cols) + 1) / GRID,
        (max(rows) - min(rows) + 1) / GRID,
    ]


async def tag_asset(asset):
    path = ROOT / asset
    key = hashlib.sha1(path.read_bytes()).hexdigest()[:16]
    cache = TAG_CACHE / f"{key}.json"
    if cache.exists():
        return json.loads(cache.read_text())
    img = Image.open(path)
    reply = await ask(
        (PROMPTS / "tagger.md").read_text(),
        [
            f"Asset file: {path.name}\nFolder: {path.parent.name}",
            ("asset_with_grid", _grid(img)),
        ],
    )
    for region in reply.get("regions", []):
        region["box"] = _cells_to_box(region.get("cells", []))
    reply["regions"] = [r for r in reply.get("regions", []) if r["box"]]
    TAG_CACHE.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(reply, indent=1))
    return reply


# --- Stage 3: vision per element type ----------------------------------------


BLOOM_PROMPTS = {"vision_bloom", "vision_photo"}
BLOOM_PAGES = [ROOT / "assets/brand-kit/06_Shapes_Cropping_Blooms/06_Shapes_Cropping_Blooms" / n
               for n in ("03_03_cropping_and_frames.png", "06_06_blooms_in_photography.png")]


def _bloom_playbook():
    path = ROOT / "prompts" / "brand-guide" / "blooms_playbook.md"
    return "\n\nBlooms playbook (how Xero uses blooms):\n" + path.read_text() if path.exists() else ""


def _rules_excerpt(sections):
    md = (ROOT / "assets" / "brand-rules" / "brand-rules.md").read_text()
    parts = re.split(r"(?m)^## ", md)
    return "\n".join(
        "## " + p
        for p in parts
        if p.split("\n")[0].strip().lower().startswith(sections)
    )


async def vision_checks(design, img, tags, funnel_stage="ad", raw_replies=None):
    """Fail findings per element type. Pass a list as raw_replies to also collect every full reply."""
    groups = {}
    for el in design["elements"]:
        if el["type"] in VISION_PROMPT:
            groups.setdefault(VISION_PROMPT[el["type"]], []).append(el)
    context = img.copy()
    context.thumbnail((640, 640))

    async def run(prompt, els):
        parts = [
            f"canvas: {json.dumps(design['canvas'])}\nfunnel_stage: {funnel_stage}\n"
            "Code checks (geometry, palette, safe zones, overlaps, cut-off tagged regions, stretch, "
            "resolution, contrast) are already done — do not repeat them.\n\nBrand rules:\n"
            + _rules_excerpt(RULE_SECTIONS[prompt])
            + (_bloom_playbook() if prompt in BLOOM_PROMPTS else ""),
            ("context", context),
        ]
        if prompt in BLOOM_PROMPTS:
            parts += [(f"brand_page_{p.stem}", Image.open(p)) for p in BLOOM_PAGES if p.exists()]
        for el in els:
            meta = {
                k: el.get(k) for k in ("id", "type", "bbox", "text", "font", "fill")
            }
            meta["source_asset"] = el.get("asset")
            meta["tags"] = tags.get(el.get("asset"))
            parts += [
                f"element: {json.dumps(meta)}",
                (f"crop_{el['id']}", crop_with_margin(img, el["bbox"])),
            ]
        reply = await ask((PROMPTS / f"{prompt}.md").read_text(), parts)
        if raw_replies is not None:
            raw_replies.append({"prompt": prompt, "reply": reply})
        found = []
        for item in reply.get("items", []):
            for chk in item.get("checks", []):
                if chk.get("verdict") == "fail":
                    found.append(
                        {
                            "element_id": str(item.get("element_id")),
                            "check": chk.get("check"),
                            "severity": chk.get("severity"),
                            "message": chk.get("message"),
                            "evidence": chk.get("evidence"),
                            "observations": item.get("observations"),
                            "source": prompt,
                            "auto_fix": False,
                        }
                    )
        return found

    results = await asyncio.gather(*[run(p, els) for p, els in groups.items()])
    return [f for r in results for f in r]


# --- Stage 4: verify -----------------------------------------------------------


async def verify(findings, design, img, max_rounds=2):
    """Second opinion on each vision fail. High-severity claims are checked twice (agreement signal)."""
    by_id = {e["id"]: e for e in design["elements"]}
    context = img.copy()
    context.thumbnail((640, 640))
    system = (PROMPTS / "verifier.md").read_text()

    async def ask_once(f, el):
        claim = {k: f.get(k) for k in ("check", "message", "evidence")}
        claim["element"] = {k: el.get(k) for k in ("id", "type", "bbox", "text")}
        return await ask(system, [f"claim: {json.dumps(claim)}",
                                  ("crop", crop_with_margin(img, el["bbox"])), ("context", context)])

    async def one(f):
        el = by_id.get(f["element_id"])
        if not el:
            return {**f, "verified": "false", "verify_evidence": "unknown element id", "verify_votes": []}
        rounds = min(max_rounds, 2 if f.get("severity") == "high" else 1)
        replies = await asyncio.gather(*[ask_once(f, el) for _ in range(rounds)])
        votes = [{"verdict": r.get("verdict"), "confidence": r.get("confidence")} for r in replies]
        first = replies[0]
        return {**f, "verified": first.get("verdict"), "verify_confidence": first.get("confidence"),
                "verify_evidence": first.get("evidence"), "verify_votes": votes}

    return await asyncio.gather(*[one(f) for f in findings])
