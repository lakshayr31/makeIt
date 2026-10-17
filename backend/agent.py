"""Copilot agent: turns a user request + canvas summary into editor ops.

The agent never draws pixels. It returns a list of ops (add_text, add_image, ...)
that the frontend applies through the same command layer the UI buttons use,
so every result stays an editable layer.
"""

import asyncio
import json

from openai import APITimeoutError, RateLimitError

from config import LLMS

OPS_SPEC = """
Coordinates are canvas pixels; (0,0) is top-left. Ops are applied in order; later ops sit on top.
New elements may set "id" (short slug) so later ops in the same reply can refer to them.

{"op":"add_text","id":"headline","text":"...","x":80,"y":120,"width":920,"fontSize":96,
 "fontFamily":"Inter","fontWeight":"bold"|"normal","fill":"#hex","textAlign":"left"|"center"|"right"}
{"op":"add_image","id":"hero","src":"<asset url from the list>","x":0,"y":0,"width":500,"height":500}
{"op":"add_image","id":"hero","prompt":"<image to generate>","transparent":true,"x":0,"y":0,"width":500,"height":500}
   (use prompt only when no brand asset fits; transparent=true for cut-out subjects, false for full backgrounds)
{"op":"add_shape","id":"pill","shape":"rect"|"circle","x":0,"y":0,"width":300,"height":80,"fill":"#hex","radius":40}
{"op":"update","id":"<existing id>","props":{"text":"...","fill":"#hex","fontSize":80,"x":0,"y":0,"width":0,"height":0,"opacity":1}}
{"op":"delete","id":"<existing id>"}
{"op":"reorder","id":"<existing id>","to":"front"|"back"|"forward"|"backward"}
{"op":"set_background","color":"#hex"}
"""

SYSTEM = f"""You are the design copilot inside a Canva-like editor.
You edit the user's design by emitting ops. Build designs as separate layers
(background, shapes, main visual, accents, text, logo) so the designer can edit each one.

Rules:
- Prefer brand assets (logos, illustrations, charms, backgrounds) from the asset list over generated images.
- Keep text inside the canvas with at least 60px margin; never overlap text on text.
- Text is real text: never ask the image generator to draw words.
- Only reference ids that exist in the canvas summary or that you created earlier in the same reply.

Ops:
{OPS_SPEC}

Reply with JSON only: {{"reply": "<one or two sentences to the user>", "ops": [ ... ]}}"""


async def complete_json(model: str, messages: list[dict], retries: int = 3,
                        timeout: float | None = None) -> dict:
    """Chat completion that must return a JSON object; retries shared-quota 429s.

    timeout: give up on a hung call after this many seconds and retry it (None = SDK default).
    """
    client, model_name = LLMS[model]
    if timeout:
        client = client.with_options(timeout=timeout, max_retries=0)
    for attempt in range(retries + 1):
        try:
            resp = await client.chat.completions.create(
                model=model_name,
                messages=messages,
                response_format={"type": "json_object"},
            )
            return json.loads(resp.choices[0].message.content or "{}")
        except (RateLimitError, APITimeoutError):
            if attempt == retries:
                raise
            await asyncio.sleep(2 * (attempt + 1))
    return {}


async def run_edit(
    request: str, canvas: dict, assets: list[str], model: str, image_url: str | None
) -> dict:
    """One copilot turn: request + current canvas → {reply, ops}."""
    context = (
        f"Canvas: {canvas.get('width')}x{canvas.get('height')}, background {canvas.get('background')}\n"
        f"Elements (bottom to top):\n{json.dumps(canvas.get('elements', []), indent=1)}\n\n"
        f"Brand assets available:\n" + "\n".join(assets) + f"\n\nRequest: {request}"
    )
    content: list[dict] | str = context
    if image_url:
        content = [
            {
                "type": "text",
                "text": context + "\n(The attached image is a reference.)",
            },
            {"type": "image_url", "image_url": {"url": image_url}},
        ]
    result = await complete_json(
        model,
        [{"role": "system", "content": SYSTEM}, {"role": "user", "content": content}],
    )
    return {"reply": result.get("reply", ""), "ops": result.get("ops", [])}
