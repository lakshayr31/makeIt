/**
 * Command layer over Fabric.js. UI buttons and the AI copilot both go through
 * these methods, so anything one can do the other can, and every change is one
 * undo step. Coordinates are design pixels, top-left based.
 */
import {
  Canvas,
  Circle,
  FabricImage,
  FabricObject,
  Point,
  Rect,
  Textbox,
} from "fabric";
import { installCanvaControls, styleControls } from "./controls";
import type { CanvasSummary, ElementProps, ElementSummary, Op } from "./types";

FabricObject.customProperties = ["id", "name", "src"];
installCanvaControls();

const HISTORY_LIMIT = 60;
const DEFAULT_FONT = "Inter";
export const MIN_ZOOM = 0.1;
export const MAX_ZOOM = 4;

type Listener = () => void;
export type ImageGenerator = (
  prompt: string,
  transparent: boolean,
  width: number,
  height: number,
) => Promise<string>;

let idCounter = 0;
const newId = (prefix: string) =>
  `${prefix}-${Date.now().toString(36)}${(idCounter++).toString(36)}`;

export class Editor {
  readonly canvas: Canvas;
  width: number;
  height: number;
  private history: string[] = [];
  private future: string[] = [];
  private listeners = new Set<Listener>();
  private restoring = false;

  constructor(el: HTMLCanvasElement, width: number, height: number) {
    this.width = width;
    this.height = height;
    this.canvas = new Canvas(el, {
      backgroundColor: "#ffffff",
      preserveObjectStacking: true,
    });
    const notify = () => this.emit();
    for (const evt of [
      "object:added",
      "object:removed",
      "selection:created",
      "selection:updated",
      "selection:cleared",
    ] as const) {
      this.canvas.on(evt, notify);
    }
    this.canvas.on("object:modified", () => this.commit());
    this.canvas.on("text:changed", notify);
    this.setZoom(1);
    this.commit();
  }

  // ---- view -------------------------------------------------------------

  get zoom() {
    return this.canvas.getZoom();
  }

  /** Zoom the whole page; the canvas element grows/shrinks with it. */
  setZoom(zoom: number) {
    const z = Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, zoom));
    this.canvas.setDimensions({
      width: Math.round(this.width * z),
      height: Math.round(this.height * z),
    });
    this.canvas.setZoom(z);
    this.canvas.requestRenderAll();
    this.emit();
  }

  /** Scale the design to fit the given screen box. */
  fit(maxW: number, maxH: number) {
    this.setZoom(Math.min(maxW / this.width, maxH / this.height));
  }

  resizeDesign(width: number, height: number, maxW: number, maxH: number) {
    this.width = width;
    this.height = height;
    this.fit(maxW, maxH);
    this.commit();
  }

  onChange(fn: Listener) {
    this.listeners.add(fn);
    return () => this.listeners.delete(fn);
  }

  private emit() {
    this.listeners.forEach((fn) => fn());
  }

  // ---- lookups ------------------------------------------------------------

  find(id: string): FabricObject | undefined {
    return this.canvas.getObjects().find((o) => o.get("id") === id);
  }

  selected(): FabricObject | undefined {
    return this.canvas.getActiveObject() ?? undefined;
  }

  select(id: string) {
    const obj = this.find(id);
    if (!obj) return;
    this.canvas.setActiveObject(obj);
    this.canvas.requestRenderAll();
    this.emit();
  }

  // ---- commands -------------------------------------------------------------

  addText(o: Extract<Op, { op: "add_text" }>) {
    const box = new Textbox(o.text, {
      width: o.width ?? Math.min(800, this.width - 120),
      fontSize: o.fontSize ?? 64,
      fontFamily: o.fontFamily ?? DEFAULT_FONT,
      fontWeight: o.fontWeight ?? "normal",
      fill: o.fill ?? "#111111",
      textAlign: o.textAlign ?? "left",
      lineHeight: 1.1,
      splitByGrapheme: false,
    });
    this.place(box, o.id ?? newId("text"), o.text.slice(0, 24), o.x, o.y);
    return box;
  }

  async addImage(o: {
    id?: string;
    src: string;
    x: number;
    y: number;
    width: number;
    height: number;
    name?: string;
  }) {
    const img = await FabricImage.fromURL(o.src, { crossOrigin: "anonymous" });
    // Contain-fit inside the requested box, centred, so brand assets never distort.
    const scale = Math.min(
      o.width / (img.width || 1),
      o.height / (img.height || 1),
    );
    img.set({ scaleX: scale, scaleY: scale });
    const x = o.x + (o.width - img.getScaledWidth()) / 2;
    const y = o.y + (o.height - img.getScaledHeight()) / 2;
    img.set("src", o.src);
    this.place(
      img,
      o.id ?? newId("image"),
      o.name ?? o.src.split("/").pop()!.slice(0, 24),
      x,
      y,
    );
    return img;
  }

  /** Add a rectangular crop of a larger image (e.g. the photo region of a reference ad). */
  async addCroppedImage(o: {
    id?: string;
    src: string;
    crop: { x: number; y: number; width: number; height: number };
    x: number;
    y: number;
    width: number;
    height: number;
    name?: string;
  }) {
    const img = await FabricImage.fromURL(o.src, { crossOrigin: "anonymous" });
    img.set({
      cropX: o.crop.x,
      cropY: o.crop.y,
      width: o.crop.width,
      height: o.crop.height,
    });
    img.set({
      scaleX: o.width / o.crop.width,
      scaleY: o.height / o.crop.height,
      src: o.src,
    });
    this.place(
      img,
      o.id ?? newId("image"),
      o.name ?? "cropped image",
      o.x,
      o.y,
    );
    return img;
  }

  /** Wipe the page and set a new size, without adding an undo step. */
  reset(width: number, height: number, background = "#ffffff") {
    this.canvas.discardActiveObject();
    this.canvas.remove(...this.canvas.getObjects());
    this.canvas.backgroundColor = background;
    this.width = width;
    this.height = height;
    this.setZoom(this.zoom);
  }

  addShape(o: Extract<Op, { op: "add_shape" }>) {
    const fill = o.fill ?? "#13B5EA";
    const shape =
      o.shape === "circle"
        ? new Circle({ radius: Math.min(o.width, o.height) / 2, fill })
        : new Rect({
            width: o.width,
            height: o.height,
            rx: o.radius ?? 0,
            ry: o.radius ?? 0,
            fill,
          });
    this.place(shape, o.id ?? newId(o.shape), o.shape, o.x, o.y);
    return shape;
  }

  update(id: string, props: Partial<ElementProps>) {
    const obj = this.find(id);
    if (!obj) return;
    const { x, y, width, height, ...style } = props;
    if ("text" in style && obj instanceof Textbox) obj.set("text", style.text);
    for (const key of [
      "fill",
      "fontSize",
      "fontFamily",
      "fontWeight",
      "textAlign",
      "opacity",
    ] as const) {
      if (style[key] !== undefined) obj.set(key, style[key]);
    }
    if (width !== undefined || height !== undefined)
      this.setSize(obj, width, height);
    if (x !== undefined || y !== undefined) {
      const tl = obj.getPointByOrigin("left", "top");
      obj.setPositionByOrigin(new Point(x ?? tl.x, y ?? tl.y), "left", "top");
    }
    obj.setCoords();
  }

  remove(id: string) {
    const obj = this.find(id);
    if (obj) this.canvas.remove(obj);
  }

  reorder(id: string, to: "front" | "back" | "forward" | "backward") {
    const obj = this.find(id);
    if (!obj) return;
    if (to === "front") this.canvas.bringObjectToFront(obj);
    else if (to === "back") this.canvas.sendObjectToBack(obj);
    else if (to === "forward") this.canvas.bringObjectForward(obj);
    else this.canvas.sendObjectBackwards(obj);
  }

  setBackground(color: string) {
    this.canvas.backgroundColor = color;
  }

  toggleVisible(id: string) {
    const obj = this.find(id);
    if (!obj) return;
    obj.visible = !obj.visible;
    this.commit();
  }

  toggleLock(id: string) {
    const obj = this.find(id);
    if (!obj) return;
    const locked = !obj.get("lockMovementX");
    obj.set({
      lockMovementX: locked,
      lockMovementY: locked,
      lockScalingX: locked,
      lockScalingY: locked,
      lockRotation: locked,
      hasControls: !locked,
    });
    this.commit();
  }

  deleteSelected() {
    const objs = this.canvas.getActiveObjects();
    if (!objs.length) return;
    this.canvas.discardActiveObject();
    objs.forEach((o) => this.canvas.remove(o));
    this.commit();
  }

  /**
   * Apply a batch of ops as ONE undo step. Generated images appear as
   * placeholders immediately and swap in as each finishes (in parallel).
   */
  async applyOps(
    ops: Op[],
    generate: ImageGenerator,
    onError: (msg: string) => void = () => {},
  ) {
    const pending: Promise<void>[] = [];
    for (const op of ops) {
      try {
        if (op.op === "add_text") this.addText(op);
        else if (op.op === "add_shape") this.addShape(op);
        else if (op.op === "update") this.update(op.id, op.props ?? {});
        else if (op.op === "delete") this.remove(op.id);
        else if (op.op === "reorder") this.reorder(op.id, op.to);
        else if (op.op === "set_background") this.setBackground(op.color);
        else if (op.op === "add_image" && op.src)
          await this.addImage({ ...op, src: op.src });
        else if (op.op === "add_image" && op.prompt)
          pending.push(this.generateInto(op, generate));
      } catch (err) {
        onError(
          `${op.op} failed: ${err instanceof Error ? err.message : String(err)}`,
        );
      }
    }
    this.canvas.requestRenderAll();
    this.commit();
    await Promise.all(
      pending.map((p) => p.catch((err) => onError(String(err)))),
    );
  }

  private async generateInto(
    op: Extract<Op, { op: "add_image" }>,
    generate: ImageGenerator,
  ) {
    const id = op.id ?? newId("gen");
    const placeholder = new Rect({
      width: op.width,
      height: op.height,
      fill: "#e5e7eb",
      strokeDashArray: [12, 8],
      stroke: "#9ca3af",
      strokeWidth: 2,
    });
    this.place(
      placeholder,
      id,
      `Generating: ${op.prompt!.slice(0, 18)}…`,
      op.x,
      op.y,
    );
    const src = await generate(
      op.prompt!,
      !!op.transparent,
      op.width,
      op.height,
    );
    const index = this.canvas.getObjects().indexOf(placeholder);
    const img = await this.addImage({
      id: id + "-img",
      src,
      x: op.x,
      y: op.y,
      width: op.width,
      height: op.height,
      name: op.prompt!.slice(0, 24),
    });
    this.canvas.remove(placeholder);
    img.set("id", id);
    if (index >= 0) this.canvas.moveObjectTo(img, index);
    this.canvas.requestRenderAll();
    this.commit();
  }

  // ---- read model for agent + panels -----------------------------------------

  summary(): CanvasSummary {
    return {
      width: this.width,
      height: this.height,
      background: String(this.canvas.backgroundColor || "#ffffff"),
      elements: this.canvas.getObjects().map((o) => this.summarize(o)),
    };
  }

  private summarize(o: FabricObject): ElementSummary {
    const tl = o.getPointByOrigin("left", "top");
    const base = {
      id: String(o.get("id")),
      name: String(o.get("name") ?? ""),
      x: Math.round(tl.x),
      y: Math.round(tl.y),
      width: Math.round(o.getScaledWidth()),
      height: Math.round(o.getScaledHeight()),
      visible: o.visible !== false,
      locked: !!o.get("lockMovementX"),
    };
    if (o instanceof Textbox)
      return {
        ...base,
        type: "text",
        text: o.text,
        fill: String(o.fill),
        fontSize: o.fontSize,
        fontWeight: String(o.fontWeight),
      };
    if (o instanceof FabricImage)
      return { ...base, type: "image", src: String(o.get("src") ?? "") };
    if (o instanceof Circle)
      return { ...base, type: "circle", fill: String(o.fill) };
    if (o instanceof Rect)
      return { ...base, type: "rect", fill: String(o.fill) };
    return { ...base, type: "other" };
  }

  // ---- history / persistence ------------------------------------------------

  /** Snapshot current state as an undo step. */
  commit() {
    if (this.restoring) return;
    const snap = JSON.stringify({
      w: this.width,
      h: this.height,
      canvas: this.canvas.toObject([
        "id",
        "name",
        "src",
        "lockMovementX",
        "lockMovementY",
        "lockScalingX",
        "lockScalingY",
        "lockRotation",
        "hasControls",
      ]),
    });
    if (snap === this.history.at(-1)) return;
    this.history.push(snap);
    if (this.history.length > HISTORY_LIMIT) this.history.shift();
    this.future = [];
    this.emit();
  }

  canUndo() {
    return this.history.length > 1;
  }
  canRedo() {
    return this.future.length > 0;
  }

  async undo() {
    if (!this.canUndo()) return;
    this.future.push(this.history.pop()!);
    await this.restore(this.history.at(-1)!);
  }

  async redo() {
    const next = this.future.pop();
    if (!next) return;
    this.history.push(next);
    await this.restore(next);
  }

  private async restore(snap: string) {
    this.restoring = true;
    const { w, h, canvas } = JSON.parse(snap);
    this.width = w;
    this.height = h;
    const zoom = this.zoom;
    await this.canvas.loadFromJSON(canvas);
    this.canvas.getObjects().forEach(styleControls);
    this.setZoom(zoom);
    this.restoring = false;
    this.emit();
  }

  exportPNG(): string {
    this.canvas.discardActiveObject();
    this.canvas.requestRenderAll();
    return this.canvas.toDataURL({
      format: "png",
      multiplier: 1 / this.canvas.getZoom(),
    });
  }

  // ---- internals ------------------------------------------------------------

  private place(
    obj: FabricObject,
    id: string,
    name: string,
    x: number,
    y: number,
  ) {
    const unique = this.find(id) ? newId(id) : id;
    obj.set({ id: unique, name });
    obj.setPositionByOrigin(new Point(x, y), "left", "top");
    obj.setCoords();
    styleControls(obj);
    this.canvas.add(obj);
  }

  private setSize(obj: FabricObject, width?: number, height?: number) {
    const tl = obj.getPointByOrigin("left", "top");
    if (obj instanceof Textbox) {
      if (width) obj.set("width", width);
    } else if (obj instanceof Rect) {
      obj.set({
        width: width ?? obj.width,
        height: height ?? obj.height,
        scaleX: 1,
        scaleY: 1,
      });
    } else if (obj instanceof Circle) {
      obj.set({
        radius: Math.min(width ?? obj.radius * 2, height ?? obj.radius * 2) / 2,
        scaleX: 1,
        scaleY: 1,
      });
    } else {
      const scale = Math.min(
        (width ?? obj.getScaledWidth()) / obj.width,
        (height ?? obj.getScaledHeight()) / obj.height,
      );
      obj.set({ scaleX: scale, scaleY: scale });
    }
    obj.setPositionByOrigin(tl, "left", "top");
  }
}
