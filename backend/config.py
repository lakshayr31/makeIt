"""Env + API clients. Keys live in ../.env (never committed)."""

import os
from pathlib import Path

from dotenv import load_dotenv
from openai import AsyncOpenAI

ROOT = Path(__file__).resolve().parent.parent
ASSETS_DIR = ROOT / "assets"
GENERATED_DIR = Path(__file__).resolve().parent / "generated"
GENERATED_DIR.mkdir(exist_ok=True)

load_dotenv(ROOT / ".env")


def _require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing {name} in .env (see .env.example)")
    return value


IMAGE_MODEL = os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-2.5-flare")
image_client = AsyncOpenAI(api_key=_require("OPENAI_API_KEY"))

# "flash" reads images and is fast; "pro" for heavier planning.
LLMS = {
    "flash": (
        AsyncOpenAI(
            base_url=_require("DEEPSEEK_FLASH_BASE_URL"),
            api_key=_require("DEEPSEEK_FLASH_API_KEY"),
        ),
        _require("DEEPSEEK_FLASH_MODEL"),
    ),
    "pro": (
        AsyncOpenAI(
            base_url=_require("DEEPSEEK_PRO_BASE_URL"),
            api_key=_require("DEEPSEEK_PRO_API_KEY"),
        ),
        _require("DEEPSEEK_PRO_MODEL"),
    ),
}
