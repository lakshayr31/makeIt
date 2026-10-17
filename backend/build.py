"""Matched variants → solved layers: resolve asset files, generate missing images, run the solver.

Writes backend/runs/<ad>/layout_<i>.json (canvas-ready layers) per variant.
Run: backend/.venv/bin/python backend/build.py backend/runs/<ad>
"""

import asyncio
import base64
import hashlib
import io
import json
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

from PIL import Image

from config import GENERATED_DIR, IMAGE_MODEL, ROOT, image_client
from layout import solve

CATALOG = ROOT / "assets/brand-kit/catalog.json"


def _local(url: str) -> Path:
    """'/assets/..' or '/generated/..' URL → file on disk."""
    if url.startswith("/generated/"):
        return GENERATED_DIR / url.removeprefix("/generated/")
    return ROOT / url.lstrip("/")


def open_image(url: str) -> Image.Image:
    path = _local(url)
    if path.suffix == ".svg":
        png = subprocess.run(["rsvg-convert", "-w", "1024", str(path)],
                             capture_output=True, check=True).stdout
        return Image.open(io.BytesIO(png)).convert("RGBA")
    return Image.open(path).convert("RGBA")


def _image_size(box: list[float]) -> str:
    """Closest supported generation size to the slot's on-canvas aspect (4:5 canvas)."""
    aspect = (box[2] * 4) / (box[3] * 5)
    return "1536x1024" if aspect > 1.2 else "1024x1536" if aspect < 0.83 else "1024x1024"


async def _generate(prompt: str, size: str, transparent: bool) -> str:
    """GPT Image → /generated URL. Cached by prompt so variants sharing a hero reuse it."""
    name = hashlib.sha1(f"{prompt}|{size}|{transparent}".encode()).hexdigest()[:16] + ".png"
    if not (GENERATED_DIR / name).exists():
        result = await image_client.images.generate(
            model=IMAGE_MODEL, prompt=prompt, size=size, quality="medium",
            background="transparent" if transparent else "opaque", output_format="png",
        )
        (GENERATED_DIR / name).write_bytes(base64.b64decode(result.data[0].b64_json))
    return f"/generated/{name}"


def _resolve_asset(slot: dict, catalog: dict) -> str | None:
    """Catalog asset → URL of the chosen colour variant (falls back to a valid colour)."""
    entry = catalog.get(slot.get("asset_id"))
    if not entry:
        return None
    variants = entry.get("variants")
    if not variants:
        return entry["url"]
    if slot.get("colour") not in variants:
        slot["colour"] = next(iter(variants))  # matcher picked a colour this shape lacks
    return variants[slot["colour"]]


async def build(run: Path) -> list[list[dict]]:
    catalog = {e["id"]: e for e in json.loads(CATALOG.read_text())}
    variants = json.loads((run / "variants.json").read_text())["variants"]

    jobs: dict[tuple, asyncio.Task] = {}
    for v in variants:
        for slot in v["slots"]:
            if slot.get("match") == "generated" and slot.get("prompt"):
                key = (slot["prompt"], _image_size(slot["box"]), bool(slot.get("transparent")))
                if key not in jobs:
                    jobs[key] = asyncio.create_task(_generate(*key))
    if jobs:
        print(f"generating {len(jobs)} image(s)…", flush=True)
    for v in variants:
        for slot in v["slots"]:
            if slot.get("match") == "dropped":
                continue
            if slot.get("match") == "generated" and slot.get("prompt"):
                key = (slot["prompt"], _image_size(slot["box"]), bool(slot.get("transparent")))
                slot["src"] = await jobs[key]
            elif slot.get("asset_id"):
                slot["src"] = _resolve_asset(slot, catalog)

    layouts = []
    for i, v in enumerate(variants):
        aspects = {}
        for slot in v["slots"]:
            if slot.get("src"):
                img = open_image(slot["src"])
                aspects[slot["id"]] = img.width / img.height
        layers = [asdict(l) for l in solve(v, aspects)]
        (run / f"layout_{i}.json").write_text(json.dumps(
            {"axis": v.get("axis"), "background_colour": v.get("background_colour"),
             "layers": layers}, indent=1))
        layouts.append(layers)
    return layouts


if __name__ == "__main__":
    asyncio.run(build(Path(sys.argv[1])))
