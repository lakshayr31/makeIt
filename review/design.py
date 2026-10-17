"""Design format, renderer and geometry helpers for the review pipeline.

A design is JSON: {"id", "canvas": {"w","h","format","bg"}, "elements": [...]}.
Element: {"id","type","z","bbox":[x,y,w,h], "asset": path | null, "crop": [x,y,w,h] in source px | null,
          "text", "font": {"size","color","bold"}, "fill", "radius"}.
"""

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
FONT_BOLD = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
FONT_REGULAR = "/System/Library/Fonts/Supplemental/Arial.ttf"


def load(path):
    return json.loads(Path(path).read_text())


def font(size, bold=True):
    return ImageFont.truetype(FONT_BOLD if bold else FONT_REGULAR, int(size))


def text_lines(el):
    return (el.get("text") or "").split("\n")


def text_size(el):
    """Width and height the element's text actually needs."""
    f = font(el["font"]["size"], el["font"].get("bold", True))
    lines = text_lines(el)
    widths = [f.getbbox(line)[2] for line in lines]
    return max(widths), int(len(lines) * el["font"]["size"] * 1.1)


def asset_image(el):
    im = Image.open(ROOT / el["asset"]).convert("RGBA")
    if el.get("crop"):
        x, y, w, h = el["crop"]
        im = im.crop((x, y, x + w, y + h))
    return im


def _draw_text(d, el, box_left, box_top, box_w, box_h, centre):
    f = font(el["font"]["size"], el["font"].get("bold", True))
    lines = text_lines(el)
    line_h = el["font"]["size"] * 1.1
    top = box_top + (box_h - line_h * len(lines)) / 2 if centre else box_top
    for i, line in enumerate(lines):
        w = f.getbbox(line)[2]
        left = box_left + (box_w - w) / 2 if centre else box_left
        d.text((left, top + i * line_h), line, font=f, fill=el["font"]["color"])


def render(design, skip_ids=(), max_z=None):
    """Render the design. skip_ids / max_z let checks see what sits *behind* an element."""
    c = design["canvas"]
    im = Image.new("RGBA", (c["w"], c["h"]), c.get("bg", "#ffffff"))
    for el in sorted(design["elements"], key=lambda e: e["z"]):
        if el["id"] in skip_ids or (max_z is not None and el["z"] >= max_z):
            continue
        x, y, w, h = [int(v) for v in el["bbox"]]
        if el.get("asset"):
            src = asset_image(el).resize((max(w, 1), max(h, 1)), Image.LANCZOS)
            im.alpha_composite(src, (x, y)) if x >= 0 and y >= 0 else _paste_clipped(
                im, src, x, y
            )
            continue
        layer = Image.new("RGBA", im.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        if el.get("fill"):
            d.rounded_rectangle(
                [x, y, x + w, y + h], el.get("radius", 0), fill=el["fill"]
            )
        if el.get("text"):
            _draw_text(d, el, x, y, w, h, centre=el["type"] == "button")
        im.alpha_composite(layer)
    return im


def _paste_clipped(canvas, src, x, y):
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    layer.paste(src, (x, y), src)
    canvas.alpha_composite(layer)


# --- geometry ---------------------------------------------------------------


def area(b):
    return max(0, b[2]) * max(0, b[3])


def intersect(a, b):
    x1, y1 = max(a[0], b[0]), max(a[1], b[1])
    x2, y2 = min(a[0] + a[2], b[0] + b[2]), min(a[1] + a[3], b[1] + b[3])
    return [x1, y1, x2 - x1, y2 - y1] if x2 > x1 and y2 > y1 else [0, 0, 0, 0]


def source_size(el):
    if el.get("crop"):
        return el["crop"][2], el["crop"][3]
    return Image.open(ROOT / el["asset"]).size


def region_on_canvas(el, region_norm):
    """Map a tag region (normalised 0-1 on the FULL source asset) onto canvas pixels.

    Returns where the whole region would sit if nothing were cropped; the visible part is
    this box ∩ the element's bbox ∩ the canvas.
    """
    full_w, full_h = Image.open(ROOT / el["asset"]).size
    cx, cy, cw, ch = el.get("crop") or [0, 0, full_w, full_h]
    bx, by, bw, bh = el["bbox"]
    sx, sy = bw / cw, bh / ch
    rx, ry, rw, rh = region_norm
    full = [
        bx + (rx * full_w - cx) * sx,
        by + (ry * full_h - cy) * sy,
        rw * full_w * sx,
        rh * full_h * sy,
    ]
    return full


def crop_with_margin(img, bbox, margin=0.15):
    x, y, w, h = bbox
    mx, my = w * margin, h * margin
    box = (
        max(0, int(x - mx)),
        max(0, int(y - my)),
        min(img.width, int(x + w + mx)),
        min(img.height, int(y + h + my)),
    )
    return img.crop(box)
