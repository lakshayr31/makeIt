"""Create-from-ad jobs: run the ad → Xero pipeline in the background and stream progress.

The pipeline steps (analyse, match, build, preview, publish) are owned by
generate.py / build.py / publish.py; this module only runs them in order for an
uploaded ad and reports each step as a server-sent event. Events are kept per
job so a page that reconnects replays everything.
"""

import asyncio
import base64
import json
import shutil
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from config import ASSETS_DIR, DESIGNS_DIR, GENERATED_DIR
from generate import RUNS, analyse, match, unknown_ids
from build import build
from preview import main as render_previews
from publish import AXIS_NAMES, publish
from review_link import review_and_fix

COMPETITORS = ASSETS_DIR / "competitors"
UPLOADS = GENERATED_DIR / "uploads"
UPLOADS.mkdir(parents=True, exist_ok=True)

STEPS = [
    ("analyse", "Reading the ad's structure"),
    ("match", "Rebuilding it with Xero assets and copy"),
    ("build", "Generating visuals and laying out"),
    ("review", "Checking brand rules and fixing"),
    ("publish", "Saving editable designs"),
]


@dataclass
class Job:
    id: str
    events: list[dict] = field(default_factory=list)
    changed: asyncio.Event = field(default_factory=asyncio.Event)
    done: bool = False

    def emit(self, event: dict) -> None:
        self.events.append({**event, "t": round(time.time(), 2)})
        self.changed.set()


JOBS: dict[str, Job] = {}


def start_job(image_data_url: str, n: int, fmt: str) -> str:
    job = Job(id=uuid.uuid4().hex[:10])
    JOBS[job.id] = job
    header, b64 = image_data_url.split(",", 1)
    ext = "png" if "png" in header else "jpg" if "jpeg" in header else "webp"
    upload = UPLOADS / f"{job.id}.{ext}"
    upload.write_bytes(base64.b64decode(b64))
    job.emit({"type": "start", "steps": [{"id": s, "label": l} for s, l in STEPS],
              "source": f"/generated/uploads/{upload.name}", "n": n})
    asyncio.create_task(_run(job, upload, n, fmt))
    return job.id


async def stream(job: Job):
    """Server-sent events: replay history, then follow until done."""
    sent = 0
    while True:
        while sent < len(job.events):
            yield f"data: {json.dumps(job.events[sent])}\n\n"
            sent += 1
        if job.done:
            return
        job.changed.clear()
        try:
            await asyncio.wait_for(job.changed.wait(), timeout=15)
        except TimeoutError:
            yield ": keep-alive\n\n"


async def _run(job: Job, upload: Path, n: int, fmt: str) -> None:
    run_name = f"job_{job.id}"
    run = RUNS / run_name
    run.mkdir(parents=True, exist_ok=True)
    # publish() finds the inspiration ad by run name in assets/competitors.
    COMPETITORS.mkdir(exist_ok=True)
    shutil.copy(upload, COMPETITORS / f"{run_name}{upload.suffix}")

    step = "analyse"
    try:
        spec = await _step(job, step, analyse(upload), _spec_summary)
        (run / "spec.json").write_text(json.dumps(spec, indent=1))

        step = "match"
        variants = await _step(job, step, match(spec, n, fmt), _variants_summary)
        (run / "variants.json").write_text(json.dumps(variants, indent=1))

        step = "build"
        variants["variants"] = variants.get("variants", [])[:n]  # matcher sometimes returns extras
        (run / "variants.json").write_text(json.dumps(variants, indent=1))
        layouts = await _step(job, step, build(run), lambda ls: f"{sum(len(l) for l in ls)} layers across {len(ls)} variants")

        step = "review"
        reviews = await _step(job, step, _review_all(run, len(layouts), fmt), _review_summary)
        await asyncio.to_thread(render_previews, run)  # thumbnails of the fixed layouts

        step = "publish"
        job.emit({"type": "step", "id": step, "status": "running"})
        ids = await asyncio.to_thread(publish, run)
        for i, design_id in enumerate(ids):
            record = json.loads((DESIGNS_DIR / f"{design_id}.json").read_text())
            axis = record["layout"].get("axis") or str(i)
            record["name"] = f"From ad · {AXIS_NAMES.get(axis, axis)}"
            record["review"] = reviews[i] if i < len(reviews) else None
            (DESIGNS_DIR / f"{design_id}.json").write_text(json.dumps(record))
            job.emit({"type": "variant", "index": i, "axis": axis, "name": record["name"],
                      "design_id": design_id, "layout": record["layout"], "review": record["review"]})
        job.emit({"type": "step", "id": step, "status": "done", "detail": f"{len(ids)} designs saved"})
        job.emit({"type": "done"})
    except Exception as err:  # surface any pipeline failure to the UI
        job.emit({"type": "step", "id": step, "status": "error", "detail": f"{type(err).__name__}: {err}"[:300]})
        job.emit({"type": "done", "error": True})
    finally:
        job.done = True
        job.changed.set()


async def _step(job: Job, step: str, work, summarise):
    """Run one pipeline step, emitting running → done (with timing and a summary)."""
    job.emit({"type": "step", "id": step, "status": "running"})
    t = time.time()
    result = await work
    job.emit({"type": "step", "id": step, "status": "done", "secs": round(time.time() - t, 1), "detail": summarise(result)})
    return result


async def _review_all(run: Path, count: int, fmt: str) -> list[dict | None]:
    """Review + fix every version in parallel. A failed review never blocks publishing."""
    async def one(i: int):
        try:
            return await review_and_fix(run / f"layout_{i}.json", fmt)
        except Exception as err:
            print(f"review of layout_{i} failed: {err!r}", flush=True)
            return None
    return await asyncio.gather(*[one(i) for i in range(count)])


def _review_summary(reviews: list[dict | None]) -> str:
    done = [r for r in reviews if r]
    fixed = sum(len(r["fixed"]) for r in done)
    left = sum(len(r["issues"]) for r in done)
    skipped = len(reviews) - len(done)
    return f"{fixed} fixed · {left} need you" + (f" · {skipped} not checked" if skipped else "")


def _spec_summary(spec: dict) -> str:
    roles = [s.get("role") for s in spec.get("slots", [])]
    claim = (spec.get("message") or {}).get("claim", "?")
    return f"{len(roles)} parts: {', '.join(roles)}. Message: {claim}"


def _variants_summary(result: dict) -> str:
    variants = result.get("variants", [])
    axes = ", ".join(AXIS_NAMES.get(v.get("axis"), v.get("axis", "?")) for v in variants)
    bad = unknown_ids(result)
    return f"{len(variants)} versions: {axes}" + (f" (unknown assets: {', '.join(bad)})" if bad else "")
