"""Designer flow: competitor ad → finished Xero ads, the way a designer would work.

1. plan     two Flash art directors look at the ad and the WHOLE brand kit (one numbered
            grid per category): backgrounds/blooms/logos, and highlights (pictures,
            product screens, charms, copy). Each only decides what it can see.
            Anything the ad promises that Xero can't (a gift, a price) becomes a question
            for the marketer instead of a guess.
2. make     GPT Image draws the missing pictures (if any), then composes each version in
            one call from the real pieces, the closest real Xero ads and the copy.

Every drawing call goes through GPT Image; Flash only picks and writes.
"""

import asyncio
import base64
import io
import json
import re
from pathlib import Path

from PIL import Image, ImageDraw

from agent import complete_json
from build import open_image
from config import ASSETS_DIR, GENERATED_DIR, IMAGE_MODEL, ROOT, image_client

KIT = ASSETS_DIR / "brand-kit"
CATALOG = KIT / "catalog"
ORIGINAL_BACKGROUNDS = KIT / "_originals/24_Background_Templates"
LOGO_GUIDES = sorted((KIT / "05_Logo_Guidelines").rglob("0[12]_*.png"))
XERO_ADS = sorted((ASSETS_DIR / "references").glob("*.png"))
GUIDE = ROOT / "prompts/brand-guide"
GRIDS_DIR = GENERATED_DIR / "grids"
GRIDS_DIR.mkdir(exist_ok=True)
MAX_QUESTIONS = 2

TRUE_CLAIMS = """Xero is online accounting software for small businesses. Only use claims like these, which Xero
really makes: try Xero free for 30 days; invoicing and getting paid faster; all your numbers in one place;
less time on admin and bookkeeping; bank feeds and reconciliation; payroll; see your cash flow.
NEVER copy the competitor's offer, prize, gift, price, percentage or number. Never invent numbers or promises."""


# ---- brand guide, trimmed per step ---------------------------------------------

def _rules(prefixes: tuple[str, ...]) -> str:
    """Only the core rules a step decides on (e.g. BL*, TP*), not the whole guide."""
    lines = (GUIDE / "core.md").read_text().splitlines()
    return "\n".join(l for l in lines if re.match(r"^[A-Z]{2}\d", l) and l.startswith(prefixes))


BACKGROUND_RULES = ("BL", "TP", "LG", "CO", "LY")
HIGHLIGHT_RULES = ("PH", "IL", "PU", "CH", "CP", "TY")
COMPOSE_RULES = ("BL1", "BL2", "BL3", "PU1", "CH1", "LG1", "LG2", "LG3", "TY1", "TY4", "CO2")


# ---- images and grids ------------------------------------------------------------

def load(name: str) -> list[dict]:
    return json.loads((CATALOG / name).read_text())


def kit_path(url: str) -> Path:
    return ROOT / url.lstrip("/")


def flat(path: Path, bg: str = "white") -> Image.Image:
    im = Image.open(path).convert("RGBA")
    base = Image.new("RGBA", im.size, bg)
    base.alpha_composite(im)
    return base.convert("RGB")


def thumb(url: str) -> Image.Image:
    """Catalog URL → RGB image on white (SVG illustrations rendered)."""
    if url.endswith(".svg"):
        im = open_image(url)
        base = Image.new("RGBA", im.size, "white")
        base.alpha_composite(im)
        return base.convert("RGB")
    return flat(kit_path(url))


def background_image(entry: dict) -> Image.Image:
    return flat(next(ORIGINAL_BACKGROUNDS.glob(Path(entry["url"]).name)))


def numbered_grid(images: list[Image.Image], cols: int = 6, cell: int = 260) -> Image.Image:
    rows = (len(images) + cols - 1) // cols
    grid = Image.new("RGB", (cols * cell, rows * cell), "#cccccc")
    draw = ImageDraw.Draw(grid)
    for i, im in enumerate(images):
        im = im.copy()
        im.thumbnail((cell - 30, cell - 30))
        x, y = (i % cols) * cell, (i // cols) * cell
        grid.paste(im, (x + 15, y + 25))
        draw.rectangle([x + 4, y + 2, x + 40, y + 22], fill="black")
        draw.text((x + 10, y + 5), str(i + 1), fill="white")
    return grid


def grids() -> dict[str, Image.Image]:
    """One numbered grid per kit category, cached on disk until the catalog changes."""
    stamp = max(p.stat().st_mtime for p in CATALOG.glob("*.json"))
    sources = {
        "backgrounds": lambda: [background_image(e) for e in load("backgrounds.json")],
        "blooms": lambda: [thumb(e["url"]) for e in load("blooms.json")],
        "logos": lambda: [flat(kit_path(e["url"]), "#888888") for e in load("logos.json")],
        "xero_ads": lambda: [flat(p) for p in XERO_ADS],
        "illustrations": lambda: [thumb(e["url"]) for e in load("illustrations.json")],
        "product_ui": lambda: [thumb(e["url"]) for e in load("product_ui.json")],
        "charms": lambda: [thumb(e["url"]) for e in load("charms.json")],
    }
    out = {}
    for name, make in sources.items():
        path = GRIDS_DIR / f"{name}.png"
        if not path.exists() or path.stat().st_mtime < stamp:
            small = name == "charms"
            numbered_grid(make(), cols=10 if small else 6, cell=160 if small else 260).save(path)
        out[name] = Image.open(path).convert("RGB")
    return out


def names(file: str) -> str:
    return "\n".join(f"{i + 1}. {e.get('name', e['id'])}" for i, e in enumerate(load(file)))


def pick(file: str, number) -> dict | None:
    items = load(file)
    n = int(number) if str(number).isdigit() else 0
    return items[n - 1] if 1 <= n <= len(items) else None


# ---- model calls -------------------------------------------------------------------

def _data_url(im: Image.Image, max_side: int = 1024) -> str:
    im = im.copy()
    im.thumbnail((max_side, max_side))
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


async def flash(system: str, parts: list) -> dict:
    """One Flash (vision) call → JSON. parts: str | (label, PIL.Image)."""
    content = []
    for p in parts:
        if isinstance(p, str):
            content.append({"type": "text", "text": p})
        else:
            content.append({"type": "text", "text": f"Image: {p[0]}"})
            content.append({"type": "image_url", "image_url": {"url": _data_url(p[1])}})
    return await complete_json("flash", [{"role": "system", "content": system},
                                         {"role": "user", "content": content}], timeout=90)


async def gpt_edit(images: list[tuple[str, Image.Image]], prompt: str, size: str) -> Image.Image:
    files = []
    for name, im in images:
        buf = io.BytesIO()
        im.save(buf, "PNG")
        files.append((f"{name}.png", buf.getvalue(), "image/png"))
    r = await image_client.images.edit(model=IMAGE_MODEL, image=files, prompt=prompt, size=size, quality="medium")
    return Image.open(io.BytesIO(base64.b64decode(r.data[0].b64_json)))


# ---- step 1: plan ------------------------------------------------------------------

def _notes(notes: list[str]) -> str:
    return ("The Xero marketer has told us (true; overrides the claims list):\n"
            + "\n".join(f"- {n}" for n in notes) + "\n") if notes else ""


async def background_director(ref: Image.Image, g: dict, n: int) -> dict:
    return await flash(
        "You are Xero's art director for backgrounds. Xero brand rules you must follow:\n" + _rules(BACKGROUND_RULES)
        + "\n\nReply with JSON only.",
        [f"We are rebuilding the competitor ad as {n} different Xero ads with the same layout. Look at every grid. "
         f"For each of {n} versions decide the background things:\n"
         f"- background: the template number whose open space fits the layout ({n} different ones)\n"
         "- bloom: whether a bloom shape helps (to frame a photo or add energy), which number, which colour "
         "(blue, green, lightblue, navy, pink, purple, yellow) and its role (behind the main picture | mask around "
         "the photo | accent at an edge). It must bleed off a canvas edge.\n"
         "- logo: the logo number the logo rules allow where it will sit\n"
         "Also pick the 2 real Xero ads whose layout and feel are closest to the competitor ad.\n"
         f"Backgrounds:\n{names('backgrounds.json')}\nBlooms:\n{names('blooms.json')}\nLogos:\n{names('logos.json')}\n"
         'Reply: {"versions": [{"background": 1, "bloom": {"use": true, "number": 3, "colour": "blue", '
         '"role": "..."}, "logo": 2, "why": "..."}], "closest_xero_ads": [4, 7], "why": "..."}',
         ("competitor ad", ref), ("backgrounds grid", g["backgrounds"]), ("blooms grid", g["blooms"]),
         ("logos", g["logos"]), ("real Xero ads grid", g["xero_ads"])]
        + [("logo rules page", flat(p)) for p in LOGO_GUIDES])


async def highlights_director(ref: Image.Image, g: dict, notes: list[str]) -> dict:
    reply = await flash(
        "You are Xero's art director for highlights. Xero brand rules you must follow:\n" + _rules(HIGHLIGHT_RULES)
        + "\n\nReply with JSON only.",
        ["We are rebuilding the competitor ad as a Xero ad with the same layout and the same JOB for each element.\n"
         + TRUE_CLAIMS + "\n" + _notes(notes) + "Look at every grid and decide the highlights:\n"
         "- present / absent: what elements the competitor ad has and doesn't have (short labels)\n"
         "- main_picture: it must show the SAME KIND of thing as the competitor's main picture. source = "
         "illustration (one of ours fits) | product_ui (the ad shows the advertiser's own product; Xero's product is "
         "its app) | generate_photo (the ad shows people or a scene) | generate_object (the ad shows an object, gift "
         "or item: make the Xero equivalent) | generate_illustration | none. For an existing illustration give up to 3 "
         "numbers; for generate give 3 different prompts. Show people ONLY if the competitor's picture shows people. "
         "Natural warm light; no text, logos or brand names in the picture.\n"
         "- product_ui: 0-2 numbers of real Xero screens, only if the ad shows a product.\n"
         "- charms: 0-3 numbers, only if they fit the ad's feel.\n"
         "- text: headline, body (null if none), cta (null if the ad has NO button): same lengths and tone.\n"
         f"- questions: at most {MAX_QUESTIONS}, and only what BLOCKS the ad (the competitor promises a gift, price or "
         "offer and the marketer hasn't told us Xero's). Never guess or fall back on these: ask. Otherwise [].\n"
         "Your main_picture must agree with your present/absent lists.\n"
         f"Illustrations:\n{names('illustrations.json')}\nProduct UI:\n{names('product_ui.json')}\n"
         f"Charms:\n{names('charms.json')}\n"
         'Reply: {"present": [], "absent": [], "main_picture": {"source": "...", "numbers": [], "prompts": []}, '
         '"product_ui": [], "charms": [], "text": {"headline": "...", "body": null, "cta": null}, '
         '"questions": [], "why": "..."}',
         ("competitor ad", ref), ("illustrations grid", g["illustrations"]), ("product UI grid", g["product_ui"]),
         ("charms grid", g["charms"]), ("real Xero ads grid (for picture style)", g["xero_ads"])])
    mp = reply.get("main_picture") or {}
    for key in ("product_ui", "charms", "text", "questions", "why"):  # Flash sometimes nests these
        if key not in reply and key in mp:
            reply[key] = mp.pop(key)
    reply.setdefault("text", {"headline": "", "body": None, "cta": None})
    reply["questions"] = [q for q in (reply.get("questions") or []) if isinstance(q, str)][:MAX_QUESTIONS]
    # An object in the competitor's ad is usually its gift or offer. Never copy it: ask what Xero's is.
    if mp.get("source") == "generate_object" and not notes and not reply["questions"]:
        reply["questions"] = ["The competitor's ad shows an object or gift. What should the Xero version offer "
                              "or show instead?"]
    return reply


async def plan(ref: Image.Image, notes: list[str], n: int) -> dict:
    g = await asyncio.to_thread(grids)
    bg, hi = await asyncio.gather(background_director(ref, g, n), highlights_director(ref, g, notes))
    return {"background": bg, "highlights": hi, "notes": notes}


def plan_summary(p: dict) -> str:
    hi, bg = p["highlights"], p["background"]
    picture = (hi.get("main_picture") or {}).get("source", "none").replace("_", " ")
    backgrounds = ", ".join(str(v.get("background")) for v in bg.get("versions", []))
    q = len(hi.get("questions") or [])
    return (f"picture: {picture}; backgrounds #{backgrounds}; {len(hi.get('product_ui') or [])} product screens; "
            f"{len(hi.get('charms') or [])} charms" + (f"; {q} question{'s' if q > 1 else ''} for you" if q else ""))


# ---- step 2: make ------------------------------------------------------------------

async def rewrite_copy(ref: Image.Image, hi: dict, answers: list[str]) -> dict:
    """Copy rewritten with the marketer's answers (only when there were questions).

    Pro, text only: the draft already carries the competitor's lengths, hook and tone, and
    copy is pure reasoning over words, where Pro writes sharper lines than Flash.
    """
    qa = "\n".join(f"Q: {q}\nA: {a or '(no answer)'}" for q, a in zip(hi.get("questions", []), answers))
    reply = await complete_json("pro", [
        {"role": "system", "content": "You are a Xero copywriter. Reply with JSON only."},
        {"role": "user", "content":
            f"Draft Xero copy for this ad:\n{json.dumps(hi['text'])}\nThe marketer answered:\n{qa}\n{TRUE_CLAIMS}\n"
            "The marketer's answers are true Xero offers and override the claims list; do not add amounts or details "
            "they did not give. REWRITE the copy so the answers become the offer: every answered detail (e.g. "
            "'no credit card needed') must appear in the headline, body or CTA. Keep roughly the draft's lengths "
            "and tone, and fill a body or CTA only where the draft has one. "
            "Xero voice: plain, confident, human, sentence case, a headline that ends with a full stop, "
            "no exclamation marks, no superlatives, no filler greetings like 'Hey there'.\n"
            'Reply: {"headline": "...", "body": null, "cta": null}'},
    ], timeout=60)
    return {k: reply.get(k) for k in ("headline", "body", "cta")} if reply.get("headline") else hi["text"]


COMPOSE = """Make a finished Xero ad.
Image 1 is a competitor ad: copy its LAYOUT exactly (positions, sizes, proportions, empty space) but none of its \
colours, brand, text, products or objects. It contains: {present}. It does NOT contain: {absent}; do not add those.
Image 2 is a real Xero ad: match its look (type, colours, finish).
{pieces}
Write this text, spelled exactly, placed and sized like the matching text in image 1 (Xero bold condensed headline, \
regular body, navy #000856 on light areas, white on blue/navy):
{text}
Do not write any other text.
Xero brand rules that must hold:
{rules}"""


def canvas_size(ref: Image.Image) -> str:
    ratio = ref.height / ref.width
    return "1024x1536" if ratio > 1.15 else "1536x1024" if ratio < 0.85 else "1024x1024"


async def make_pictures(ref: Image.Image, hi: dict, style_ad: Image.Image) -> list[Image.Image]:
    """The main pictures: generated by GPT Image, or taken from our illustrations. [] when none is needed."""
    mp = hi.get("main_picture") or {}
    source = mp.get("source", "none")
    if source.startswith("generate") and mp.get("prompts"):
        kind = {"generate_photo": "photo",
                "generate_object": "product photo of this object on a clean surface"}.get(source, "flat illustration")
        return list(await asyncio.gather(*[gpt_edit(
            [("competitor", ref), ("xero", style_ad)],
            f"Make a new {kind} (no text, no logos, no brand names): {prompt}\n"
            "Match the look of image 2 (a real Xero ad). Image 1 only shows what the picture needs to show, "
            "not its style or brand.", "1024x1024") for prompt in mp["prompts"][:3]]))
    if source == "illustration":
        found = [e for e in (pick("illustrations.json", x) for x in mp.get("numbers", [])) if e]
        return [thumb(e["url"]) for e in found[:3]]
    return []


def compose_inputs(ref: Image.Image, style_ad: Image.Image, version: dict, hi: dict, picture: Image.Image | None,
                   text: dict) -> tuple[list[tuple[str, Image.Image]], str]:
    images = [("competitor", ref), ("xero_style", style_ad)]
    pieces = []
    bg = pick("backgrounds.json", version.get("background"))
    if bg:
        images.append(("background", background_image(bg)))
        pieces.append(f"Image {len(images)}: the background. Use it as the base canvas exactly: same white areas and "
                      "blue shapes, same places and colours.")
    bloom = version.get("bloom") or {}
    entry = pick("blooms.json", bloom.get("number")) if bloom.get("use") else None
    if entry:
        colour = bloom.get("colour") if bloom.get("colour") in (entry.get("variants") or {}) else "blue"
        images.append(("bloom", flat(kit_path(entry["variants"][colour]))))
        pieces.append(f"Image {len(images)}: a Xero bloom shape. Use this exact shape and colour as "
                      f"{bloom.get('role', 'an accent')}; scale it so it bleeds off an edge.")
    if picture is not None:
        images.append(("picture", picture))
        pieces.append(f"Image {len(images)}: the main picture, placed where the competitor's main picture sits.")
    for u in [e for e in (pick("product_ui.json", x) for x in hi.get("product_ui") or []) if e][:2]:
        images.append((u["id"], thumb(u["url"])))
        pieces.append(f"Image {len(images)}: a real Xero product screen. Keep the screen exactly; place it where "
                      "the competitor shows its product.")
    logo = pick("logos.json", version.get("logo")) or load("logos.json")[1]
    images.append(("logo", flat(kit_path(logo["url"]), "#888888")))
    pieces.append(f"Image {len(images)}: the Xero logo, where the competitor's logo sits. Copy it exactly.")
    charms = [e for e in (pick("charms.json", x) for x in hi.get("charms") or []) if e][:3]
    if charms:
        first = len(images) + 1
        for c in charms:
            images.append(("charm", thumb(c["url"])))
        pieces.append(f"Images {first}-{len(images)}: Xero charms. Add them small, near the main picture, never "
                      "over faces, the logo or text.")
    absent = " ".join(hi.get("absent") or []).lower()
    if text.get("cta") and ("button" in absent or "cta" in absent):
        text = {**text, "cta": None}  # the director said the ad has no button; never draw one
    lines = [f'- headline: "{text.get("headline", "")}"']
    if text.get("body"):
        lines.append(f'- body: "{text["body"]}"')
    if text.get("cta"):
        lines.append(f'- button (navy pill, white label): "{text["cta"]}"')
    prompt = COMPOSE.format(present=", ".join(hi.get("present") or []), absent=", ".join(hi.get("absent") or []),
                            pieces="\n".join(pieces), text="\n".join(lines), rules=_rules(COMPOSE_RULES))
    return images, prompt


def style_ad_for(p: dict) -> Image.Image:
    picks = [XERO_ADS[int(x) - 1] for x in p["background"].get("closest_xero_ads") or []
             if str(x).isdigit() and 0 < int(x) <= len(XERO_ADS)]
    return flat(picks[0] if picks else XERO_ADS[6])


def versions_for(p: dict, n: int) -> list[dict]:
    """n versions from the background director's list (cycled if it gave fewer)."""
    given = p["background"].get("versions") or [{"background": 5, "logo": 2}]
    return [given[i % len(given)] for i in range(n)]


def version_summary(version: dict, hi: dict, picture_i: int) -> dict:
    """Small 'how it was designed' record for the Create page and the design file."""
    bg = pick("backgrounds.json", version.get("background"))
    bloom = version.get("bloom") or {}
    mp = hi.get("main_picture") or {}
    return {
        "axis": f"v{picture_i + 1}",
        "background": {"type": bg["name"] if bg else "white"},
        "visual": {"type": mp.get("source", "none").replace("_", " "),
                   "treatment": f"{bloom.get('colour', '')} bloom, {bloom.get('role', '')}" if bloom.get("use") else "plain"},
        "changes": [version.get("why", "")],
    }
