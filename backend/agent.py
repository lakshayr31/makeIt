"""Copilot agent: turns a user request + canvas summary into editor ops.

The agent never draws pixels. It returns a list of ops (add_text, add_image, ...)
that the frontend applies through the same command layer the UI buttons use,
so every result stays an editable layer.
"""

import asyncio
import json
import re
import time
from collections.abc import Callable

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


_JSON_BLOCK = re.compile(r"\{.*\}", re.S)


def _parse_json(content: str | None) -> dict | None:
    content = (content or "").strip()
    for text in (content, (m.group(0) if (m := _JSON_BLOCK.search(content)) else "")):
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass
    return None


async def _create_with_retry(client, retries: int, **kwargs):
    for attempt in range(retries + 1):
        try:
            return await client.chat.completions.create(**kwargs)
        except (RateLimitError, APITimeoutError):
            if attempt == retries:
                raise
            await asyncio.sleep(2 * (attempt + 1))


async def complete_json_with_tools(
    model: str,
    messages: list[dict],
    tools: list[dict],
    handlers: dict[str, Callable],
    max_calls: int = 3,
    retries: int = 3,
    timeout: float | None = None,
) -> dict:
    """JSON completion where the model may call lookup tools first (up to max_calls).

    Tool rounds run WITHOUT response_format: both DeepSeek endpoints accept
    json_object + tools but then never call a tool. If the tool-free answer
    isn't valid JSON, one more call is made in JSON mode with no tools.
    A handler returns str, or (str, [image data URLs]); images go in a follow-up
    user message because tool messages can't carry images.
    Returns the parsed JSON plus "_lookups": [topic per call].
    timeout: per-call seconds before a hung call is retried (None = SDK default).
    """
    client, model_name = LLMS[model]
    if timeout:
        client = client.with_options(timeout=timeout, max_retries=0)
    messages = list(messages)
    lookups: list[str] = []

    async def finish(content: str | None) -> dict:
        result = _parse_json(content)
        if result is None:
            resp = await _create_with_retry(
                client, retries, model=model_name, messages=messages,
                response_format={"type": "json_object"},
            )
            result = _parse_json(resp.choices[0].message.content) or {}
        result["_lookups"] = lookups
        return result

    while len(lookups) < max_calls:
        t0 = time.perf_counter()
        resp = await _create_with_retry(
            client, retries, model=model_name, messages=messages,
            tools=tools, tool_choice="auto",
        )
        msg = resp.choices[0].message
        if not msg.tool_calls:
            return await finish(msg.content)

        messages.append(msg.model_dump(exclude_none=True))
        images: list[str] = []
        for tc in msg.tool_calls:
            name = tc.function.name
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            handler = handlers.get(name)
            if handler is None:
                text = f"Unknown tool {name!r}."
            elif len(lookups) >= max_calls:
                text = "Lookup budget used."
            else:
                out = handler(**args)
                text, imgs = out if isinstance(out, tuple) else (out, [])
                images += imgs
                lookups.append(args.get("topic", name))
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": text})
            print(f"[tools] {model} {name}({args}) model round {time.perf_counter() - t0:.1f}s", flush=True)
        if images:
            messages.append({
                "role": "user",
                "content": [{"type": "text", "text": "Brand-book page image(s) returned by brand_page:"}]
                + [{"type": "image_url", "image_url": {"url": u}} for u in images],
            })

    messages.append({"role": "user", "content": "Lookup budget used. Answer now with the JSON."})
    resp = await _create_with_retry(
        client, retries, model=model_name, messages=messages,
        response_format={"type": "json_object"},
    )
    result = _parse_json(resp.choices[0].message.content) or {}
    result["_lookups"] = lookups
    return result
