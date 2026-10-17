"""On-demand Xero brand-guide lookups for LLM agents (OpenAI tools format)."""

import base64
import io
import json
from functools import lru_cache

from PIL import Image

from config import ROOT

TOPICS = [
    "bloom",
    "template",
    "pattern",
    "photo",
    "illustration",
    "product_ui",
    "charms",
    "logo",
    "colour",
    "type",
    "copy",
    "layout",
]
GUIDE = ROOT / "prompts/brand-guide"
MAX_SIDE = 1280
MAX_PAGES = 2


@lru_cache(maxsize=1)
def core_rules() -> str:
    path = GUIDE / "core.md"
    return path.read_text() if path.exists() else ""


def _unknown(topic: str) -> str:
    return f"Unknown topic {topic!r}. Valid topics: {', '.join(TOPICS)}"


@lru_cache(maxsize=None)
def brand_guide(topic: str) -> str:
    if topic not in TOPICS:
        return _unknown(topic)
    path = GUIDE / "topics" / f"{topic}.md"
    return path.read_text() if path.exists() else f"No guide written yet for {topic!r}."


def _png_data_url(path) -> str:
    img = Image.open(path)
    img.thumbnail((MAX_SIDE, MAX_SIDE))
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGBA")
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


@lru_cache(maxsize=None)
def _page_images(topic: str) -> tuple[str, ...]:
    pages_file = GUIDE / "pages.json"
    if topic not in TOPICS or not pages_file.exists():
        return ()
    paths = json.loads(pages_file.read_text()).get(topic, [])
    return tuple(
        _png_data_url(ROOT / p) for p in paths[:MAX_PAGES] if (ROOT / p).exists()
    )


def brand_page_images(topic: str) -> list[str]:
    """Data URLs (PNG, max side 1280) for up to 2 brand-book pages on this topic."""
    return list(_page_images(topic))


def _topic_tool(name: str, description: str) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": {"topic": {"type": "string", "enum": TOPICS}},
                "required": ["topic"],
            },
        },
    }


GUIDE_TOOL = _topic_tool(
    "brand_guide",
    "Read the full Xero brand rules for one topic (detail, how to apply, edge cases). "
    "Use when the core rules are not enough to decide.",
)
PAGE_TOOL = _topic_tool(
    "brand_page",
    "Return the original Xero brand-book page image(s) for one topic, to compare a design "
    "against visually. Reviewer only; costs more than brand_guide.",
)


def brand_page(topic: str) -> tuple[str, list[str]]:
    """Tool handler: short text for the tool message + images for a follow-up user message."""
    if topic not in TOPICS:
        return _unknown(topic), []
    images = brand_page_images(topic)
    if not images:
        return f"No brand-book pages mapped for {topic!r}.", []
    return f"{len(images)} brand-book page image(s) for {topic!r} follow in the next message.", images


HANDLERS = {"brand_guide": brand_guide, "brand_page": brand_page}


# --- Blooms playbook: given in full to every agent that composes, edits or reviews ---

PLAYBOOK = GUIDE / "blooms_playbook.md"


@lru_cache(maxsize=1)
def blooms_playbook() -> str:
    return PLAYBOOK.read_text() if PLAYBOOK.exists() else ""


def with_playbook(system: str) -> str:
    """Append the blooms playbook to an agent's system prompt."""
    playbook = blooms_playbook()
    return f"{system}\n\n---\n{playbook}" if playbook else system

