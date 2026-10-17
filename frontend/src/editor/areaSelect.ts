// Drag-a-rectangle mode for "Select area & ask…". The marquee is a DOM overlay,
// not a Fabric object, so it can never end up in undo history or a saved design.
import type { Editor } from "./Editor";
import type { Box } from "../agent";

const MIN_SIDE = 8; // design px; smaller drags count as a click → cancel

/**
 * Let the user drag a box anywhere in the workspace, even starting or ending outside the page.
 * Calls onDone(the part of the box inside the page, in design px), or onDone(null) on Esc,
 * a tiny drag, or a box that misses the page. Returns a cancel fn.
 */
export function startAreaSelect(
  editor: Editor,
  onDone: (box: Box | null) => void,
): () => void {
  const c = editor.canvas;
  const workspace = c.wrapperEl.closest(".workspace") ?? document.body;
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
  const prevCursor = (workspace as HTMLElement).style.cursor;
  (workspace as HTMLElement).style.cursor = "crosshair";

  // Fixed-position overlay in screen px, so the marquee can extend past the page.
  const overlay = document.createElement("div");
  overlay.className = "area-marquee";
  overlay.style.position = "fixed";
  overlay.style.display = "none";
  document.body.appendChild(overlay);

  let start: { cx: number; cy: number } | null = null;
  let box: Box | null = null;
  let finished = false;

  /** Screen rect → the part of it on the page, in design px. */
  const toPageBox = (x1: number, y1: number, x2: number, y2: number): Box | null => {
    const a = c.getScenePoint(new MouseEvent("mousemove", { clientX: Math.min(x1, x2), clientY: Math.min(y1, y2) }));
    const b = c.getScenePoint(new MouseEvent("mousemove", { clientX: Math.max(x1, x2), clientY: Math.max(y1, y2) }));
    const left = Math.max(0, a.x);
    const top = Math.max(0, a.y);
    const right = Math.min(editor.width, b.x);
    const bottom = Math.min(editor.height, b.y);
    if (right <= left || bottom <= top) return null;
    return [Math.round(left), Math.round(top), Math.round(right - left), Math.round(bottom - top)];
  };

  const onDown = (e: PointerEvent) => {
    if (e.button !== 0 || !workspace.contains(e.target as Node)) return;
    if ((e.target as HTMLElement).closest("button, input, textarea, .zoombar, .page-header")) return;
    e.preventDefault();
    e.stopPropagation();
    start = { cx: e.clientX, cy: e.clientY };
  };
  const onMove = (e: PointerEvent) => {
    if (!start) return;
    Object.assign(overlay.style, {
      display: "block",
      left: `${Math.min(start.cx, e.clientX)}px`,
      top: `${Math.min(start.cy, e.clientY)}px`,
      width: `${Math.abs(e.clientX - start.cx)}px`,
      height: `${Math.abs(e.clientY - start.cy)}px`,
    });
    box = toPageBox(start.cx, start.cy, e.clientX, e.clientY);
  };
  const onUp = (e: PointerEvent) => {
    if (!start) return;
    e.stopPropagation();
    finish(box && box[2] >= MIN_SIDE && box[3] >= MIN_SIDE ? box : null);
  };
  const onKey = (e: KeyboardEvent) => e.key === "Escape" && finish(null);

  // Capture phase: we get the drag before Fabric or the stage handlers do.
  window.addEventListener("pointerdown", onDown, true);
  window.addEventListener("pointermove", onMove, true);
  window.addEventListener("pointerup", onUp, true);
  window.addEventListener("keydown", onKey);

  function cleanup() {
    window.removeEventListener("pointerdown", onDown, true);
    window.removeEventListener("pointermove", onMove, true);
    window.removeEventListener("pointerup", onUp, true);
    window.removeEventListener("keydown", onKey);
    overlay.remove();
    (workspace as HTMLElement).style.cursor = prevCursor;
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
