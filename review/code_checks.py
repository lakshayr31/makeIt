"""Stage 2 — preflight: exact, measured checks. No AI."""

import statistics

from review.design import (
    area,
    intersect,
    region_on_canvas,
    render,
    source_size,
    text_size,
)

NAVY, CYAN, WHITE = "#000856", "#00B8E4", "#FFFFFF"
PALETTE = [
    NAVY,
    CYAN,
    WHITE,
    "#0B1B4D",
    "#F2F2F2",
    "#E6E6E6",
    "#2E7CF6",
    "#2E5BFF",
    "#13B5EA",
    "#0B5CFF",
    "#6EE7B7",
    "#F2C811",
    "#F47C8C",
    "#B39DDB",
    "#59C3E1",
    "#2E75B6",
    "#0A1E3F",
]
# Logo asset colour, by brand-kit file prefix (10_Logo/01 white, 02 navy, 03 cyan).
LOGO_COLOUR = {"01_": WHITE, "02_": NAVY, "03_": CYAN}
ALLOWED_LOGO_PAIRS = {(WHITE, NAVY), (CYAN, NAVY), (NAVY, WHITE), (NAVY, CYAN)}
# Meta 9:16 story/reel safe zones, as fractions of the canvas (17_Meta_Asset_Safe_Zones).
SAFE_SIDE, SAFE_TOP, SAFE_BOTTOM_LEFT, SAFE_BOTTOM_RIGHT = 0.06, 0.14, 0.35, 0.40
MUST_STAY_INSIDE = {"text", "button", "logo", "charm", "card", "product"}
FOREGROUND = {"text", "button", "logo", "card", "charm"}
CLEAR_SPACE_LOGO_HEIGHTS = 0.5  # assumption: brand kit gives no number


def _rgb(hex_):
    hex_ = hex_.lstrip("#")
    return tuple(int(hex_[i : i + 2], 16) for i in (0, 2, 4))


def _lum(rgb):
    def ch(c):
        c /= 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (ch(c) for c in rgb[:3])
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    la, lb = sorted((_lum(a), _lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def _nearest(rgb, hexes, max_dist=40):
    best = min(hexes, key=lambda h: sum((x - y) ** 2 for x, y in zip(_rgb(h), rgb[:3])))
    dist = sum((x - y) ** 2 for x, y in zip(_rgb(best), rgb[:3])) ** 0.5
    return best if dist <= max_dist else None


def _median_behind(design, el):
    """Median colour of whatever sits behind the element."""
    img = render(design, max_z=el["z"]).convert("RGB")
    x, y, w, h = [int(v) for v in el["bbox"]]
    box = (max(0, x), max(0, y), min(img.width, x + w), min(img.height, y + h))
    px = list(img.crop(box).getdata()) or [(255, 255, 255)]
    return tuple(int(statistics.median(p[i] for p in px)) for i in range(3))


def _finding(el, check, severity, message, auto_fix=False):
    return {
        "element_id": el["id"],
        "check": check,
        "severity": severity,
        "message": message,
        "source": "code",
        "auto_fix": auto_fix,
    }


def check_design(design, tags):
    c = design["canvas"]
    canvas = [0, 0, c["w"], c["h"]]
    els = design["elements"]
    out = []

    for el in els:
        x, y, w, h = el["bbox"]
        inside = intersect(el["bbox"], canvas)

        if el["type"] in MUST_STAY_INSIDE and area(inside) < area(el["bbox"]) * 0.99:
            out.append(
                _finding(
                    el,
                    "off_canvas",
                    "high",
                    f"{el['type'].title()} runs off the edge of the canvas.",
                )
            )

        if el.get("asset"):
            sw, sh = source_size(el)
            if abs((w / h) / (sw / sh) - 1) > 0.03:
                out.append(
                    _finding(
                        el,
                        "stretched",
                        "high",
                        "Image is stretched or squashed out of its real proportions.",
                    )
                )
            if w / sw > 1.5:
                out.append(
                    _finding(
                        el,
                        "low_resolution",
                        "medium",
                        f"Image is shown {w / sw:.1f}× larger than its real size and will look blurry.",
                    )
                )

        for region in (tags.get(el.get("asset")) or {}).get("regions", []):
            full = region_on_canvas(el, region["box"])
            seen = intersect(full, intersect(el["bbox"], canvas))
            if (
                region.get("must_not_cut")
                and area(full)
                and area(seen) / area(full) < 0.97
            ):
                cut = 1 - area(seen) / area(full)
                out.append(
                    _finding(
                        el,
                        "cut_off_subject",
                        "high",
                        f"The {region['label']} is cut off ({cut:.0%} of it is hidden).",
                    )
                )
            if region.get("must_not_cover") and area(seen):
                for other in els:
                    if other["z"] > el["z"] and other["type"] in FOREGROUND:
                        cover = area(intersect(other["bbox"], seen)) / area(seen)
                        if cover > 0.03:
                            out.append(
                                _finding(
                                    other,
                                    "covers_content",
                                    "high",
                                    f"{other['type'].title()} covers {cover:.0%} of the {region['label']} in {el['id']}.",
                                )
                            )

        if el["type"] in ("text", "button"):
            tw, th = text_size(el)
            pad = 0.85 if el["type"] == "button" else 1.02
            if tw > w * pad or th > h * 1.05:
                out.append(
                    _finding(
                        el, "text_overflow", "high", "Text does not fit inside its box."
                    )
                )
            if el["type"] == "text":
                ratio = contrast(_rgb(el["font"]["color"]), _median_behind(design, el))
                if ratio < 4.5:
                    out.append(
                        _finding(
                            el,
                            "low_contrast",
                            "high",
                            f"Text contrast is {ratio:.1f}:1 (needs at least 4.5:1).",
                        )
                    )

        for colour in (el.get("fill"), (el.get("font") or {}).get("color")):
            if colour and not _nearest(_rgb(colour), PALETTE, max_dist=12):
                out.append(
                    _finding(
                        el,
                        "off_palette",
                        "medium",
                        f"Colour {colour} is not a brand colour.",
                        auto_fix=True,
                    )
                )

        if el["type"] == "logo":
            prefix = el["asset"].split("/")[-1][:3]
            behind = _nearest(_median_behind(design, el), [NAVY, CYAN, WHITE])
            logo = LOGO_COLOUR.get(prefix)
            if logo and behind and (logo, behind) not in ALLOWED_LOGO_PAIRS:
                out.append(
                    _finding(
                        el,
                        "logo_colour_pair",
                        "high",
                        f"Logo colour {logo} on {behind} is not an approved pairing.",
                        auto_fix=True,
                    )
                )
            gap = min(x, y, c["w"] - x - w, c["h"] - y - h)
            if 0 <= gap < h * CLEAR_SPACE_LOGO_HEIGHTS:
                out.append(
                    _finding(
                        el,
                        "logo_clear_space",
                        "medium",
                        "Logo is too close to the edge of the canvas.",
                    )
                )

        if c.get("format") == "story" and el["type"] in MUST_STAY_INSIDE:
            zones = [
                [0, 0, c["w"], c["h"] * SAFE_TOP],
                [0, 0, c["w"] * SAFE_SIDE, c["h"]],
                [c["w"] * (1 - SAFE_SIDE), 0, c["w"] * SAFE_SIDE, c["h"]],
                [
                    0,
                    c["h"] * (1 - SAFE_BOTTOM_LEFT),
                    c["w"] / 2,
                    c["h"] * SAFE_BOTTOM_LEFT,
                ],
                [
                    c["w"] / 2,
                    c["h"] * (1 - SAFE_BOTTOM_RIGHT),
                    c["w"] / 2,
                    c["h"] * SAFE_BOTTOM_RIGHT,
                ],
            ]
            if any(
                area(intersect(el["bbox"], z)) > area(el["bbox"]) * 0.02 for z in zones
            ):
                out.append(
                    _finding(
                        el,
                        "safe_zone",
                        "high",
                        "Sits inside a Meta safe zone, where app buttons will cover it.",
                    )
                )

    fg = [e for e in els if e["type"] in FOREGROUND]
    for i, a in enumerate(fg):
        for b in fg[i + 1 :]:
            ov = area(intersect(a["bbox"], b["bbox"]))
            if ov > 0.02 * min(area(a["bbox"]), area(b["bbox"])):
                top = a if a["z"] > b["z"] else b
                under = b if top is a else a
                out.append(
                    _finding(
                        top,
                        "covers_content",
                        "high",
                        f"{top['type'].title()} overlaps {under['type']} {under['id']}.",
                    )
                )
    return out
