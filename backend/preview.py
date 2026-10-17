"""Render solved layouts (layout_<i>.json) to PNG, for eyeballing before the canvas UI.

Run: backend/.venv/bin/python backend/preview.py backend/runs/<ad-name>
"""

import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from build import open_image
from layout import FONT_BOLD, FONT_MEDIUM, LINE_HEIGHT, H, W


def _draw_image(canvas: Image.Image, layer: dict) -> None:
    props = layer["props"]
    img = open_image(props["src"]).resize(
        (max(1, round(layer["w"])), max(1, round(layer["h"])))
    )
    x, y = round(layer["x"]), round(layer["y"])
    if props.get("pill"):  # logo on busy surface: white capsule behind it
        pad = layer["h"] * 0.35
        ImageDraw.Draw(canvas).rounded_rectangle(
            (x - pad, y - pad, x + layer["w"] + pad, y + layer["h"] + pad),
            radius=layer["h"],
            fill="#FFFFFF",
        )
    if clip := props.get("clip"):  # cover-fit: only show the part inside the box
        cx, cy, cw, ch = (round(v) for v in clip)
        region = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        region.paste(img, (x, y), img)
        canvas.alpha_composite(
            region.crop((cx, cy, cx + cw, cy + ch)), (max(cx, 0), max(cy, 0))
        )
    else:
        canvas.paste(img, (x, y), img)


def _draw_text(draw: ImageDraw.ImageDraw, layer: dict) -> None:
    props = layer["props"]
    x, y, w, h = layer["x"], layer["y"], layer["w"], layer["h"]
    font = ImageFont.truetype(
        FONT_BOLD if props["weight"] == "bold" else FONT_MEDIUM, props["font_size"]
    )
    if props.get("pill"):
        draw.rounded_rectangle((x, y, x + w, y + h), radius=h / 2, fill=props["fill"])
        draw.text(
            (x + w / 2, y + h / 2),
            props["text"],
            font=font,
            fill=props["colour"],
            anchor="mm",
        )
        return
    for i, line in enumerate(props["lines"]):
        draw.text(
            (x, y + i * props["font_size"] * LINE_HEIGHT),
            line,
            font=font,
            fill=props["colour"],
        )


def render(layout: dict) -> Image.Image:
    canvas = Image.new("RGBA", (W, H), layout.get("background_colour") or "#FFFFFF")
    for layer in layout["layers"]:
        draw = ImageDraw.Draw(canvas)
        if layer["type"] == "image":
            _draw_image(canvas, layer)
        elif layer["type"] == "text":
            _draw_text(draw, layer)
        elif layer["type"] == "rect":
            p = layer["props"]
            draw.rounded_rectangle(
                (
                    layer["x"],
                    layer["y"],
                    layer["x"] + layer["w"],
                    layer["y"] + layer["h"],
                ),
                radius=p.get("radius", 0),
                fill=p["fill"],
            )
    return canvas


def main(run: Path) -> None:
    tiles = []
    for path in sorted(run.glob("layout_*.json")):
        layout = json.loads(path.read_text())
        img = render(layout)
        img.convert("RGB").save(run / f"{path.stem}_{layout.get('axis')}.png")
        tiles.append(img.resize((W // 3, H // 3)))
    strip = Image.new("RGB", (len(tiles) * (W // 3 + 20) - 20, H // 3), "#EEEEEE")
    for i, t in enumerate(tiles):
        strip.paste(t, (i * (W // 3 + 20), 0), t)
    strip.save(run / "variants.png")
    print(f"wrote {run / 'variants.png'}")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
