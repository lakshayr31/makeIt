"""Competitor ad → Xero variants: Analyst (Flash, vision) then Matcher (Pro).

Writes backend/runs/<ad-name>/{spec.json, variants.json, layout_<i>.json, variants.png}.
Run: backend/.venv/bin/python backend/generate.py assets/competitors/<ad> [N]
"""

import asyncio
import base64
import io
import json
import re
import sys
import time
from pathlib import Path

from PIL import Image

from agent import complete_json
from build import build
from config import ASSETS_DIR
from preview import main as preview
from publish import publish

PROMPTS = Path(__file__).parent / "prompts"
RUNS = Path(__file__).parent / "runs"
CATALOG = ASSETS_DIR / "brand-kit" / "catalog.json"
BRAND_RULES = ASSETS_DIR / "brand-rules" / "brand-rules.md"
CATALOG_FIELDS = ["id", "bucket", "kind", "name", "subjects", "concepts", "colours_available",
                  "aspect", "has_transparency", "mood", "visual_weight", "text_safe_area"]
PRODUCT = (
    "Xero: online accounting software for small businesses. Invoicing, getting paid, "
    "bank reconciliation, payroll, expenses, reporting, all in one place, on any device. "
    "Offer: free 30-day trial."
)
SKIPPED_RULES = {"8.", "9."}  # guideline-sheet artefacts that contradict the reference ads


def _sections(path: Path) -> dict[str, str]:
    """Split a prompt file on its '## ' headings."""
    parts = re.split(r"^## (.+)$", path.read_text(), flags=re.M)
    return {parts[i].strip(): parts[i + 1].strip() for i in range(1, len(parts), 2)}


def _system(sections: dict[str, str]) -> str:
    return sections["System prompt"] + "\n\n## Output schema\n" + sections["Output schema"]


def _image_url(path: Path) -> str:
    img = Image.open(path).convert("RGB")
    img.thumbnail((768, 768))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def _brand_summary() -> str:
    lines = BRAND_RULES.read_text().split("---")[0].splitlines()
    return "\n".join(l for l in lines if l[:1].isdigit() and l.split()[0] not in SKIPPED_RULES)


def _catalog() -> str:
    entries = [e for e in json.loads(CATALOG.read_text()) if e.get("placeable", True)]
    return json.dumps([{k: e[k] for k in CATALOG_FIELDS if k in e} for e in entries])


async def analyse(ad: Path) -> dict:
    s = _sections(PROMPTS / "analyst.md")
    user = s["User message"].strip("`").split("`")[0]
    return await complete_json("flash", [
        {"role": "system", "content": _system(s)},
        {"role": "user", "content": [
            {"type": "text", "text": user},
            {"type": "image_url", "image_url": {"url": _image_url(ad)}},
        ]},
    ])


async def match(spec: dict, n: int, fmt: str = "4:5") -> dict:
    s = _sections(PROMPTS / "matcher.md")
    user = (s["User message"]
            .replace("{{SPEC_JSON}}", json.dumps(spec))
            .replace("{{CATALOG_JSON}}", _catalog())
            .replace("{{BRAND_RULES}}", _brand_summary())
            .replace("{{PRODUCT}}", PRODUCT)
            .replace("{{FORMAT}}", fmt)
            .replace("{{N}}", str(n)))
    return await complete_json("pro", [
        {"role": "system", "content": _system(s)},
        {"role": "user", "content": user},
    ])


def unknown_ids(variants: dict) -> list[str]:
    """Asset ids the matcher used that are not in the catalog."""
    ids = {e["id"] for e in json.loads(CATALOG.read_text())}
    return sorted({s["asset_id"] for v in variants.get("variants", []) for s in v["slots"]
                   if s.get("asset_id") and s["asset_id"] not in ids})


async def main(ad: Path, n: int) -> None:
    out = RUNS / ad.stem
    out.mkdir(parents=True, exist_ok=True)
    t = time.time()
    spec = await analyse(ad)
    (out / "spec.json").write_text(json.dumps(spec, indent=1))
    print(f"analyst: {time.time() - t:.0f}s, {len(spec.get('slots', []))} slots")
    t = time.time()
    variants = await match(spec, n)
    (out / "variants.json").write_text(json.dumps(variants, indent=1))
    print(f"matcher: {time.time() - t:.0f}s, {len(variants.get('variants', []))} variants → {out}")
    if bad := unknown_ids(variants):
        print(f"WARNING unknown asset ids: {bad}")
    t = time.time()
    await build(out)
    preview(out)
    print(f"build + render: {time.time() - t:.0f}s → {out / 'variants.png'}")
    print(f"designs: {publish(out)}")


if __name__ == "__main__":
    asyncio.run(main(Path(sys.argv[1]), int(sys.argv[2]) if len(sys.argv) > 2 else 3))
