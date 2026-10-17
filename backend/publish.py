"""Publish a solved run as designs: one saved design per variant.

Each design starts with the solved `layout` (the editor turns it into layers on
first open, then autosave stores the real canvas) and keeps the competitor ad as
its `inspiration`, shown in the editor's Uploads tab.
Run: backend/.venv/bin/python backend/publish.py backend/runs/<ad>
"""

import json
import shutil
import sys
import time
from pathlib import Path

from config import ASSETS_DIR, DESIGNS_DIR

AXIS_NAMES = {
    "faithful": "Closest match",
    "hero": "New visual",
    "palette": "New colours",
    "mirror": "Mirrored",
    "copy": "New copy",
}


def publish(run: Path) -> list[str]:
    source = next((ASSETS_DIR / "competitors").glob(f"{run.name}.*"), None)
    title = run.name.replace("_", " ").capitalize()
    slug = run.name.lower().replace("_", "-")
    ids = []
    for path in sorted(run.glob("layout_*.json")):
        layout = json.loads(path.read_text())
        index = path.stem.split("_")[1]
        design_id = f"d-ad-{slug}-{index}"
        axis = layout.get("axis") or index
        (DESIGNS_DIR / f"{design_id}.json").write_text(
            json.dumps(
                {
                    "id": design_id,
                    "name": f"{title} · {AXIS_NAMES.get(axis, axis)}",
                    "updated_at": time.time(),
                    "width": 1080,
                    "height": 1350,
                    "state": None,
                    "layout": layout,
                    "inspiration": f"/assets/competitors/{source.name}"
                    if source
                    else None,
                }
            )
        )
        preview = run / f"{path.stem}_{axis}.png"
        if preview.exists():
            shutil.copy(preview, DESIGNS_DIR / f"{design_id}.png")
        ids.append(design_id)
    return ids


if __name__ == "__main__":
    print(publish(Path(sys.argv[1])))
