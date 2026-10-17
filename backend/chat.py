"""Chat edits: one Flash call decides the intent; swap picks brand-kit assets; generate makes 3 images.

Contract: docs/agent-chat-contract.md.
"""

import asyncio
import json
import re

from agent import complete_json
from build import _generate
from config import ROOT

PROMPTS = ROOT / "prompts"
CATALOG = ROOT / "assets/brand-kit/catalog.json"
INTENTS = {"layout", "remove", "swap", "generate", "clarify", "other"}
SWAP_OPTIONS = 3
HISTORY_LIMIT = 6


def _catalog() -> list[dict]:
    return json.loads(CATALOG.read_text())


def _entry_src(entry: dict) -> str:
    variants = entry.get("variants") or {}
    return next(iter(variants.values()), None) or entry["url"]


def _kind_of(src: str | None, catalog: list[dict]) -> str | None:
    for e in catalog:
        if src and (e["url"] == src or src in (e.get("variants") or {}).values()):
            return e["kind"]
    if src and "/parts/charms/" in src:
        return "charm"
    if src and "/parts/blooms/" in src:
        return "bloom"
    return None


def swap_options(kind: str | None, query: str, current_src: str | None) -> list[dict]:
    """Brand-kit assets of the same kind, ranked by keyword overlap with the query."""
    catalog = _catalog()
    kind = kind or _kind_of(current_src, catalog) or "illustration"
    words = set(re.findall(r"[a-z]+", query.lower()))

    def text(e):
        fields = [
            e.get("name"),
            e.get("description"),
            e.get("usage_note"),
            *(e.get("subjects") or []),
            *(e.get("concepts") or []),
        ]
        return " ".join(str(f) for f in fields if f).lower()

    pool = [e for e in catalog if e["kind"] == kind and _entry_src(e) != current_src]
    pool.sort(key=lambda e: -len(words & set(re.findall(r"[a-z]+", text(e)))))
    return [
        {"label": e.get("name") or e["id"], "src": _entry_src(e)}
        for e in pool[:SWAP_OPTIONS]
    ]


def _src_of(canvas: dict, element_id: str | None) -> str | None:
    for el in canvas.get("elements", []):
        if el.get("id") == element_id:
            return el.get("src")
    return None


def _style(prompt: str) -> str:
    style_file = PROMPTS / "image_style.md"
    style = style_file.read_text().strip() if style_file.exists() else ""
    return prompt if not style or "Xero" in prompt else f"{prompt} {style}"


async def turn(body: dict) -> dict:
    """User message + design context → intent + what the editor should do."""
    context = {k: body.get(k) for k in ("request", "context", "canvas")}
    context["history"] = (body.get("history") or [])[-HISTORY_LIMIT:]
    context["inspiration_attached"] = bool(body.get("inspiration"))
    content = [
        {"type": "text", "text": json.dumps(context)},
        {"type": "text", "text": "Image `design` (area box drawn in orange, if any):"},
        {"type": "image_url", "image_url": {"url": body["screenshot"]}},
    ]
    if body.get("inspiration"):
        content += [
            {"type": "text", "text": "Image `inspiration` (attached by the user):"},
            {"type": "image_url", "image_url": {"url": body["inspiration"]}},
        ]
    result = await complete_json(
        "flash",
        [
            {"role": "system", "content": (PROMPTS / "agent_turn.md").read_text()},
            {"role": "user", "content": content},
        ],
    )

    intent = result.get("intent") if result.get("intent") in INTENTS else "other"
    result["intent"] = intent
    if intent == "swap":
        swap = result.get("swap") or {}
        current = _src_of(body.get("canvas") or {}, result.get("target_id"))
        result["options"] = swap_options(
            swap.get("kind"), swap.get("query") or body.get("request", ""), current
        )
    if intent == "generate" and result.get("generate"):
        result["generate"]["prompt"] = _style(result["generate"].get("prompt", ""))
    return result


def _size_for(box: list[float]) -> str:
    aspect = box[2] / box[3] if box and box[3] else 1
    return (
        "1536x1024" if aspect > 1.2 else "1024x1536" if aspect < 0.83 else "1024x1024"
    )


async def generate(
    prompt: str, box: list[float], transparent: bool, n: int
) -> list[dict]:
    """n variations in parallel. Each prompt gets a variation tag so the image cache doesn't return n copies."""
    size = _size_for(box)
    urls = await asyncio.gather(
        *[
            _generate(f"{prompt} (variation {i + 1})", size, transparent)
            for i in range(n)
        ]
    )
    return [{"src": u} for u in urls]
