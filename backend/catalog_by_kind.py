"""Write catalog.json split by category, for people browsing the brand kit.

catalog.json stays the source (the pipeline reads it as one list); this writes
assets/brand-kit/catalog/<category>.json, one file per kind, plus index.json.
Re-run after catalog.py changes the catalog.
Run: backend/.venv/bin/python backend/catalog_by_kind.py
"""

import json

from config import ASSETS_DIR

CATALOG = ASSETS_DIR / "brand-kit/catalog.json"
OUT = ASSETS_DIR / "brand-kit/catalog"
# kind in catalog.json → file name, in display order
CATEGORIES = {
    "background_template": "backgrounds",
    "bloom": "blooms",
    "charm": "charms",
    "illustration": "illustrations",
    "product_ui": "product_ui",
    "logo": "logos",
}


def main() -> None:
    catalog = json.loads(CATALOG.read_text())
    OUT.mkdir(exist_ok=True)
    index = {}
    for kind, name in CATEGORIES.items():
        items = [e for e in catalog if e["kind"] == kind]
        (OUT / f"{name}.json").write_text(json.dumps(items, indent=1))
        index[name] = {"kind": kind, "count": len(items), "file": f"{name}.json"}
    unsorted = [e["id"] for e in catalog if e["kind"] not in CATEGORIES]
    if unsorted:
        index["uncategorised"] = unsorted
    (OUT / "index.json").write_text(json.dumps(index, indent=1))
    print(json.dumps(index, indent=1))


if __name__ == "__main__":
    main()
