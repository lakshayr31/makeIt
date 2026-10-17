/**
 * Open a solved variant (backend/runs/<ad>/layout_<i>.json, produced by layout.py)
 * as editable layers. Positions are already exact design pixels, so this is a
 * straight mapping: image → image, text → text box, CTA → pill + label, rect → shape.
 */
import type { Editor } from "./Editor";

export interface SolvedLayout {
  axis: string;
  background_colour: string | null;
  layers: SolvedLayer[];
}

interface SolvedLayer {
  id: string;
  role: string;
  type: "image" | "text" | "rect";
  x: number;
  y: number;
  w: number;
  h: number;
  z: number;
  props: {
    src?: string;
    clip?: [number, number, number, number] | null;
    pill?: boolean;
    text?: string;
    font_size?: number;
    weight?: string;
    colour?: string;
    fill?: string;
    radius?: number;
    mask?: string; // id of the layer whose shape this one shows through (photo in a bloom)
  };
}

const DESIGN_W = 1080;
const DESIGN_H = 1350;
// Solver measures text with Arial; matching it keeps line breaks identical.
const FONT = "Arial";
const TEXT_SLACK = 6; // px: browser vs Pillow metrics differ slightly
const LOGO_PILL_PAD = 0.35;

function naturalSize(src: string): Promise<{ w: number; h: number }> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve({ w: img.naturalWidth, h: img.naturalHeight });
    img.onerror = reject;
    img.src = src;
  });
}

/** Cover-fit image: show only the part inside its clip box, as a real crop. */
async function addClippedImage(editor: Editor, l: SolvedLayer) {
  const [cx, cy, cw, ch] = l.props.clip!;
  const { w: nw, h: nh } = await naturalSize(l.props.src!);
  const sx = nw / l.w;
  const sy = nh / l.h;
  await editor.addCroppedImage({
    id: l.id,
    name: l.role,
    src: l.props.src!,
    crop: { x: (cx - l.x) * sx, y: (cy - l.y) * sy, width: cw * sx, height: ch * sy },
    x: cx,
    y: cy,
    width: cw,
    height: ch,
  });
}

async function addImageLayer(editor: Editor, l: SolvedLayer) {
  if (l.props.pill) {
    const pad = l.h * LOGO_PILL_PAD;
    editor.addShape({
      op: "add_shape", id: `${l.id}_pill`, shape: "rect",
      x: l.x - pad, y: l.y - pad, width: l.w + 2 * pad, height: l.h + 2 * pad,
      fill: "#FFFFFF", radius: l.h,
    });
  }
  if (l.props.clip) return addClippedImage(editor, l);
  await editor.addImage({ id: l.id, name: l.role, src: l.props.src!, x: l.x, y: l.y, width: l.w, height: l.h });
}

function addTextLayer(editor: Editor, l: SolvedLayer) {
  const p = l.props;
  const fontSize = p.font_size ?? 40;
  const text = { fontSize, fontFamily: FONT, fontWeight: p.weight === "bold" ? "bold" : "normal", fill: p.colour };
  if (p.pill) {
    editor.addShape({
      op: "add_shape", id: `${l.id}_pill`, shape: "rect",
      x: l.x, y: l.y, width: l.w, height: l.h, fill: p.fill, radius: l.h / 2,
    });
    editor.addText({
      op: "add_text", id: l.id, text: p.text ?? "", textAlign: "center",
      x: l.x, y: l.y + (l.h - fontSize * 1.13) / 2, width: l.w, ...text,
    });
    return;
  }
  editor.addText({ op: "add_text", id: l.id, text: p.text ?? "", x: l.x, y: l.y, width: l.w + TEXT_SLACK, ...text });
}

export async function importLayout(editor: Editor, layout: SolvedLayout) {
  editor.reset(DESIGN_W, DESIGN_H, layout.background_colour ?? "#FFFFFF");
  for (const l of [...layout.layers].sort((a, b) => a.z - b.z)) {
    if (l.type === "image" && l.props.src) await addImageLayer(editor, l);
    else if (l.type === "text") addTextLayer(editor, l);
    else if (l.type === "rect")
      editor.addShape({
        op: "add_shape", id: l.id, shape: "rect",
        x: l.x, y: l.y, width: l.w, height: l.h, fill: l.props.fill, radius: l.props.radius ?? 0,
      });
  }
  // Masks last: both layers must exist. The mask layer stays its own (visible) layer below.
  for (const l of layout.layers) if (l.props.mask) await editor.setMask(l.id, l.props.mask);
  editor.canvas.requestRenderAll();
  editor.commit();
}
