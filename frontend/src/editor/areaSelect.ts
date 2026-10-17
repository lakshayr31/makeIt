// Drag-a-rectangle mode for "Select area & ask…". The marquee is a DOM overlay,
// not a Fabric object, so it can never end up in undo history or a saved design.
import { util, type TPointerEventInfo } from "fabric";
import type { Editor } from "./Editor";
import type { Box } from "../agent";

const MIN_SIDE = 8; // design px; smaller drags count as a click → cancel

/** Let the user drag a box on the canvas. Calls onDone(box in design px) or onDone(null) on Esc / tiny drag. Returns a cancel fn. */
export function startAreaSelect(
  editor: Editor,
  onDone: (box: Box | null) => void,
): () => void {
  const c = editor.canvas;
  const saved = {
    selection: c.selection,
    skipTargetFind: c.skipTargetFind,
    defaultCursor: c.defaultCursor,
    hoverCursor: c.hoverCursor,
  };
  c.discardActiveObject();
  c.selection = false;
  c.skipTargetFind = true;
  c.defaultCursor = c.hoverCursor = "crosshair";
  c.setCursor("crosshair");
  c.requestRenderAll();

  const overlay = document.createElement("div");
  overlay.className = "area-marquee";
  overlay.style.display = "none";
  c.wrapperEl.appendChild(overlay);

  let start: { x: number; y: number } | null = null;
  let box: Box | null = null;
  let finished = false;

  const draw = (b: Box) => {
    const tl = util.transformPoint(
      { x: b[0], y: b[1] },
      c.viewportTransform,
    );
    const z = c.getZoom();
    Object.assign(overlay.style, {
      display: "block",
      left: `${tl.x}px`,
      top: `${tl.y}px`,
      width: `${b[2] * z}px`,
      height: `${b[3] * z}px`,
    });
  };

  const onDown = (e: TPointerEventInfo) => {
    const p = c.getScenePoint(e.e);
    start = { x: p.x, y: p.y };
  };
  const onMove = (e: TPointerEventInfo) => {
    if (!start) return;
    const p = c.getScenePoint(e.e);
    const x = Math.max(0, Math.min(start.x, p.x));
    const y = Math.max(0, Math.min(start.y, p.y));
    const x2 = Math.min(editor.width, Math.max(start.x, p.x));
    const y2 = Math.min(editor.height, Math.max(start.y, p.y));
    box = [
      Math.round(x),
      Math.round(y),
      Math.round(x2 - x),
      Math.round(y2 - y),
    ];
    draw(box);
  };
  const onUp = () => {
    if (!start) return;
    finish(box && box[2] >= MIN_SIDE && box[3] >= MIN_SIDE ? box : null);
  };
  const onKey = (e: KeyboardEvent) => e.key === "Escape" && finish(null);

  c.on("mouse:down", onDown);
  c.on("mouse:move", onMove);
  c.on("mouse:up", onUp);
  window.addEventListener("keydown", onKey);

  function cleanup() {
    c.off("mouse:down", onDown);
    c.off("mouse:move", onMove);
    c.off("mouse:up", onUp);
    window.removeEventListener("keydown", onKey);
    overlay.remove();
    Object.assign(c, saved);
    c.setCursor(saved.defaultCursor ?? "default");
    c.requestRenderAll();
  }
  function finish(result: Box | null) {
    if (finished) return;
    finished = true;
    cleanup();
    onDone(result);
  }
  return () => finish(null);
}

/** Ids of visible elements whose bounds intersect the box, topmost first. */
export function touchingIds(editor: Editor, box: Box): string[] {
  const [bx, by, bw, bh] = box;
  return editor.canvas
    .getObjects()
    .filter((o) => {
      if (o.visible === false || !o.get("id")) return false;
      const r = o.getBoundingRect(); // scene coords in Fabric 7
      return (
        r.left < bx + bw &&
        r.left + r.width > bx &&
        r.top < by + bh &&
        r.top + r.height > by
      );
    })
    .reverse()
    .map((o) => String(o.get("id")));
}
