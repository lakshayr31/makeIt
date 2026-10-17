"""Split the charm and bloom sprite sheets into one transparent PNG per shape × colour.

Sheets are transparent with each shape's colourways stacked in a column inside a
thin dashed box. We drop the thin lines, find each blob, group blobs into columns,
and name each by its dominant colour.

Output: assets/brand-kit/parts/{charms,blooms}/<NN>/<colour>.png
Run: backend/.venv/bin/python backend/split_sheets.py
"""

import shutil

import numpy as np
from PIL import Image
from scipy import ndimage

from config import ASSETS_DIR

KIT = ASSETS_DIR / "brand-kit"
OUT = KIT / "parts"
SHEETS = {
    "charms": KIT / "22_Charms/22_Charms/08_0dad3276-a933-47e9-9154-8958bc31193d.png",
    "blooms": KIT
    / "06_Shapes_Cropping_Blooms/06_Shapes_Cropping_Blooms/08_6014a7f4-cff7-44fb-bd3d-ccd99dcf3821_Blooms.png",
}
# Brand colourways (sampled from the sheets); nearest one names each variant.
PALETTE = {
    "lightblue": (104, 199, 250),
    "blue": (52, 103, 212),
    "navy": (2, 8, 80),
    "green": (142, 230, 174),
    "yellow": (245, 205, 75),
    "pink": (240, 122, 150),
    "purple": (196, 140, 245),
}
COLOUR_ORDER = {
    "charms": ["blue", "green", "yellow", "pink", "purple"],
    "blooms": ["lightblue", "blue", "navy", "green", "yellow", "pink", "purple"],
}
LINE_WIDTH = 5  # dashed boxes are thinner than this; shapes are far thicker
MERGE_GAP = 6  # px; joins tiny anti-alias gaps inside one icon
DASH_JOIN = 12  # px; closes the gaps between dashes of a column box
MIN_AREA = 400


def _masks(alpha: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """(shape pixels, dashed-outline pixels)."""
    solid = alpha > 16
    opened = ndimage.binary_opening(solid, structure=np.ones((LINE_WIDTH, LINE_WIDTH)))
    # Grow back the anti-aliased edges the opening shaved off, but only onto real pixels.
    shapes = ndimage.binary_dilation(opened, iterations=3) & solid
    return shapes, solid & ~shapes


def _column_regions(lines: np.ndarray) -> list[tuple[slice, slice]]:
    """Each dashed box → its bounding slice. Dashes are joined, then the box is filled."""
    lines = lines.copy()
    lines[:4, :] = lines[-4:, :] = lines[:, :4] = lines[:, -4:] = False  # sheet frame
    closed = ndimage.binary_dilation(lines, iterations=DASH_JOIN)
    filled = ndimage.binary_fill_holes(closed)
    labels, _ = ndimage.label(filled)
    regions = [sl for sl in ndimage.find_objects(labels) if sl is not None]
    big = [r for r in regions if (r[0].stop - r[0].start) > 150]
    return sorted(big, key=lambda r: (round(r[0].start / 150), r[1].start))


def _blobs(mask: np.ndarray) -> list[tuple[slice, slice]]:
    labels, _ = ndimage.label(ndimage.binary_dilation(mask, iterations=MERGE_GAP))
    return [
        sl for i, sl in enumerate(ndimage.find_objects(labels), start=1)
        if sl is not None and (mask[sl] & (labels[sl] == i)).sum() >= MIN_AREA
    ]


def _union(a: tuple[slice, slice], b: tuple[slice, slice]) -> tuple[slice, slice]:
    return (slice(min(a[0].start, b[0].start), max(a[0].stop, b[0].stop)),
            slice(min(a[1].start, b[1].start), max(a[1].stop, b[1].stop)))


def _inside(box, region) -> bool:
    cy, cx = (box[0].start + box[0].stop) / 2, (box[1].start + box[1].stop) / 2
    return region[0].start <= cy < region[0].stop and region[1].start <= cx < region[1].stop


def _colour_name(rgba: np.ndarray, kind: str) -> str:
    px = rgba[rgba[..., 3] > 200][:, :3].astype(int)
    # Ignore white highlights and dark shadow outliers when judging the base colour.
    px = px[(px.sum(1) < 700)]
    if len(px) == 0:
        return "white"
    rgb = np.median(px, axis=0)
    name = min(PALETTE, key=lambda k: sum((rgb - PALETTE[k]) ** 2))
    # Charms have a single blue colourway.
    return "blue" if kind == "charms" and name in ("lightblue", "navy") else name


def _group(col: list, expected: int) -> list:
    """Merge detached bits (sparkles, steam) into icons: the expected-1 widest
    vertical gaps separate icons; every narrower gap is inside one icon."""
    if len(col) <= expected:
        return col
    gaps = [b[0].start - a[0].stop for a, b in zip(col, col[1:])]
    cut_after = set(sorted(range(len(gaps)), key=lambda i: gaps[i])[-(expected - 1):])
    groups = [col[0]]
    for i, box in enumerate(col[1:]):
        groups[-1:] = [groups[-1], box] if i in cut_after else [_union(groups[-1], box)]
    return groups


def _split_rows(shapes: np.ndarray, region, expected: int) -> list:
    """Fallback for icons whose anti-aliasing touches: cut at the widest empty-row runs."""
    occupied = shapes[region].any(axis=1)
    runs, start = [], None
    for y, filled in enumerate(occupied):
        if not filled and start is None:
            start = y
        elif filled and start is not None:
            if start > 0:  # the band above the first icon is not a cut
                runs.append((y - start, start, y))
            start = None
    cuts = sorted(r[1] for r in sorted(runs)[-(expected - 1):]) if len(runs) >= expected - 1 else []
    if not cuts:
        return []
    bounds = [0, *cuts, len(occupied)]
    boxes = []
    for top, bottom in zip(bounds, bounds[1:]):
        sub = shapes[region][top:bottom]
        ys, xs = np.nonzero(sub)
        if len(ys):
            y0 = region[0].start + top
            boxes.append((slice(y0 + ys.min(), y0 + ys.max() + 1),
                          slice(region[1].start + xs.min(), region[1].start + xs.max() + 1)))
    return boxes if len(boxes) == expected else []


def split(kind: str, sheet_path) -> int:
    img = np.array(Image.open(sheet_path).convert("RGBA"))
    shapes, lines = _masks(img[..., 3])
    clean = img.copy()
    clean[..., 3] = np.where(shapes, img[..., 3], 0)
    blobs = _blobs(shapes)
    count = 0
    for n, region in enumerate(_column_regions(lines), start=1):
        col = sorted((b for b in blobs if _inside(b, region)), key=lambda b: b[0].start)
        boxes = _group(col, len(COLOUR_ORDER[kind]))
        if len(boxes) < len(COLOUR_ORDER[kind]):
            want = len(COLOUR_ORDER[kind])
            # Some columns carry an extra shade (e.g. light + dark blue).
            boxes = (_split_rows(shapes, region, want + 1)
                     or _split_rows(shapes, region, want) or boxes)
        order = COLOUR_ORDER[kind]
        # Brand sheets stack colourways in a fixed order; fall back to sampling if counts differ.
        if len(boxes) == len(order):
            variants = list(zip(order, boxes))
        else:
            variants = [(_colour_name(clean[b], kind), b) for b in boxes]
        folder = OUT / kind / f"{n:02d}"
        folder.mkdir(parents=True, exist_ok=True)
        seen: dict[str, int] = {}
        for name, box in variants:
            seen[name] = seen.get(name, 0) + 1
            suffix = "" if seen[name] == 1 else f"_{seen[name]}"
            Image.fromarray(clean[box]).save(folder / f"{name}{suffix}.png")
            count += 1
    return count


if __name__ == "__main__":
    shutil.rmtree(OUT, ignore_errors=True)
    for kind, path in SHEETS.items():
        print(f"{kind}: {split(kind, path)} parts")
