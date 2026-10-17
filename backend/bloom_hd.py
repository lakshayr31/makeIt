"""Rebuild catalog bloom parts as crisp HD PNGs from the 06 brand-kit source sheet."""

import json
import re
from collections import defaultdict
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
KIT = ROOT / "assets" / "brand-kit"
SRC_DIR = KIT / "06_Shapes_Cropping_Blooms" / "06_Shapes_Cropping_Blooms"
CATALOG = KIT / "catalog.json"
HD_DIR = KIT / "parts" / "blooms_hd"
HD_LONG_SIDE = 2048
CMP_SIZE = 64
MIN_IOU = 0.8


def alpha_of(path):
    return np.array(Image.open(path).convert("RGBA"))[:, :, 3]


def tight_crop(alpha, thresh=16):
    ys, xs = np.where(alpha > thresh)
    return alpha[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1]


def silhouette(alpha):
    img = Image.fromarray(tight_crop(alpha)).resize(
        (CMP_SIZE, CMP_SIZE), Image.BILINEAR
    )
    return np.array(img) > 127


# Transforms applied to the big source so it matches the part's orientation.
TRANSFORMS = {
    "none": lambda a: a,
    "flip_h": lambda a: a[:, ::-1],
    "flip_v": lambda a: a[::-1, :],
    "rot90": lambda a: np.rot90(a, 1),
    "rot180": lambda a: np.rot90(a, 2),
    "rot270": lambda a: np.rot90(a, 3),
    "transpose": lambda a: a.T,
    "anti_transpose": lambda a: np.rot90(a, 2).T,
}


def iou(a, b):
    return (a & b).sum() / max((a | b).sum(), 1)


def source_shapes():
    groups = defaultdict(list)
    for p in sorted(SRC_DIR.glob("*.png")):
        m = re.match(r"(\d+)_", p.name)
        if not m or not 9 <= int(m.group(1)) <= 41:
            continue
        with Image.open(p) as im:
            groups[im.size].append(p)
    return {size: paths[0] for size, paths in groups.items()}


def best_assignment(scores):
    """Greedy highest-IoU-first distinct assignment of parts -> shapes."""
    pairs = sorted(
        ((s, part, shape) for (part, shape), (s, _) in scores.items()), reverse=True
    )
    used_parts, used_shapes, out = set(), set(), {}
    for s, part, shape in pairs:
        if part in used_parts or shape in used_shapes:
            continue
        out[part] = shape
        used_parts.add(part)
        used_shapes.add(shape)
    return out


def hd_alpha(alpha):
    a = tight_crop(alpha, thresh=0)
    h, w = a.shape
    scale = HD_LONG_SIDE / max(h, w)
    size = (max(1, round(w * scale)), max(1, round(h * scale)))
    big = np.array(Image.fromarray(a).resize(size, Image.LANCZOS)).astype(np.float32)
    return np.clip((big - 128) * 3 + 128, 0, 255).astype(np.uint8)


def flat_colour(path):
    px = np.array(Image.open(path).convert("RGBA")).reshape(-1, 4)
    opaque = px[px[:, 3] > 200][:, :3]
    if len(opaque) == 0:
        opaque = px[px[:, 3] > 0][:, :3]
    return tuple(int(v) for v in np.median(opaque, axis=0))


def main():
    catalog = json.loads(CATALOG.read_text())
    blooms = [e for e in catalog if e.get("kind") == "bloom"]
    shapes = source_shapes()
    print(f"{len(shapes)} distinct source shapes, {len(blooms)} catalog blooms")
    if len(shapes) != len(blooms):
        print("WARNING: shape count != bloom count")

    src_alpha = {size: alpha_of(p) for size, p in shapes.items()}
    part_sil = {}
    for e in blooms:
        first = next(iter(e["variants"].values()))
        part_sil[e["id"]] = silhouette(alpha_of(ROOT / first.lstrip("/")))

    scores = {}
    for pid, psil in part_sil.items():
        for size, a in src_alpha.items():
            best = max(
                (
                    (iou(psil, silhouette(fn(a))), name)
                    for name, fn in TRANSFORMS.items()
                )
            )
            scores[(pid, size)] = best

    mapping = best_assignment(scores)
    print(f"{'part':10} {'source':28} {'size':10} {'xform':15} IoU")
    for e in blooms:
        pid = e["id"]
        if pid not in mapping:
            print(f"WARNING: {pid} unmatched")
            continue
        size = mapping[pid]
        s, xf = scores[(pid, size)]
        flag = "" if s >= MIN_IOU else "  <-- WARNING low IoU"
        print(
            f"{pid:10} {shapes[size].name[:28]:28} {size[0]}x{size[1]:<6} {xf:15} {s:.3f}{flag}"
        )

    written = 0
    for e in blooms:
        pid = e["id"]
        if pid not in mapping:
            continue
        size = mapping[pid]
        _, xf = scores[(pid, size)]
        alpha = hd_alpha(np.ascontiguousarray(TRANSFORMS[xf](src_alpha[size])))
        h, w = alpha.shape
        nn = pid.split("-")[1]
        out_dir = HD_DIR / nn
        out_dir.mkdir(parents=True, exist_ok=True)
        variants = {}
        for colour, url in e["variants"].items():
            rgb = flat_colour(ROOT / url.lstrip("/"))
            rgba = np.zeros((h, w, 4), np.uint8)
            rgba[:, :, :3] = rgb
            rgba[:, :, 3] = alpha
            Image.fromarray(rgba, "RGBA").save(out_dir / f"{colour}.png", optimize=True)
            variants[colour] = f"/assets/brand-kit/parts/blooms_hd/{nn}/{colour}.png"
            written += 1
        e["variants"] = variants
        e["url"] = variants.get("blue", next(iter(variants.values())))
        e["width"], e["height"], e["aspect"] = w, h, round(w / h, 2)

    CATALOG.write_text(json.dumps(catalog, indent=1, ensure_ascii=False))
    print(f"wrote {written} HD PNGs; catalog updated")


if __name__ == "__main__":
    main()
