"""Read and edit the brand guide makeIt follows (prompts/brand-guide), and list the brand kit by kind.

core.md holds the short rules every agent gets, one per line under `## <topic>`:
    BL1 MUST: Scale blooms beyond the frame ...
topics/<topic>.md holds the long guide for one topic (read on demand via brand_guide()).
"""

import json
import re

import brand_tools
from brand_tools import GUIDE, TOPICS
from config import ROOT

CORE = GUIDE / "core.md"
CATALOG = ROOT / "assets/brand-kit/catalog.json"
RULE = re.compile(r"^([A-Z]{2,3})(\d+) (MUST|SHOULD): (.+)$")
TITLES = {
    "bloom": "Blooms & cropping",
    "template": "Background templates",
    "pattern": "Patterns",
    "photo": "Photography",
    "illustration": "Illustrations",
    "product_ui": "Product UI",
    "charms": "Charms",
    "logo": "Logo",
    "colour": "Colour",
    "type": "Typography",
    "copy": "Copy & voice",
    "layout": "Layout",
}
# Rule id prefix per topic, for topics that have no rules yet to copy it from.
PREFIX = {
    "bloom": "BL",
    "template": "TP",
    "pattern": "PT",
    "photo": "PH",
    "illustration": "IL",
    "product_ui": "PU",
    "charms": "CH",
    "logo": "LG",
    "colour": "CO",
    "type": "TY",
    "copy": "CP",
    "layout": "LY",
}
LEARNED = "## Learned from edits"
# Brand-kit kinds → Elements tab groups, in display order, with the topic that governs them.
GROUPS = [
    ("background_template", "Backgrounds", "template"),
    ("bloom", "Blooms & cropping", "bloom"),
    ("charm", "Charms", "charms"),
    ("product_ui", "Product UI", "product_ui"),
    ("illustration", "Illustrations", "illustration"),
    ("logo", "Logos", "logo"),
]


def _read_core() -> tuple[str, dict[str, list[dict]]]:
    """core.md → (header line, rules per topic in file order)."""
    header, rules, topic = "", {t: [] for t in TOPICS}, None
    for line in CORE.read_text().splitlines():
        if line.startswith("## "):
            topic = line[3:].strip()
            rules.setdefault(topic, [])
        elif topic and (m := RULE.match(line.strip())):
            rules[topic].append(
                {"id": m[1] + m[2], "level": m[3], "text": m[4].strip()}
            )
        elif line.startswith("# "):
            header = line
    return header, rules


def _write_core(header: str, rules: dict[str, list[dict]]) -> None:
    lines = [header]
    for topic, items in rules.items():
        lines.append(f"## {topic}")
        lines += [f"{r['id']} {r['level']}: {r['text']}" for r in items]
    CORE.write_text("\n".join(lines) + "\n")
    _forget_cached_guide()


def _forget_cached_guide() -> None:
    """Agents read the guide through lru_caches; drop them so the next call sees the edit."""
    brand_tools.core_rules.cache_clear()
    brand_tools.brand_guide.cache_clear()


def _detail_path(topic: str):
    return GUIDE / "topics" / f"{topic}.md"


def _topic(topic: str, rules: list[dict]) -> dict:
    path = _detail_path(topic)
    return {
        "id": topic,
        "title": TITLES.get(topic, topic),
        "rules": rules,
        "detail": path.read_text() if path.exists() else "",
    }


def guide() -> dict:
    _, rules = _read_core()
    return {"topics": [_topic(t, rules.get(t, [])) for t in TOPICS]}


def _next_id(topic: str, taken: list[dict]) -> str:
    prefix = (
        taken[0]["id"].rstrip("0123456789")
        if taken
        else PREFIX.get(topic, topic[:2].upper())
    )
    numbers = [
        int(r["id"][len(prefix) :]) for r in taken if r["id"][len(prefix) :].isdigit()
    ]
    return f"{prefix}{max(numbers, default=0) + 1}"


def _clean(rule: dict) -> dict | None:
    """One rule from the client → stored shape, or None if it is empty. Keeps it on one line."""
    text = " ".join(str(rule.get("text", "")).split())
    level = "MUST" if str(rule.get("level", "")).upper() == "MUST" else "SHOULD"
    return {"id": rule.get("id"), "level": level, "text": text} if text else None


def save_topic(topic: str, new_rules: list[dict], detail: str | None) -> dict:
    """Replace one topic's rules (missing ones are deleted, id-less ones get new ids)."""
    if topic not in TOPICS:
        raise KeyError(topic)
    header, rules = _read_core()
    kept, existing = [], {r["id"] for r in rules.get(topic, [])}
    for raw in new_rules:
        rule = _clean(raw)
        if not rule:
            continue
        if rule["id"] not in existing or rule["id"] in {r["id"] for r in kept}:
            rule["id"] = _next_id(topic, rules.get(topic, []) + kept)
        kept.append(rule)
    rules[topic] = kept
    _write_core(header, rules)
    if detail is not None:
        _detail_path(topic).write_text(detail)
        _forget_cached_guide()
    return _topic(topic, kept)


def add_rule(topic: str, level: str, text: str, why: str | None = None) -> dict:
    """Append one rule learned while editing: to core.md, and with its reason to the topic guide."""
    if topic not in TOPICS:
        raise KeyError(topic)
    rule = _clean({"level": level, "text": text})
    if not rule:
        raise ValueError("empty rule")
    header, rules = _read_core()
    rule["id"] = _next_id(topic, rules.get(topic, []))
    rules.setdefault(topic, []).append(rule)
    _write_core(header, rules)

    path = _detail_path(topic)
    detail = path.read_text() if path.exists() else f"# {TITLES.get(topic, topic)}\n"
    if LEARNED not in detail:
        detail = detail.rstrip() + f"\n\n{LEARNED}\n"
    detail = (
        detail.rstrip()
        + f"\n- **{rule['id']} {rule['level']}: {rule['text']}**"
        + (f"\n  - Why: {why}" if why else "")
        + "\n"
    )
    path.write_text(detail)
    _forget_cached_guide()
    return rule


def _item(entry: dict) -> dict:
    variants = entry.get("variants") or {}
    return {
        "id": entry["id"],
        "name": entry.get("name") or entry["id"],
        "src": next(iter(variants.values()), None) or entry["url"],
        "description": entry.get("description") or "",
        "usage_note": entry.get("usage_note") or "",
        "colours": list(variants),
    }


def library() -> dict:
    catalog = json.loads(CATALOG.read_text())
    return {
        "groups": [
            {
                "id": kind,
                "title": title,
                "topic": topic,
                "items": [_item(e) for e in catalog if e.get("kind") == kind],
            }
            for kind, title, topic in GROUPS
        ]
    }


# ---- adding elements ---------------------------------------------------------------

KIND_FILES = {  # kind → split catalog file (assets/brand-kit/catalog/)
    "background_template": "backgrounds.json", "bloom": "blooms.json", "charm": "charms.json",
    "illustration": "illustrations.json", "product_ui": "product_ui.json", "logo": "logos.json",
}
UPLOADS = ROOT / "assets/brand-kit/uploads"


def add_element(kind: str, name: str, image_data_url: str) -> dict:
    """Save an uploaded image as a new kit asset of `kind` and register it in both catalogs."""
    import base64
    import io
    import time

    from PIL import Image

    if kind not in KIND_FILES:
        raise KeyError(kind)
    header, b64 = image_data_url.split(",", 1)
    im = Image.open(io.BytesIO(base64.b64decode(b64)))
    has_alpha = im.mode in ("RGBA", "LA") or "transparency" in im.info
    im = im.convert("RGBA")
    folder = UPLOADS / kind
    folder.mkdir(parents=True, exist_ok=True)
    asset_id = f"{kind}-u{int(time.time())}"
    path = folder / f"{asset_id}.png"
    im.save(path)
    url = "/assets/" + path.relative_to(ROOT / "assets").as_posix()
    bucket = {"background_template": "background", "bloom": "background", "charm": "charm"}.get(kind, "fixed")
    entry = {
        "id": asset_id, "bucket": bucket, "kind": kind, "url": url, "width": im.width, "height": im.height,
        "aspect": round(im.width / im.height, 3), "has_transparency": has_alpha,
        "content_box": [0.0, 0.0, 1.0, 1.0], "placeable": True, "name": name.strip() or asset_id,
        "description": "", "subjects": [], "concepts": [], "mood": [], "usage_note": "Added by the team.",
    }
    for file in (CATALOG, CATALOG.parent / "catalog" / KIND_FILES[kind]):
        if file.exists():
            items = json.loads(file.read_text())
            items.append(entry)
            file.write_text(json.dumps(items, indent=1))
    index = CATALOG.parent / "catalog" / "index.json"
    if index.exists():
        idx = json.loads(index.read_text())
        for key, meta in idx.items():
            if meta.get("kind") == kind:
                meta["count"] = meta.get("count", 0) + 1
        index.write_text(json.dumps(idx, indent=1))
    return _item(entry)
