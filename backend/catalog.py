"""Cataloguer: one-off pass that gives every usable brand asset matching metadata.

Buckets are decided by source folder (code); meaning (name, subjects, concepts,
mood, text-safe area) comes from Flash. Charms and blooms are catalogued once
per shape, with their colour variants listed. Guideline sheets are skipped.

Output: assets/brand-kit/catalog.json
Run: backend/.venv/bin/python backend/catalog.py [--force]
Needs: backend/split_sheets.py run first (assets/brand-kit/parts/).
"""

import asyncio
import base64
import io
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image

from agent import complete_json
from config import ASSETS_DIR

KIT = ASSETS_DIR / "brand-kit"
PARTS = KIT / "parts"
OUT = KIT / "catalog.json"
CONCURRENCY = 8
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".svg"}

# (folder glob, bucket, kind). Folders not listed (guidelines, safe zones, bloom
# reference sheets) are reference-only and stay out of the catalogue.
SINGLE_SOURCES = [
    ("24_Background_Templates", "background", "background_template"),
    ("07_Illustration", "fixed", "illustration"),
    ("11_Product_UI_References", "fixed", "product_ui"),
    ("10_Logo", "fixed", "logo"),
    ("22_Charms", "charm", "charm"),
]
SHEET_FILES = {"08_0dad3276-a933-47e9-9154-8958bc31193d.png"}  # split into parts/

PROMPT = """You catalogue one Xero brand asset so a design agent can later pick it for an ad.
Bucket: {bucket} ({bucket_hint}). Kind: {kind}. Source file: {file}.

Return JSON only:
{{
  "placeable": true unless this is a reference/guideline sheet or a grid of many icons,
  "name": "2-4 word name, e.g. 'padlock charm', 'invoice dashboard', 'navy blob template'",
  "description": "one sentence: what it literally shows",
  "subjects": ["3-6 concrete nouns visible in it"],
  "concepts": ["2-5 marketing ideas it can stand for, e.g. security, getting paid, saving time, growth"],
  "mood": "calm" | "playful" | "energetic" | "professional",
  "visual_weight": "light" | "medium" | "heavy",
  "text_safe_area": "where headline text could sit on it without clashing, e.g. 'top 40% plain blue'; 'n/a' for small elements",
  "usage_note": "one sentence on how a designer would use it (crop, scale, layer, pair with)"
}}"""

BUCKET_HINTS = {
    "background": "sits at the back of the ad",
    "fixed": "artwork used as-is, never recoloured",
    "charm": "small foreground accent icon",
}


COLOUR_WORDS = {"blue", "light", "lightblue", "navy", "green", "yellow", "pink", "purple"}


def _colourless(name: str) -> str:
    """Charm/bloom colour is a choice, not part of the shape's name."""
    return " ".join(w for w in name.split() if w.lower() not in COLOUR_WORDS) or name


def _load(path: Path) -> Image.Image:
    if path.suffix.lower() == ".svg":
        png = subprocess.run(
            ["rsvg-convert", "-w", "1024", str(path)], capture_output=True, check=True
        ).stdout
        return Image.open(io.BytesIO(png))
    return Image.open(path)


def _url(path: Path) -> str:
    return "/assets/" + path.relative_to(ASSETS_DIR).as_posix()


def _file_facts(img: Image.Image) -> dict:
    """Size, transparency, and the bounding box of visible pixels (0-1 fractions)."""
    rgba = img.convert("RGBA")
    w, h = rgba.size
    alpha = rgba.getchannel("A")
    box = alpha.point(lambda a: 255 if a > 16 else 0).getbbox() or (0, 0, w, h)
    return {
        "width": w,
        "height": h,
        "aspect": round(w / h, 3),
        "has_transparency": alpha.getextrema()[0] < 250,
        "content_box": [
            round(box[0] / w, 3),
            round(box[1] / h, 3),
            round((box[2] - box[0]) / w, 3),
            round((box[3] - box[1]) / h, 3),
        ],
    }


def _data_url(img: Image.Image) -> str:
    """Downscaled PNG on light grey so transparent shapes stay visible."""
    rgba = img.convert("RGBA")
    rgba.thumbnail((768, 768))
    if max(rgba.size) < 256:  # tiny charms: upscale so the model can read them
        rgba = rgba.resize((rgba.width * 3, rgba.height * 3), Image.LANCZOS)
    bg = Image.new("RGBA", rgba.size, (235, 235, 235, 255))
    bg.alpha_composite(rgba)
    buf = io.BytesIO()
    bg.convert("RGB").save(buf, "PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def _items() -> list[dict]:
    """Every asset to catalogue: {id, bucket, kind, preview path, variants}."""
    items = []
    for folder, bucket, kind in SINGLE_SOURCES:
        files = sorted(
            p
            for p in (KIT / folder).rglob("*")
            if p.suffix.lower() in IMAGE_EXTS and p.name not in SHEET_FILES
        )
        for i, path in enumerate(files, start=1):
            items.append(
                {
                    "id": f"{kind}-{i:02d}",
                    "bucket": bucket,
                    "kind": kind,
                    "preview": path,
                    "variants": None,
                }
            )
    for kind, bucket in (("charms", "charm"), ("blooms", "background")):
        for shape_dir in sorted((PARTS / kind).iterdir()):
            variants = {p.stem: _url(p) for p in sorted(shape_dir.glob("*.png"))}
            preview = shape_dir / (
                "blue.png" if "blue" in variants else next(iter(variants)) + ".png"
            )
            items.append(
                {
                    "id": f"{kind[:-1]}-{shape_dir.name}",
                    "bucket": bucket,
                    "kind": kind[:-1],
                    "preview": preview,
                    "variants": variants,
                }
            )
    return items


# Order matches the 12 named blooms on brand-book page 06/02_blooms_set.
BLOOM_NAMES = {
    f"bloom-{i:02d}": f"{name} Bloom"
    for i, name in enumerate(
        ["Peace", "Energy", "X", "Spark", "Grow", "Pulse",
         "Harmony", "Motion", "Balance", "Ease", "Surge", "Stride"], start=1)
}


async def _catalogue(item: dict, sem: asyncio.Semaphore) -> dict:
    img = _load(item["preview"])
    entry = {
        "id": item["id"],
        "bucket": item["bucket"],
        "kind": item["kind"],
        "url": _url(item["preview"]),
        **_file_facts(img),
    }
    if item["variants"]:
        entry["colours_available"] = list(item["variants"])
        entry["variants"] = item["variants"]
    prompt = PROMPT.format(
        bucket=item["bucket"],
        bucket_hint=BUCKET_HINTS[item["bucket"]],
        kind=item["kind"],
        file=item["preview"].name,
    )
    async with sem:
        meta = await complete_json(
            "flash",
            [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": _data_url(img)}},
                    ],
                }
            ],
        )
    if item["variants"] and meta.get("name"):
        meta["name"] = _colourless(meta["name"])
    if entry["id"] in BLOOM_NAMES:  # brand-book names (page 02), so agents can pick by personality
        meta["name"] = BLOOM_NAMES[entry["id"]]
    print(f"  {entry['id']}: {meta.get('name')}", flush=True)
    return {**entry, **meta}


async def main(force: bool) -> None:
    done = (
        {}
        if force or not OUT.exists()
        else {e["id"]: e for e in json.loads(OUT.read_text())}
    )
    todo = [it for it in _items() if it["id"] not in done]
    print(f"{len(done) + len(todo)} assets, {len(todo)} to catalogue")
    sem = asyncio.Semaphore(CONCURRENCY)
    results = await asyncio.gather(
        *(_catalogue(it, sem) for it in todo), return_exceptions=True
    )
    for it, res in zip(todo, results):
        if isinstance(res, BaseException):
            print(f"  FAILED {it['id']}: {res}")
        else:
            done[res["id"]] = res
    OUT.write_text(json.dumps(sorted(done.values(), key=lambda e: e["id"]), indent=1))
    print(f"wrote {len(done)} entries → {OUT}")


if __name__ == "__main__":
    asyncio.run(main("--force" in sys.argv))
