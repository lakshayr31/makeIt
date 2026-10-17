"""makeIt backend: brand assets, copilot agent, image generation."""

import base64
import mimetypes
import uuid

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from agent import run_edit
from config import ASSETS_DIR, GENERATED_DIR, IMAGE_MODEL, image_client

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".svg"}

app = FastAPI(title="makeIt")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)
app.mount("/assets", StaticFiles(directory=ASSETS_DIR), name="assets")
app.mount("/generated", StaticFiles(directory=GENERATED_DIR), name="generated")


def _asset_urls() -> list[str]:
    return sorted(
        "/assets/" + p.relative_to(ASSETS_DIR).as_posix()
        for p in ASSETS_DIR.rglob("*")
        if p.suffix.lower() in IMAGE_EXTS and not p.name.startswith(".")
    )


def _to_data_url(url: str) -> str:
    """The LLM can't reach localhost, so inline local images as base64."""
    if url.startswith("data:"):
        return url
    for prefix, base in (("/assets/", ASSETS_DIR), ("/generated/", GENERATED_DIR)):
        idx = url.find(prefix)
        if idx != -1:
            path = (base / url[idx + len(prefix) :]).resolve()
            if not path.is_relative_to(base.resolve()) or not path.is_file():
                raise HTTPException(404, f"Image not found: {url}")
            mime = mimetypes.guess_type(path.name)[0] or "image/png"
            return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode()}"
    return url


@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/assets")
def list_assets():
    """Assets grouped by folder, e.g. {"brand-kit/10_Logo": [...], "references": [...]}."""
    groups: dict[str, list[str]] = {}
    for url in _asset_urls():
        parts = url.removeprefix("/assets/").split("/")
        group = "/".join(parts[:2]) if parts[0] == "brand-kit" else parts[0]
        groups.setdefault(group, []).append(url)
    return groups


@app.get("/api/layer-tests")
def list_layer_tests():
    """Layer splits saved as assets/layers/*.json, for opening in the editor."""
    return sorted(f"/assets/layers/{p.name}" for p in (ASSETS_DIR / "layers").glob("*.json"))


class EditRequest(BaseModel):
    request: str
    canvas: dict
    model: str = "flash"
    reference_url: str | None = None


@app.post("/api/agent/edit")
async def agent_edit(body: EditRequest):
    if body.model not in ("flash", "pro"):
        raise HTTPException(400, "model must be flash or pro")
    brand_assets = [u for u in _asset_urls() if u.startswith("/assets/brand-kit/")]
    image = _to_data_url(body.reference_url) if body.reference_url else None
    model = "flash" if image else body.model  # only Flash reads images
    return await run_edit(body.request, body.canvas, brand_assets, model, image)


class ImageRequest(BaseModel):
    prompt: str
    transparent: bool = False
    size: str = "1024x1024"
    quality: str = "medium"


@app.post("/api/image")
async def generate_image(body: ImageRequest):
    """GPT Image Flare → PNG saved under /generated, returns its URL."""
    result = await image_client.images.generate(
        model=IMAGE_MODEL,
        prompt=body.prompt,
        size=body.size,
        quality=body.quality,
        background="transparent" if body.transparent else "opaque",
        output_format="png",
    )
    data = result.data[0]
    if not data.b64_json:
        raise HTTPException(502, "Image model returned no image")
    name = f"{uuid.uuid4().hex}.png"
    (GENERATED_DIR / name).write_bytes(base64.b64decode(data.b64_json))
    return {"url": f"/generated/{name}"}
