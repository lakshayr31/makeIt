"""Make the brand-kit background templates see-through where they are white.

The templates ship as solid PNGs: a blue bloom shape on pure white. The white is the
empty window (where a photo or the canvas colour should show), so we turn it into
transparency. Edges stay smooth: each pixel's alpha is how far it is from white,
relative to the template's solid colour.

Originals are kept in assets/brand-kit/_originals/ (assets/ is not in git), and the
script always works from them, so it is safe to run again.
Run: backend/.venv/bin/python backend/transparent_templates.py
"""

import json
import shutil

import numpy as np
from PIL import Image

from config import ASSETS_DIR

TEMPLATES = ASSETS_DIR / "brand-kit/24_Background_Templates/24_Background_Templates"
ORIGINALS = ASSETS_DIR / "brand-kit/_originals/24_Background_Templates"
CATALOG = ASSETS_DIR / "brand-kit/catalog.json"
SOLID_BELOW = (
    200  # a pixel whose darkest channel is under this is the shape, not an edge
)


def white_to_alpha(rgb: np.ndarray) -> np.ndarray:
    """RGB (h, w, 3) → RGBA: white becomes transparent, the shape colour stays opaque."""
    rgb = rgb.astype(np.float32)
    solid = rgb.min(axis=-1) < SOLID_BELOW
    fg = np.median(rgb[solid], axis=0)  # the template's one shape colour
    alpha = np.linalg.norm(255 - rgb, axis=-1) / np.linalg.norm(255 - fg)
    out = np.empty(rgb.shape[:2] + (4,), np.uint8)
    out[..., :3] = fg.round().astype(np.uint8)
    out[..., 3] = (np.clip(alpha, 0, 1) * 255).round().astype(np.uint8)
    return out


def main() -> None:
    ORIGINALS.mkdir(parents=True, exist_ok=True)
    for path in sorted(TEMPLATES.glob("*.png")):
        original = ORIGINALS / path.name
        if not original.exists():
            shutil.copy(path, original)
        rgba = white_to_alpha(np.array(Image.open(original).convert("RGB")))
        Image.fromarray(rgba, "RGBA").save(path)
        print(f"{path.name[:12]}: {100 * (rgba[..., 3] == 0).mean():.0f}% transparent")

    catalog = json.loads(CATALOG.read_text())
    for entry in catalog:
        if entry.get("kind") == "background_template":
            entry["has_transparency"] = True
    CATALOG.write_text(json.dumps(catalog, indent=1))


if __name__ == "__main__":
    main()
