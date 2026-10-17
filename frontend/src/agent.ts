// Client for the chat agent (see docs/agent-chat-contract.md) + canvas helpers it needs.
import { FabricImage, Point, Textbox } from "fabric";
import type { Editor, ImageGenerator } from "./editor/Editor";
import type { CanvasSummary, Op } from "./editor/types";

export type Box = [number, number, number, number];

export type ChatContext =
  | { kind: "element"; id: string; name: string }
  | { kind: "area"; box: Box }
  | null;

export type Intent =
  "layout" | "remove" | "swap" | "generate" | "clarify" | "other";

export interface ChatOption {
  label?: string;
  src: string;
  warning?: string | null; // generated image still failed the brand check after one retry
}

export interface BrandIssue {
  element_id: string;
  check?: string;
  message: string;
  fixable?: boolean;
}

export interface CheckResponse {
  passed: boolean;
  issues: BrandIssue[];
  ops: Op[];
  fixed: string[];
}

export interface GeneratePlan {
  prompt: string;
  box: Box;
  mode: "replace" | "add";
  target_id: string | null;
  transparent: boolean;
}

export interface TurnRequest {
  request: string;
  screenshot: string;
  canvas: CanvasSummary;
  context:
    | { kind: "element"; id: string }
    | { kind: "area"; box: Box; touches: string[] }
    | null;
  inspiration: string | null;
  selection_image: string | null; // close-up of the selected element or area
  history: { role: "user" | "agent"; text: string }[];
}

export interface TurnResponse {
  intent: Intent;
  reply?: string;
  ops?: Op[];
  question?: { text: string; choices: string[] };
  target_id?: string;
  options?: ChatOption[];
  generate?: GeneratePlan;
  swap?: unknown;
  override?: { label: string; ops: Op[] }; // literal off-brand version of the request, if it asked for one
}

export const agentCheck = (req: {
  request: string;
  screenshot: string;
  canvas: CanvasSummary;
  changed_ids: string[];
  vision: boolean;
}) => postJSON<CheckResponse>("/api/agent/check", req);

async function postJSON<T>(url: string, body: unknown): Promise<T> {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok)
    throw new Error(`${res.status} ${(await res.text()).slice(0, 200)}`);
  return res.json();
}

export const agentTurn = (req: TurnRequest) =>
  postJSON<TurnResponse>("/api/agent/turn", req);

export const agentGenerate = (req: {
  prompt: string;
  box: Box;
  transparent: boolean;
  n: number;
}) => postJSON<{ options: ChatOption[] }>("/api/agent/generate", req);

/** ImageGenerator for Editor.applyOps when the agent's ops include a prompt-only add_image. */
export const generateOne: ImageGenerator = async (
  prompt,
  transparent,
  width,
  height,
) => {
  const { options } = await agentGenerate({
    prompt,
    box: [0, 0, width, height],
    transparent,
    n: 1,
  });
  if (!options[0]) throw new Error("No image generated");
  return options[0].src;
};

const SCREENSHOT_MAX_SIDE = 1280;
const BOX_STROKE = 6;
const SELECTION_MAX_SIDE = 480;

async function downscale(src: string, maxSide: number, crop?: Box): Promise<string> {
  const img = new Image();
  img.src = src;
  await img.decode();
  const [sx, sy, sw, sh] = crop ?? [0, 0, img.width, img.height];
  const scale = Math.min(1, maxSide / Math.max(sw, sh));
  const out = document.createElement("canvas");
  out.width = Math.max(1, Math.round(sw * scale));
  out.height = Math.max(1, Math.round(sh * scale));
  out.getContext("2d")!.drawImage(img, sx, sy, sw, sh, 0, 0, out.width, out.height);
  return out.toDataURL("image/png");
}

/** Small picture of what the message is about: the element itself, or the canvas inside the area box. */
export async function selectionImage(editor: Editor, ctx: ChatContext): Promise<string | null> {
  if (!ctx) return null;
  if (ctx.kind === "element") {
    const png = editor.exportElement(ctx.id);
    return png ? downscale(png, SELECTION_MAX_SIDE) : null;
  }
  const active = editor.canvas.getActiveObject();
  const full = editor.exportPNG(); // design-pixel scale, so the box maps 1:1
  if (active) editor.canvas.setActiveObject(active);
  editor.canvas.requestRenderAll();
  return downscale(full, SELECTION_MAX_SIDE, ctx.box);
}

/** Design PNG (downscaled to ≤1280px) with the area box outlined in orange. */
export async function screenshotWithBox(
  editor: Editor,
  box: Box | null,
): Promise<string> {
  const active = editor.canvas.getActiveObject();
  const full = editor.exportPNG(); // design-pixel scale (multiplier = 1/zoom)
  if (active) editor.canvas.setActiveObject(active);
  editor.canvas.requestRenderAll();

  const img = new Image();
  img.src = full;
  await img.decode();
  const scale = Math.min(
    1,
    SCREENSHOT_MAX_SIDE / Math.max(img.width, img.height),
  );
  const out = document.createElement("canvas");
  out.width = Math.round(img.width * scale);
  out.height = Math.round(img.height * scale);
  const ctx = out.getContext("2d")!;
  ctx.drawImage(img, 0, 0, out.width, out.height);
  if (box) {
    // Box is in design pixels; the export is design-sized before our downscale.
    const k = out.width / editor.width;
    ctx.strokeStyle = "#ff6a13";
    ctx.lineWidth = BOX_STROKE;
    ctx.strokeRect(box[0] * k, box[1] * k, box[2] * k, box[3] * k);
  }
  return out.toDataURL("image/png");
}

/** Swap an image's src in place: same on-canvas box, new picture cover-fitted into it. One undo step. */
export async function replaceImageSrc(editor: Editor, id: string, src: string) {
  const obj = editor.find(id);
  if (!(obj instanceof FabricImage)) throw new Error(`"${id}" is not an image`);
  const tl = obj.getPointByOrigin("left", "top");
  const boxW = obj.getScaledWidth();
  const boxH = obj.getScaledHeight();
  await obj.setSrc(src, { crossOrigin: "anonymous" });
  const el = obj.getElement() as HTMLImageElement;
  const iw = el.naturalWidth || el.width;
  const ih = el.naturalHeight || el.height;
  const scale = Math.max(boxW / iw, boxH / ih);
  const cropW = boxW / scale;
  const cropH = boxH / scale;
  obj.set({
    src,
    cropX: (iw - cropW) / 2,
    cropY: (ih - cropH) / 2,
    width: cropW,
    height: cropH,
    scaleX: scale,
    scaleY: scale,
  });
  obj.setPositionByOrigin(new Point(tl.x, tl.y), "left", "top");
  obj.setCoords();
  editor.canvas.requestRenderAll();
  editor.commit();
}

/** Add a generated image at `box`, stacked above the background and below the lowest text. One undo step. */
export async function addImageBelowText(
  editor: Editor,
  src: string,
  box: Box,
  name = "generated",
) {
  const [x, y, width, height] = box;
  const img = await editor.addImage({ src, x, y, width, height, name });
  const objs = editor.canvas.getObjects();
  const firstText = objs.findIndex((o) => o instanceof Textbox);
  if (firstText >= 0 && firstText < objs.indexOf(img))
    editor.canvas.moveObjectTo(img, firstText);
  editor.canvas.requestRenderAll();
  editor.commit();
}

/** Briefly flash a selection outline on an element so the user sees what changed. */
export function pulse(editor: Editor, id: string) {
  if (!editor.find(id)) return;
  editor.select(id);
  setTimeout(() => {
    if (editor.selected()?.get("id") === id) {
      editor.canvas.discardActiveObject();
      editor.canvas.requestRenderAll();
    }
  }, 900);
}
