"""Breaker: split a finished ad into editable layers whose stack looks the same as the ad.

GPT Image does all the pixel work, each element kept exactly where it was drawn:
  plate      the ad with text, logo and charms removed (bottom layer)
  cut-outs   one transparent full-canvas image per element (logo, button, charms, screens, picture)
Flash is used ONLY to read the text (words, box, colour), so headline / body / button become real
text boxes the user can retype. The original ad stays as a hidden bottom layer, so a design is never
worse than before. No layout code: nothing is measured or re-placed from our asset files.
"""

import asyncio
import base64
import io
import json

import numpy as np
from PIL import Image

from config import GENERATED_DIR, IMAGE_MODEL, image_client
from designer import flash

ADS = GENERATED_DIR / "ads"
MAGENTA = (255, 0, 255)
# Which elements get a cut-out, in stacking order (bottom → top), and how to name them to GPT.
CUTOUT_ORDER = ["picture", "screen", "charm", "logo", "button"]
DESCRIBE = {
    "picture": "the main picture (photo, illustration or object), not the background or blooms",
    "screen": "the product screen(s): every tablet, phone or laptop showing an app",
    "charm": "the small decorative charms / stickers / icons",
    "logo": "the brand logo wordmark (and its pill if it has one)",
    "button": "the call-to-action button (pill with its label)",
}
TEXT_ROLES = ("headline", "body", "button")


async def _edit(ad: Image.Image, prompt: str, transparent: bool) -> Image.Image:
    buf = io.BytesIO()
    ad.save(buf, "PNG")
    size = f"{ad.width}x{ad.height}"
    kwargs = {"model": IMAGE_MODEL, "image": [("ad.png", buf.getvalue(), "image/png")], "prompt": prompt,
              "size": size, "quality": "medium"}
    if transparent:
        try:
            r = await image_client.images.edit(**kwargs, background="transparent", output_format="png")
        except Exception:  # this model/endpoint has no transparent edits: key out a magenta field instead
            r = await image_client.images.edit(**kwargs, prompt=prompt.replace("fully transparent", "flat solid #FF00FF magenta"))
            return _key_out(Image.open(io.BytesIO(base64.b64decode(r.data[0].b64_json))))
    else:
        r = await image_client.images.edit(**kwargs)
    return Image.open(io.BytesIO(base64.b64decode(r.data[0].b64_json)))


def _key_out(im: Image.Image, tolerance: int = 60) -> Image.Image:
    """Magenta → transparent (fallback when the edit endpoint can't return alpha)."""
    rgba = np.array(im.convert("RGBA")).astype(int)
    dist = np.abs(rgba[..., :3] - np.array(MAGENTA)).sum(axis=-1)
    rgba[..., 3] = np.where(dist < tolerance, 0, 255)
    return Image.fromarray(rgba.astype("uint8"), "RGBA")


def _is_blank(im: Image.Image) -> bool:
    """A cut-out with (almost) nothing opaque means the element wasn't there."""
    alpha = np.array(im.convert("RGBA"))[..., 3]
    return (alpha > 32).mean() < 0.001


async def plate(ad: Image.Image) -> Image.Image:
    return await _edit(ad, "The same image with the headline, all body text, the call-to-action button, the brand "
                           "logo (the 'xero' wordmark and its pill, wherever it is) and the small charms/stickers removed, "
                           "the areas behind them filled in to match. "
                           "Keep the background, blooms, main picture and product screens exactly as they are. "
                           "Same size, same framing. No text anywhere.", transparent=False)


async def cutout(ad: Image.Image, element: str) -> Image.Image:
    return await _edit(ad, f"Keep ONLY {DESCRIBE[element]}, exactly where it is, at the same size and the same "
                           "pixels; make everything else in the image fully transparent. Same canvas size. "
                           "Do not add, move or redraw anything.", transparent=True)


async def read_text(ad: Image.Image) -> list[dict]:
    """Flash reads the words: the only non-GPT step, so text becomes retypable."""
    reply = await flash(
        "You read the text on a finished ad precisely. Reply with JSON only.",
        ["List every text block: role headline | body | button | other. The brand logo wordmark ('xero') is NOT "
         "text: skip it. For each block give the exact words (keep line "
         "breaks as \\n), the box [x, y, w, h] in 0-1000 units of the canvas (tight around the text), the number of "
         "lines, bold true/false, colour as hex (#000856 navy, #FFFFFF white, or what you see), and alignment "
         "left|center. For a button also give its pill fill colour as pill_fill.\n"
         'Reply: {"blocks": [{"role": "headline", "text": "...", "box": [60, 700, 880, 180], "lines": 2, '
         '"bold": true, "colour": "#000856", "align": "left", "pill_fill": null}]}',
         ("ad", ad)])
    blocks = [b for b in reply.get("blocks", []) if b.get("text") and len(b.get("box") or []) == 4]
    blocks = [b for b in blocks if b["text"].strip().lower() != "xero"]  # the wordmark is its own cut-out
    for b in blocks:  # GPT draws Xero text navy; a near-black read is navy
        if _is_dark(b.get("colour")):
            b["colour"] = "#000856"
    return blocks


def _is_dark(colour) -> bool:
    try:
        r, g, b = (int(str(colour).lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
    except (ValueError, TypeError):
        return False
    return r + g + b < 150


def _text_layers(blocks: list[dict], w: int, h: int, z: float) -> list[dict]:
    layers = []
    for i, b in enumerate(blocks):
        bx, by, bw, bh = (v / 1000 for v in b["box"])
        bw *= 1.12  # our Arial is wider than GPT's condensed lettering: keep the same line breaks
        lines = max(1, int(b.get("lines") or 1))
        font_size = round(bh * h / (lines * 1.15))
        role = b.get("role", "other")
        if role == "button":
            layers.append({"id": f"button_{i}", "role": "cta", "type": "text", "x": bx * w, "y": by * h,
                           "w": bw * w, "h": bh * h, "z": z + i * 0.01,
                           "props": {"text": b["text"], "font_size": round(bh * h * 0.42), "weight": "bold",
                                     "colour": b.get("colour") or "#FFFFFF", "fill": b.get("pill_fill") or "#000856",
                                     "pill": True}})
            continue
        layers.append({"id": f"{role}_{i}", "role": role, "type": "text", "x": bx * w, "y": by * h,
                       "w": bw * w, "h": bh * h, "z": z + i * 0.01,
                       "props": {"text": b["text"], "font_size": font_size,
                                 "weight": "bold" if b.get("bold", role == "headline") else "medium",
                                 "colour": b.get("colour") or "#000856"}})
    return layers


def _elements(plan: dict | None) -> list[str]:
    """Which cut-outs to make, from the job's plan (everything if there is no plan)."""
    if not plan:
        return CUTOUT_ORDER
    hi = plan.get("highlights") or {}
    wanted = ["logo"]
    if (hi.get("main_picture") or {}).get("source", "none") != "none":
        wanted.append("picture")
    if hi.get("product_ui"):
        wanted.append("screen")
    if hi.get("charms"):
        wanted.append("charm")
    if (hi.get("text") or {}).get("cta"):
        wanted.append("button")
    return [e for e in CUTOUT_ORDER if e in wanted]


async def split(design_id: str, plan: dict | None) -> dict:
    """Finished ad → SolvedLayout (the editor's layer format). Writes the layer PNGs next to the ad."""
    ad = Image.open(ADS / f"{design_id}.png").convert("RGB")
    w, h = ad.size
    out = ADS / design_id
    out.mkdir(exist_ok=True)
    elements = _elements(plan)

    base_plate, blocks, *cuts = await asyncio.gather(plate(ad), read_text(ad), *[cutout(ad, e) for e in elements])
    base_plate.convert("RGB").save(out / "plate.png")

    def image_layer(name: str, z: float, hidden: bool = False, role: str | None = None) -> dict:
        return {"id": name, "role": role or name, "type": "image", "x": 0, "y": 0, "w": w, "h": h, "z": z,
                "props": {"src": f"/generated/ads/{design_id}/{name}.png", "clip": None, "hidden": hidden}}

    ad.save(out / "original.png")
    layers = [image_layer("original", 0, hidden=True), image_layer("plate", 1, role="background")]
    z = 2.0
    for element, im in zip(elements, cuts):
        if _is_blank(im):
            continue
        im.save(out / f"{element}.png")
        layers.append(image_layer(element, z))
        z += 1
    # Text: real text boxes; the GPT-drawn text is not kept (it is part of what the plate removed).
    layers += _text_layers(blocks, w, h, z)
    return {"axis": "split", "background_colour": "#FFFFFF", "width": w, "height": h, "layers": layers,
            "elements": elements, "text_blocks": len(blocks)}


async def render_check(layout: dict, design_id: str) -> float:
    """Mean abs difference (0-255) between the stacked visible image layers and the original ad."""
    out = ADS / design_id
    stack = None
    for l in sorted(layout["layers"], key=lambda x: x["z"]):
        if l["type"] != "image" or l["props"].get("hidden"):
            continue
        im = Image.open(out / f"{l['id']}.png").convert("RGBA")
        stack = im if stack is None else Image.alpha_composite(stack, im)
    if stack is None:
        return 255.0
    a = np.array(stack.convert("RGB").resize((256, 256))).astype(int)
    b = np.array(Image.open(out / "original.png").convert("RGB").resize((256, 256))).astype(int)
    return float(np.abs(a - b).mean())


if __name__ == "__main__":
    import sys

    did = sys.argv[1]
    run = GENERATED_DIR / "runs" / f"job_{did.split('-')[3]}" / "plan.json"
    p = json.loads(run.read_text()) if run.exists() else None
    lay = asyncio.run(split(did, p))
    print(json.dumps({k: v for k, v in lay.items() if k != "layers"}), [l["id"] for l in lay["layers"]])
    print("diff vs original (image layers only):", round(asyncio.run(render_check(lay, did)), 1))
