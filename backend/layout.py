"""Layout solver: matcher variant (rough 0-1 boxes) → exact, non-overlapping layers.

The LLM decides what goes where roughly; this code decides exact pixels:
  1. text is measured with a real font and sized to fit (headline shrinks before it overflows)
  2. text/CTA/logo are stacked in rows top to bottom with a fixed gap, so nothing collides
  3. the text block is pulled up if it would cross the bottom safe zone
  4. a text card is resized to wrap the text it carries
  5. images are fitted to their box by their real aspect ratio

Output layers map 1:1 onto canvas objects (Fabric later): image | text | rect.
"""

from dataclasses import dataclass, field

from PIL import ImageFont

W, H = 1080, 1350
MARGIN = 72
GAP = 32
SAFE_BOTTOM = int(H * 0.94)  # Meta bottom safe row
FONT_BOLD = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
FONT_MEDIUM = "/System/Library/Fonts/Supplemental/Arial.ttf"
HEADLINE_SIZES = range(104, 47, -4)
LINE_HEIGHT = 1.08
CTA_HEIGHT, CTA_FONT, CTA_PAD = 92, 36, 48
LOGO_HEIGHT = 60
CARD_PAD = 48
TEXT_ROLES = {"headline", "support", "proof", "cta"}


@dataclass
class Layer:
    id: str
    role: str
    type: str  # image | text | rect
    x: float
    y: float
    w: float
    h: float
    z: float
    props: dict = field(default_factory=dict)


def _wrap(text: str, font: ImageFont.FreeTypeFont, width: float) -> list[str]:
    lines, line = [], ""
    for word in text.split():
        trial = f"{line} {word}".strip()
        if font.getlength(trial) <= width or not line:
            line = trial
        else:
            lines.append(line)
            line = word
    return lines + [line] if line else lines


def _fit_headline(text: str, width: float, max_lines: int) -> tuple[int, list[str]]:
    """Largest size whose wrap stays within max_lines."""
    for size in HEADLINE_SIZES:
        lines = _wrap(text, ImageFont.truetype(FONT_BOLD, size), width)
        if len(lines) <= max_lines:
            return size, lines
    size = HEADLINE_SIZES[-1]
    return size, _wrap(text, ImageFont.truetype(FONT_BOLD, size), width)


def _text_layer(slot: dict, x: float, y: float, w: float, shrink: int) -> Layer:
    role = slot["role"]
    if role == "cta":
        font = ImageFont.truetype(FONT_BOLD, CTA_FONT)
        pill_w = font.getlength(slot["text"]) + 2 * CTA_PAD
        return Layer(slot["id"], role, "text", x, y, pill_w, CTA_HEIGHT, slot.get("z", 5), {
            "text": slot["text"], "font_size": CTA_FONT, "weight": "bold",
            "colour": slot.get("colour") or "#FFFFFF", "fill": slot.get("fill") or "#000856",
            "pill": True, "lines": [slot["text"]],
        })
    if role == "headline":
        size, lines = _fit_headline(slot["text"], w, max(slot.get("lines", 2), 3) - shrink)
        weight, font_path = "bold", FONT_BOLD
    else:
        size, weight, font_path = 38, "medium", FONT_MEDIUM
        lines = _wrap(slot["text"], ImageFont.truetype(font_path, size), w)
    return Layer(slot["id"], role, "text", x, y, w, len(lines) * size * LINE_HEIGHT, slot.get("z", 4), {
        "text": slot["text"], "font_size": size, "weight": weight,
        "colour": slot.get("colour") or "#000856", "lines": lines,
    })


def _px(box: list[float]) -> tuple[float, float, float, float]:
    x, y, w, h = box
    return x * W, y * H, w * W, h * H


def _rows(slots: list[dict]) -> list[list[dict]]:
    """Group text/CTA/logo into rows: slots that share vertical space but not horizontal."""
    rows: list[list[dict]] = []
    for slot in sorted(slots, key=lambda s: (s["box"][1], s["box"][0])):
        _, y, _, h = slot["box"]
        for row in rows:
            ry, rh = row[0]["box"][1], row[0]["box"][3]
            same_band = y < ry + rh and ry < y + h
            side_by_side = all(slot["box"][0] >= r["box"][0] + r["box"][2] or
                               r["box"][0] >= slot["box"][0] + slot["box"][2] for r in row)
            if same_band and side_by_side:
                row.append(slot)
                break
        else:
            rows.append([slot])
    return rows


def _logo_layer(slot: dict, x: float, y: float, aspect: float) -> Layer:
    return Layer(slot["id"], "logo", "image", x, y, LOGO_HEIGHT * aspect, LOGO_HEIGHT,
                 slot.get("z", 6), {"src": slot["src"], "pill": slot.get("pill", False)})


def _stack(flow: list[dict], aspects: dict[str, float], shrink: int) -> list[Layer]:
    layers: list[Layer] = []
    cursor = None
    for row in _rows(flow):
        row_layers = []
        for slot in row:
            x, y, w, _ = _px(slot["box"])
            x, w = max(x, MARGIN), min(w, W - 2 * MARGIN)
            top = y if cursor is None else max(y, cursor + GAP)
            if slot["role"] == "logo":
                row_layers.append(_logo_layer(slot, x, top, aspects.get(slot["id"], 3.5)))
            else:
                row_layers.append(_text_layer(slot, x, top, w, shrink))
        row_top = min(l.y for l in row_layers)
        row_h = max(l.h for l in row_layers)
        for l in row_layers:  # align the row on its top, centre shorter items vertically
            l.y = row_top + (row_h - l.h) / 2
        cursor = row_top + row_h
        layers += row_layers
    return layers


def _fit_image(slot: dict, aspect: float) -> Layer:
    x, y, w, h = _px(slot["box"])
    fit = slot.get("fit", "contain")
    scale_w = w if (w / h < aspect) == (fit == "contain") else h * aspect
    iw, ih = scale_w, scale_w / aspect
    return Layer(slot["id"], slot["role"], "image", x + (w - iw) / 2, y + (h - ih) / 2, iw, ih,
                 slot.get("z", 2), {"src": slot["src"], "clip": [x, y, w, h] if fit == "cover" else None})


def solve(variant: dict, aspects: dict[str, float]) -> list[Layer]:
    """aspects: slot id → width/height of its resolved image. Slots carry `src` for images."""
    slots = [s for s in variant["slots"] if s.get("match") != "dropped" and "box" in s]
    flow = [s for s in slots if s["role"] in TEXT_ROLES and s.get("text") or s["role"] == "logo"]
    flow_ids = {s["id"] for s in flow}

    # The text block may rise into the panel area, but no higher than the card/panel top.
    card = next((s for s in slots if s.get("kind") == "card"), None)
    ceiling = min([_px(s["box"])[1] for s in flow] + ([_px(card["box"])[1] + CARD_PAD] if card else []))
    for shrink in range(0, 3):  # lift first; shrink the headline only if lifting can't fit it
        stacked = _stack(flow, aspects, shrink)
        overflow = max(l.y + l.h for l in stacked) - SAFE_BOTTOM
        room = min(l.y for l in stacked) - ceiling
        if overflow <= room:
            break
    lift = max(0.0, overflow)
    for l in stacked:
        l.y -= lift

    layers = list(stacked)
    for slot in slots:
        if slot["id"] in flow_ids:
            continue
        if slot.get("kind") == "card":
            continue  # rebuilt below from the text it carries
        if slot.get("src"):
            layers.append(_fit_image(slot, aspects.get(slot["id"], 1.0)))
    layers.append(_card(stacked, card))
    return sorted(layers, key=lambda l: l.z)


def _card(stacked: list[Layer], card: dict | None) -> Layer:
    """Card wrapping the text block. Always present: it guarantees text contrast whatever
    sits behind it. Fill follows the text colour (navy text → white card, white → navy)."""
    headline = next((l for l in stacked if l.role == "headline"), None)
    light_text = headline is not None and headline.props["colour"].upper() == "#FFFFFF"
    fill = "#000856" if light_text else "#FFFFFF"
    x0 = min(l.x for l in stacked) - CARD_PAD
    y0 = min(l.y for l in stacked) - CARD_PAD
    x1 = max(l.x + l.w for l in stacked) + CARD_PAD
    if card:
        x1 = max(x1, _px(card["box"])[0] + _px(card["box"])[2])
    y1 = max(l.y + l.h for l in stacked) + CARD_PAD
    return Layer(card["id"] if card else "card", "card", "rect", x0, y0, x1 - x0, y1 - y0, 1.5,
                 {"fill": fill, "radius": 40})
