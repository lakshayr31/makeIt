/**
 * Open an AI layer split (assets/layers/*.json) as editable layers.
 * Text becomes real text, shapes become shapes, and photos are cropped
 * out of the original reference by their bounding box.
 */
import type { Editor } from "./Editor";

export interface LayerSplit {
  reference: string;
  canvas: { w: number; h: number; background: string };
  layers: SplitLayer[];
}

interface SplitLayer {
  id: string;
  type:
    | "shape"
    | "image"
    | "text"
    | "button"
    | "card"
    | "logo"
    | "sticker"
    | string;
  bbox: [number, number, number, number];
  z: number;
  text?: string;
  fill?: string;
  shape?: "blob" | "rect" | "rounded-rect" | "circle" | string;
  font?: { weight?: string; size_px?: number; color?: string };
  description?: string;
}

const DESIGN_WIDTH = 1080;
const BUTTON_PADDING_RATIO = 0.5;

export async function importLayers(editor: Editor, split: LayerSplit) {
  const s = DESIGN_WIDTH / split.canvas.w;
  editor.reset(
    DESIGN_WIDTH,
    Math.round(split.canvas.h * s),
    split.canvas.background,
  );

  for (const l of [...split.layers].sort((a, b) => a.z - b.z)) {
    const [bx, by, bw, bh] = l.bbox;
    const box = { x: bx * s, y: by * s, width: bw * s, height: bh * s };
    const font = {
      fontSize: (l.font?.size_px ?? 24) * s,
      fontWeight: l.font?.weight === "bold" ? "bold" : "normal",
      fill: l.font?.color ?? "#111111",
    };

    if (l.type === "image") {
      await editor.addCroppedImage({
        id: l.id,
        src: split.reference,
        crop: { x: bx, y: by, width: bw, height: bh },
        ...box,
        name: l.description,
      });
    } else if (l.type === "text" || l.type === "logo") {
      editor.addText({
        op: "add_text",
        id: l.id,
        text: l.text ?? "",
        x: box.x,
        y: box.y,
        width: box.width,
        ...font,
      });
    } else if (l.type === "button") {
      editor.addShape({
        op: "add_shape",
        id: l.id,
        shape: "rect",
        ...box,
        fill: l.fill,
        radius: box.height / 2,
      });
      const textY = box.y + (box.height - font.fontSize) * BUTTON_PADDING_RATIO;
      editor.addText({
        op: "add_text",
        id: `${l.id}_label`,
        text: l.text ?? "",
        x: box.x,
        y: textY,
        width: box.width,
        textAlign: "center",
        ...font,
      });
    } else {
      const shape = l.shape === "circle" ? "circle" : "rect";
      const radius =
        l.shape === "blob"
          ? Math.min(box.width, box.height) / 3
          : l.shape === "rounded-rect"
            ? 12 * s
            : 0;
      editor.addShape({
        op: "add_shape",
        id: l.id,
        shape,
        ...box,
        fill: l.fill ?? "#cccccc",
        radius,
      });
    }
  }
  editor.canvas.requestRenderAll();
  editor.commit();
}
