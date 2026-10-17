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
from pathlib import Path

import numpy as np
from scipy import ndimage
from PIL import Image, ImageFont

from config import GENERATED_DIR, IMAGE_MODEL, image_client
from designer import flash

ADS = GENERATED_DIR / "ads"
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
FONT_BOLD = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
FONT_REGULAR = "/System/Library/Fonts/Supplemental/Arial.ttf"


def _fit_size(text: str, bold: bool, box_w: float, start: int) -> int:
    """Largest size (≤ start) at which the longest line fits the box width in our font."""
    longest = max(text.split("\n"), key=len)
    for size in range(start, 11, -2):
        if ImageFont.truetype(FONT_BOLD if bold else FONT_REGULAR, size).getlength(longest) <= box_w:
            return size
    return 12


CALL_TIMEOUT = 60  # s per GPT call: a normal edit is ~15s; a stalled one is cut and retried once
_client = image_client.with_options(timeout=CALL_TIMEOUT, max_retries=0)


async def _edit(ad: Image.Image, prompt: str, transparent: bool) -> Image.Image:
    buf = io.BytesIO()
    ad.save(buf, "PNG")
    size = f"{ad.width}x{ad.height}"
    kwargs = {"model": IMAGE_MODEL, "image": [("ad.png", buf.getvalue(), "image/png")], "prompt": prompt,
              "size": size, "quality": "medium"}
    if transparent:
        kwargs |= {"background": "transparent", "output_format": "png"}  # proven to work on this endpoint
    last: Exception | None = None
    for attempt in range(2):
        try:
            r = await _client.images.edit(**kwargs)
            return Image.open(io.BytesIO(base64.b64decode(r.data[0].b64_json)))
        except Exception as err:  # a stall or a shared-endpoint hiccup: one more go, then give up
            last = err
            print(f"breaker call failed (attempt {attempt + 1}): {err!r}", flush=True)
    raise last  # type: ignore[misc]


def _is_blank(im: Image.Image) -> bool:
    """A cut-out with (almost) nothing opaque means the element wasn't there."""
    alpha = np.array(im.convert("RGBA"))[..., 3]
    return (alpha > 32).mean() < 0.001


SPLIT_APART = {"charm", "screen"}  # several separate things in one cut-out → one layer each
JOIN_GAP = 12  # px: pieces closer than this are one thing (a charm's sparkle lines, a phone and its shadow)
MIN_PIECE = 400  # px² of opaque pixels; smaller blobs are stray noise from the model


def _pieces(im: Image.Image) -> list[Image.Image]:
    """Split a transparent cut-out into its disconnected parts (each returned on the full canvas)."""
    rgba = np.array(im.convert("RGBA"))
    # GPT sometimes returns a faint haze over most of the canvas; the real element is the solid
    # part (alpha above half), kept with a thin soft edge around it.
    solid = rgba[..., 3] > 128
    soft = rgba[..., 3] > 32
    labels, count = ndimage.label(ndimage.binary_dilation(solid, iterations=JOIN_GAP))
    masks = [ndimage.binary_dilation((labels == i) & solid, iterations=3) & soft for i in range(1, count + 1)]
    sizes = [int(m.sum()) for m in masks]
    floor = max(MIN_PIECE, int(0.02 * max(sizes, default=0)))  # haze and specks next to a real piece
    pieces = []
    for m, size in zip(masks, sizes):
        if size < floor:
            continue
        part = rgba.copy()
        part[..., 3] = np.where(m, rgba[..., 3], 0)
        pieces.append(Image.fromarray(part, "RGBA"))
    return pieces or [im]


def _merged(pieces: list[Image.Image]) -> Image.Image:
    out = pieces[0]
    for p in pieces[1:]:
        out = Image.alpha_composite(out, p)
    return out


def _trim(im: Image.Image, pad: int = 4) -> tuple[Image.Image, tuple[int, int, int, int]]:
    """Crop a transparent cut-out to the pixels GPT drew → (cropped image, (x, y, w, h) on the canvas).

    Only the bounds of what came back are read; nothing is measured or guessed about the design.
    """
    rgba = im.convert("RGBA")
    ys, xs = np.nonzero(np.array(rgba)[..., 3] > 32)  # pieces are already haze-free here
    x0, y0 = max(int(xs.min()) - pad, 0), max(int(ys.min()) - pad, 0)
    x1, y1 = min(int(xs.max()) + pad + 1, rgba.width), min(int(ys.max()) + pad + 1, rgba.height)
    return rgba.crop((x0, y0, x1, y1)), (x0, y0, x1 - x0, y1 - y0)


async def plate(ad: Image.Image, elements: list[str]) -> Image.Image:
    """Everything that gets its own layer is removed here, so nothing appears twice in the stack."""
    removed = ", ".join(["the headline and all body text"] + [DESCRIBE[e] for e in elements])
    return await _edit(ad, f"The same image with these removed: {removed}. Fill the areas behind them with the "
                           "surrounding background and bloom shapes so it looks like they were never there. "
                           "Keep the background colours and bloom shapes exactly as they are. Same size, same "
                           "framing. No text, no logo, no people, no devices anywhere.", transparent=False)


async def cutout(ad: Image.Image, element: str) -> Image.Image:
    return await _edit(ad, f"Keep ONLY {DESCRIBE[element]}, exactly where it is, at the same size and the same "
                           "pixels; make everything else in the image fully transparent. Same canvas size. "
                           "Do not add, move or redraw anything.", transparent=True)


async def read_text(ad: Image.Image) -> list[dict]:
    """Flash reads the words: the only non-GPT step, so text becomes retypable."""
    reply = await flash(
        "You read the text on a finished ad precisely. Reply with JSON only.",
        ["List the ad's own text blocks: role headline | body | button. Skip the brand logo wordmark ('xero') "
         "and skip any text that is inside a product screen, phone, tablet or laptop (dashboard numbers, labels). "
         "For each block give the exact words (keep line "
         "breaks as \\n), the box [x, y, w, h] in 0-1000 units of the canvas (tight around the text), the number of "
         "lines, bold true/false, colour as hex (#000856 navy, #FFFFFF white, or what you see), and alignment "
         "left|center. For a button also give its pill fill colour as pill_fill.\n"
         'Reply: {"blocks": [{"role": "headline", "text": "...", "box": [60, 700, 880, 180], "lines": 2, '
         '"bold": true, "colour": "#000856", "align": "left", "pill_fill": null}]}',
         ("ad", ad)])
    blocks = [b for b in reply.get("blocks", []) if b.get("text") and len(b.get("box") or []) == 4]
    blocks = [b for b in blocks if b["text"].strip().lower() != "xero"]  # the wordmark is its own cut-out
    blocks = [b for b in blocks if b.get("role") in TEXT_ROLES][:6]  # never the tiny screen text
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
        lines = max(1, int(b.get("lines") or 1))
        bold = bool(b.get("bold", b.get("role") == "headline"))
        # Start from the line height, then shrink so our (wider) Arial keeps GPT's line breaks.
        font_size = _fit_size(b["text"], bold, bw * w, round(bh * h / (lines * 1.15)))
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
                                 "weight": "bold" if bold else "medium",
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
    return await split_image(ADS / f"{design_id}.png", ADS / design_id, f"/generated/ads/{design_id}", plan)


async def split_image(image_path, out: Path, url_base: str, plan: dict | None = None) -> dict:
    """Any flat picture → layers. url_base is where `out` is served (the layer PNGs go in there).

    Used by the create flow (plan known) and by the chat ("break this up": plan None → every
    element kind is tried; blank cut-outs are dropped).
    """
    ad = Image.open(image_path).convert("RGB")
    w, h = ad.size
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    elements = _elements(plan)

    base_plate, blocks, *cuts = await asyncio.gather(plate(ad, elements), read_text(ad), *[cutout(ad, e) for e in elements])
    base_plate.convert("RGB").save(out / "plate.png")

    def image_layer(name: str, z: float, hidden: bool = False, role: str | None = None,
                    box: tuple[int, int, int, int] = (0, 0, w, h)) -> dict:
        x, y, bw, bh = box
        return {"id": name, "role": role or name, "type": "image", "x": x, "y": y, "w": bw, "h": bh, "z": z,
                "props": {"src": f"{url_base}/{name}.png", "clip": None, "hidden": hidden}}

    ad.save(out / "original.png")
    layers = [image_layer("original", 0, hidden=True), image_layer("plate", 1, role="background")]
    z = 2.0
    has_button_text = any(b.get("role") == "button" for b in blocks)
    for element, im in zip(elements, cuts):
        if _is_blank(im) or (element == "button" and has_button_text):  # the retypable pill replaces the cut-out
            continue
        pieces = _pieces(im)  # real pieces only: stray haze no longer inflates the box
        parts = pieces if element in SPLIT_APART else [_merged(pieces)]
        for k, part in enumerate(parts):
            name = element if len(parts) == 1 else f"{element}_{k + 1}"
            cropped, box = _trim(part)  # tight bounds, so selecting the layer selects just that element
            cropped.save(out / f"{name}.png")
            layers.append(image_layer(name, z, role=element, box=box))
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
        full = Image.new("RGBA", (layout["width"], layout["height"]), (0, 0, 0, 0))
        full.paste(im, (int(l["x"]), int(l["y"])))
        stack = full if stack is None else Image.alpha_composite(stack, full)
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
