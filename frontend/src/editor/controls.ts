/** Canva-style selection handles: round corners, pill sides, rotate knob below. */
import { Control, FabricImage, InteractiveFabricObject, controlsUtils, type FabricObject } from 'fabric'

export const ACCENT = '#FF6A13'

const HANDLE_STROKE = '#d7dbe0'
const SHADOW = 'rgba(15, 23, 32, 0.18)'

type RenderFn = Control['render']

const withShadow = (ctx: CanvasRenderingContext2D, draw: () => void) => {
  ctx.save()
  ctx.shadowColor = SHADOW
  ctx.shadowBlur = 4
  ctx.shadowOffsetY = 1
  draw()
  ctx.restore()
}

const renderCorner: RenderFn = (ctx, left, top) =>
  withShadow(ctx, () => {
    ctx.beginPath()
    ctx.arc(left, top, 7, 0, Math.PI * 2)
    ctx.fillStyle = '#fff'
    ctx.fill()
    ctx.lineWidth = 1
    ctx.strokeStyle = HANDLE_STROKE
    ctx.stroke()
  })

const pill = (vertical: boolean): RenderFn => (ctx, left, top, _style, obj) =>
  withShadow(ctx, () => {
    const [w, h] = vertical ? [6, 18] : [18, 6]
    ctx.translate(left, top)
    ctx.rotate(((obj.angle ?? 0) * Math.PI) / 180)
    ctx.beginPath()
    ctx.roundRect(-w / 2, -h / 2, w, h, 3)
    ctx.fillStyle = '#fff'
    ctx.fill()
    ctx.strokeStyle = HANDLE_STROKE
    ctx.stroke()
  })

const renderRotate: RenderFn = (ctx, left, top) =>
  withShadow(ctx, () => {
    ctx.beginPath()
    ctx.arc(left, top, 12, 0, Math.PI * 2)
    ctx.fillStyle = '#fff'
    ctx.fill()
    ctx.strokeStyle = HANDLE_STROKE
    ctx.stroke()
    // circular-arrow glyph
    ctx.shadowColor = 'transparent'
    ctx.beginPath()
    ctx.arc(left, top, 5, Math.PI * 0.15, Math.PI * 1.75)
    ctx.strokeStyle = '#3d4752'
    ctx.lineWidth = 1.6
    ctx.stroke()
    ctx.beginPath()
    ctx.moveTo(left + 5, top - 4.5)
    ctx.lineTo(left + 5.5, top + 0.5)
    ctx.lineTo(left + 1, top - 1.5)
    ctx.fillStyle = '#3d4752'
    ctx.fill()
  })

/** Global look for every object's selection box. */
export function installCanvaControls() {
  Object.assign(InteractiveFabricObject.ownDefaults, {
    borderColor: ACCENT,
    borderScaleFactor: 2,
    padding: 0,
    transparentCorners: false,
    cornerSize: 18,
    touchCornerSize: 28,
    snapAngle: 45, // rotation clicks to 0/45/90… when near, like Canva
    snapThreshold: 4,
  })
}

/** Per-object handle set. Images only scale from corners so they never distort. */
export function styleControls(obj: FabricObject) {
  const c = obj.controls
  for (const key of ['tl', 'tr', 'bl', 'br'] as const) if (c[key]) c[key].render = renderCorner
  for (const key of ['ml', 'mr'] as const) if (c[key]) c[key].render = pill(true)
  for (const key of ['mt', 'mb'] as const) if (c[key]) c[key].render = pill(false)
  if (c.mtr) {
    obj.controls = {
      ...c,
      mtr: new Control({
        x: 0,
        y: 0.5,
        offsetY: 36,
        sizeX: 26,
        sizeY: 26,
        withConnection: false,
        actionName: 'rotate',
        actionHandler: controlsUtils.rotationWithSnapping,
        cursorStyleHandler: controlsUtils.rotationStyleHandler,
        render: renderRotate,
      }),
    }
  }
  if (obj instanceof FabricImage) obj.setControlsVisibility({ ml: false, mr: false, mt: false, mb: false })
}
