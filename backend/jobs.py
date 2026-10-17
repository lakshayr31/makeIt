"""Create-from-ad jobs: run the ad → Xero pipeline in the background and stream progress.

The pipeline steps (analyse, match, build, preview, publish) are owned by
generate.py / build.py / publish.py; this module only runs them in order for an
uploaded ad and reports each step as a server-sent event. Events are kept per
job so a page that reconnects replays everything.
"""

import asyncio
import base64
import json
import os
import shutil
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image

import breaker
import designer
from config import ASSETS_DIR, DESIGNS_DIR, GENERATED_DIR, ROOT
from generate import RUNS, analyse, art_direct, match_versions, unknown_ids
from build import build
from preview import main as render_previews, render as render_layout
from publish import AXIS_NAMES, publish
from review_link import pretag, review_and_fix

sys.path.insert(0, str(ROOT))  # review/ lives at the repo root
from review.escalation import escalate  # noqa: E402
from review.run_flat import review_flat  # noqa: E402

COMPETITORS = ASSETS_DIR / "competitors"
UPLOADS = GENERATED_DIR / "uploads"
UPLOADS.mkdir(parents=True, exist_ok=True)
ADS = GENERATED_DIR / "ads"  # finished designer-flow images, served at /generated/ads/
ADS.mkdir(parents=True, exist_ok=True)
# "designer": GPT composes finished ads from real kit pieces (default).
# "layers": the older analyse → match → layout solver pipeline (editable layers).
PIPELINE = os.getenv("MAKEIT_PIPELINE", "designer")
REVIEW_TIMEOUT = 90  # s per image; runs beside the breaker, so it costs no waiting

DESIGNER_STEPS = [
    ("plan", "Art directing: backgrounds, pieces and copy"),
    ("pictures", "Making the main pictures"),
    ("compose", "Composing the versions"),
    ("publish", "Saving designs"),
    ("review", "Checking brand rules"),
    ("layers", "Splitting into editable layers"),
]
STEPS = [
    ("analyse", "Reading the ad's structure"),
    ("direct", "Art directing Xero versions"),
    ("match", "Picking Xero assets and writing copy"),
    ("build", "Generating visuals and laying out"),
    ("publish", "Saving editable designs"),
    ("review", "Checking brand rules and fixing"),
]


@dataclass
class Job:
    id: str
    events: list[dict] = field(default_factory=list)
    changed: asyncio.Event = field(default_factory=asyncio.Event)
    done: bool = False
    answers: asyncio.Future | None = None  # set while the art director waits on the marketer

    def emit(self, event: dict) -> None:
        self.events.append({**event, "t": round(time.time(), 2)})
        self.changed.set()


JOBS: dict[str, Job] = {}


def start_job(image_data_url: str, n: int, fmt: str, prompt: str = "") -> str:
    job = Job(id=uuid.uuid4().hex[:10])
    JOBS[job.id] = job
    header, b64 = image_data_url.split(",", 1)
    ext = "png" if "png" in header else "jpg" if "jpeg" in header else "webp"
    upload = UPLOADS / f"{job.id}.{ext}"
    upload.write_bytes(base64.b64decode(b64))
    steps = DESIGNER_STEPS if PIPELINE == "designer" else STEPS
    job.emit({"type": "start", "steps": [{"id": s, "label": l} for s, l in steps],
              "source": f"/generated/uploads/{upload.name}", "n": n})
    runner = _run_designer if PIPELINE == "designer" else _run
    asyncio.create_task(runner(job, upload, n, fmt, prompt))
    return job.id


def answer_job(job: Job, answers: list[str]) -> bool:
    """The marketer answered the art director's questions; the job continues."""
    if job.answers is None or job.answers.done():
        return False
    job.answers.set_result([str(a) for a in answers])
    return True


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


async def _run_designer(job: Job, upload: Path, n: int, fmt: str, prompt: str = "") -> None:
    """Designer flow: plan (ask if needed) → pictures → compose → publish → review."""
    run = designer.GENERATED_DIR / "runs" / f"job_{job.id}"
    run.mkdir(parents=True, exist_ok=True)
    ref = designer.flat(upload)
    notes = [prompt] if prompt else []
    step = "plan"
    try:
        p = await _step(job, step, designer.plan(ref, notes, n), designer.plan_summary)
        (run / "plan.json").write_text(json.dumps(p, indent=1))
        hi = p["highlights"]
        text = hi["text"]

        questions = hi.get("questions") or []
        if questions:
            job.answers = asyncio.get_running_loop().create_future()
            job.emit({"type": "questions", "questions": questions})
            answers = await job.answers
            job.emit({"type": "answered", "answers": answers})
            if any(a.strip() for a in answers):
                text = await designer.rewrite_copy(ref, hi, answers)
                (run / "copy.json").write_text(json.dumps({"answers": answers, "text": text}, indent=1))

        style_ad = designer.style_ad_for(p)
        step = "pictures"
        pictures = await _step(job, step, designer.make_pictures(ref, hi, style_ad),
                               lambda ps: f"{len(ps)} pictures" if ps else "not needed")
        for i, im in enumerate(pictures):
            im.save(run / f"picture_{i + 1}.png")

        step = "compose"
        size = designer.canvas_size(ref)
        versions = designer.versions_for(p, n)

        async def compose(i: int) -> Image.Image:
            picture = pictures[i % len(pictures)] if pictures else None
            images, prompt_text = designer.compose_inputs(ref, style_ad, versions[i], hi, picture, text)
            (run / f"compose_{i + 1}.txt").write_text(prompt_text)
            return await designer.gpt_edit(images, prompt_text, size)

        finals = await _step(job, step, asyncio.gather(*[compose(i) for i in range(n)]),
                             lambda fs: f"{len(fs)} versions at {size}")

        step = "publish"
        job.emit({"type": "step", "id": step, "status": "running"})
        ids = []
        for i, im in enumerate(finals):
            design_id = f"d-ad-job-{job.id}-{i}"
            im.convert("RGB").save(ADS / f"{design_id}.png")
            thumb = im.convert("RGB").copy()
            thumb.thumbnail((480, 480))
            thumb.save(DESIGNS_DIR / f"{design_id}.png")
            direction = designer.version_summary(versions[i], hi, i)
            record = {
                "id": design_id, "name": f"From ad · Version {i + 1}", "updated_at": time.time(),
                "width": im.width, "height": im.height, "state": None, "layout": None,
                "image": f"/generated/ads/{design_id}.png",
                "inspiration": f"/generated/uploads/{upload.name}", "review": None, "direction": direction,
            }
            _write_design(record)
            ids.append(design_id)
            job.emit({"type": "variant", "index": i, "axis": direction["axis"], "name": record["name"],
                      "design_id": design_id, "layout": None, "image": record["image"],
                      "width": im.width, "height": im.height, "review": None, "direction": direction})
        job.emit({"type": "step", "id": step, "status": "done", "detail": f"{len(ids)} designs saved"})

        step = "review+layers"  # both read the saved images; neither waits for the other
        await asyncio.gather(
            _step(job, "review", _review_images(job, ids), _review_summary),
            _step(job, "layers", _split_all(job, ids, p), lambda ls: f"{sum(1 for l in ls if l)} of {len(ls)} split"),
        )
        job.emit({"type": "done"})
    except Exception as err:  # surface any pipeline failure to the UI
        job.emit({"type": "step", "id": step, "status": "error", "detail": f"{type(err).__name__}: {err}"[:300]})
        job.emit({"type": "done", "error": True})
    finally:
        job.done = True
        job.changed.set()


async def _split_all(job: Job, ids: list[str], plan: dict) -> list[dict | None]:
    """Breaker on every saved version in parallel: layers land on the design as it finishes."""
    async def one(i: int, design_id: str):
        try:
            layout = await asyncio.wait_for(breaker.split(design_id, plan), 120)
        except Exception as err:  # the single-image design stays usable
            print(f"split of {design_id} failed: {err!r}", flush=True)
            job.emit({"type": "layers", "index": i, "design_id": design_id, "layout": None})
            return None
        record = _read_design(design_id)
        if record.get("state") is None:  # not opened yet: next open shows the layers
            record["layout"] = layout
            _write_design(record)
        job.emit({"type": "layers", "index": i, "design_id": design_id, "layout": layout})
        return layout

    return await asyncio.gather(*[one(i, d) for i, d in enumerate(ids)])


async def _review_images(job: Job, ids: list[str]) -> list[dict | None]:
    """Brand check of each finished image (vision + verify; nothing to auto-fix on a flat picture)."""
    async def one(i: int, design_id: str):
        try:
            _design, _raw, checked, _secs = await asyncio.wait_for(review_flat(ADS / f"{design_id}.png"), REVIEW_TIMEOUT)
            found = escalate([f for f in checked if f.get("verified") == "true"])
            review = {"fixed": [],
                      "issues": [f["message"] for f in found if f["tier"] == "issue"],
                      "suggestions": [f["message"] for f in found if f["tier"] == "suggestion"]}
        except Exception as err:  # a failed review never breaks the saved design
            print(f"review of {design_id} failed: {err!r}", flush=True)
            review = None
        record = _read_design(design_id)
        record["review"] = review
        _write_design(record)
        job.emit({"type": "review", "index": i, "design_id": design_id, "review": review})
        return review

    return await asyncio.gather(*[one(i, d) for i, d in enumerate(ids)])


async def _run(job: Job, upload: Path, n: int, fmt: str, prompt: str = "") -> None:
    run_name = f"job_{job.id}"
    run = RUNS / run_name
    run.mkdir(parents=True, exist_ok=True)
    # publish() finds the inspiration ad by run name in assets/competitors.
    COMPETITORS.mkdir(exist_ok=True)
    shutil.copy(upload, COMPETITORS / f"{run_name}{upload.suffix}")

    step = "analyse"
    try:
        spec = await _step(job, step, analyse(upload), _spec_summary)
        if prompt:
            spec["user_brief"] = prompt  # the matcher reads it from SPEC
        (run / "spec.json").write_text(json.dumps(spec, indent=1))

        step = "direct"
        direction = await _step(job, step, art_direct(spec, n, fmt), _direction_summary)
        (run / "direction.json").write_text(json.dumps(direction, indent=1))

        step = "match"
        variants = await _step(job, step, match_versions(spec, direction, fmt), _variants_summary)
        (run / "variants.json").write_text(json.dumps(variants, indent=1))

        step = "build"
        variants["variants"] = variants.get("variants", [])[:n]  # matcher sometimes returns extras
        (run / "variants.json").write_text(json.dumps(variants, indent=1))
        layouts = await _step(job, step, build(run, on_image=pretag), lambda ls: f"{sum(len(l) for l in ls)} layers across {len(ls)} variants")

        await asyncio.to_thread(render_previews, run)  # thumbnails for the designs page

        # Publish first so people can open designs now; the brand review fills in after.
        step = "publish"
        job.emit({"type": "step", "id": step, "status": "running"})
        ids = await asyncio.to_thread(publish, run)
        for i, design_id in enumerate(ids):
            record = _read_design(design_id)
            axis = record["layout"].get("axis") or str(i)
            record["name"] = f"From ad · {AXIS_NAMES.get(axis, axis)}"
            record["review"] = None
            versions = direction.get("versions", [])
            record["direction"] = versions[i] if i < len(versions) else None
            _write_design(record)
            job.emit({"type": "variant", "index": i, "axis": axis, "name": record["name"],
                      "design_id": design_id, "layout": record["layout"], "review": None,
                      "direction": record["direction"]})
        job.emit({"type": "step", "id": step, "status": "done", "detail": f"{len(ids)} designs saved"})

        step = "review"
        await _step(job, step, _review_all(job, run, ids, fmt), _review_summary)
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


async def _review_all(job: Job, run: Path, ids: list[str], fmt: str) -> list[dict | None]:
    """Review + fix every saved version in parallel, emitting each result as it lands."""
    async def one(i: int, design_id: str):
        path = run / f"layout_{i}.json"
        try:
            review = await review_and_fix(path, fmt)
        except Exception as err:  # a failed review never breaks the saved design
            print(f"review of {path.name} failed: {err!r}", flush=True)
            review = None
        record = _read_design(design_id)
        record["review"] = review
        layout = None
        if review and record.get("state") is None:  # not opened yet: swap in the fixed layout
            layout = json.loads(path.read_text())
            record["layout"] = layout
            img = await asyncio.to_thread(render_layout, layout)
            img.convert("RGB").save(DESIGNS_DIR / f"{design_id}.png")
        _write_design(record)
        job.emit({"type": "review", "index": i, "design_id": design_id, "review": review, "layout": layout})
        return review

    return await asyncio.gather(*[one(i, d) for i, d in enumerate(ids)])


def _read_design(design_id: str) -> dict:
    return json.loads((DESIGNS_DIR / f"{design_id}.json").read_text())


def _write_design(record: dict) -> None:
    (DESIGNS_DIR / f"{record['id']}.json").write_text(json.dumps(record))


def _review_summary(reviews: list[dict | None]) -> str:
    done = [r for r in reviews if r]
    fixed = sum(len(r["fixed"]) for r in done)
    left = sum(len(r["issues"]) for r in done)
    skipped = len(reviews) - len(done)
    return f"{fixed} fixed · {left} need you" + (f" · {skipped} not checked" if skipped else "")


def _direction_summary(direction: dict) -> str:
    parts = []
    for v in direction.get("versions", []):
        visual = v.get("visual") or {}
        parts.append(f"{v.get('axis')}: {visual.get('type')} {visual.get('treatment', '')} on {(v.get('background') or {}).get('type')}")
    looked = direction.get("_lookups") or []
    return "; ".join(parts) + (f" (read: {', '.join(looked)})" if looked else "")


def _spec_summary(spec: dict) -> str:
    roles = [s.get("role") for s in spec.get("slots", [])]
    claim = (spec.get("message") or {}).get("claim", "?")
    return f"{len(roles)} parts: {', '.join(roles)}. Message: {claim}"


def _variants_summary(result: dict) -> str:
    variants = result.get("variants", [])
    axes = ", ".join(AXIS_NAMES.get(v.get("axis"), v.get("axis", "?")) for v in variants)
    bad = unknown_ids(result)
    return f"{len(variants)} versions: {axes}" + (f" (unknown assets: {', '.join(bad)})" if bad else "")
