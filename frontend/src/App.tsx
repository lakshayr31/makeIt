import { useCallback, useEffect, useRef, useState } from 'react'
import type { TPointerEventInfo } from 'fabric'
import { Editor } from './editor/Editor'
import { Header } from './components/Header'
import { ContextToolbar } from './components/ContextToolbar'
import { SelectionMiniBar } from './components/SelectionMiniBar'
import { LeftPanel } from './components/LeftPanel'
import { ZoomBar } from './components/ZoomBar'
import { ContextMenu } from './components/ContextMenu'
import type { FabricObject } from 'fabric'

const DESIGN_W = 1080
const DESIGN_H = 1080
const STAGE_PADDING = 96
const NUDGE = 1
const NUDGE_BIG = 10

/** Badge shown next to the pointer while rotating ("45°") or resizing ("540 × 320"). */
interface Badge {
  text: string
  x: number
  y: number
}

export function App() {
  const canvasEl = useRef<HTMLCanvasElement>(null)
  const stageRef = useRef<HTMLDivElement>(null)
  const [editor, setEditor] = useState<Editor | null>(null)
  const [, setTick] = useState(0)
  const [badge, setBadge] = useState<Badge | null>(null)
  const [transforming, setTransforming] = useState(false)
  const [menu, setMenu] = useState<{ x: number; y: number; target?: FabricObject } | null>(null)
  const closeMenu = useCallback(() => setMenu(null), [])

  const fitToScreen = useCallback((ed: Editor) => {
    const stage = stageRef.current
    if (!stage) return
    ed.fit(stage.clientWidth - STAGE_PADDING * 2, stage.clientHeight - STAGE_PADDING * 2)
  }, [])

  // Create the editor once.
  useEffect(() => {
    const ed = new Editor(canvasEl.current!, DESIGN_W, DESIGN_H)
    const rerender = () => setTick((t) => t + 1)
    const off = ed.onChange(rerender)

    const showBadge = (text: string, e: TPointerEventInfo['e']) => {
      const stage = stageRef.current!.getBoundingClientRect()
      const p = 'clientX' in e ? e : (e as TouchEvent).touches[0]
      setBadge({ text, x: p.clientX - stage.left + 16, y: p.clientY - stage.top + 16 })
      setTransforming(true)
    }
    ed.canvas.on('object:rotating', ({ target, e }) => showBadge(`${Math.round(((target.angle % 360) + 360) % 360)}°`, e))
    ed.canvas.on('object:scaling', ({ target, e }) =>
      showBadge(`w ${Math.round(target.getScaledWidth())}  h ${Math.round(target.getScaledHeight())}`, e),
    )
    ed.canvas.on('object:moving', () => setTransforming(true))
    ed.canvas.on('mouse:up', () => {
      setBadge(null)
      setTransforming(false)
    })

    setEditor(ed)
    const raf = requestAnimationFrame(() => fitToScreen(ed))
    return () => {
      cancelAnimationFrame(raf)
      off()
      ed.canvas.dispose()
    }
  }, [fitToScreen])

  // Right-click: select what's under the pointer, then open the menu.
  useEffect(() => {
    if (!editor) return
    const el = editor.canvas.upperCanvasEl
    const onContext = (e: MouseEvent) => {
      e.preventDefault()
      const target = editor.canvas.findTarget(e).target
      if (target) editor.canvas.setActiveObject(target)
      else editor.canvas.discardActiveObject()
      editor.canvas.requestRenderAll()
      setMenu({ x: e.clientX, y: e.clientY, target })
    }
    el.addEventListener('contextmenu', onContext)
    return () => el.removeEventListener('contextmenu', onContext)
  }, [editor])

  // Pinch / ctrl+scroll zooms, like Canva.
  useEffect(() => {
    const stage = stageRef.current
    if (!stage || !editor) return
    const onWheel = (e: WheelEvent) => {
      if (!e.ctrlKey && !e.metaKey) return
      e.preventDefault()
      editor.setZoom(editor.zoom * Math.exp(-e.deltaY * 0.01))
    }
    stage.addEventListener('wheel', onWheel, { passive: false })
    return () => stage.removeEventListener('wheel', onWheel)
  }, [editor])

  // Keyboard shortcuts.
  useEffect(() => {
    if (!editor) return
    const onKey = (e: KeyboardEvent) => {
      const typing = (e.target as HTMLElement).closest('input, textarea, [contenteditable]')
      if (typing) return
      const mod = e.metaKey || e.ctrlKey
      const sel = editor.selected()
      const id = sel?.get('id') as string | undefined
      const editingText = !!(sel as { isEditing?: boolean } | undefined)?.isEditing
      const key = e.key.toLowerCase()

      if (mod && !editingText && key === 'c' && sel) {
        e.preventDefault()
        editor.copySelected()
      } else if (mod && !editingText && key === 'v') {
        e.preventDefault()
        editor.paste()
      } else if (mod && key === 'd' && sel) {
        e.preventDefault()
        editor.duplicateSelected()
      } else if (e.altKey && e.shiftKey && e.code === 'KeyL' && id) {
        e.preventDefault()
        editor.toggleLock(id)
      } else if (mod && e.key.toLowerCase() === 'z') {
        e.preventDefault()
        if (e.shiftKey) editor.redo()
        else editor.undo()
      } else if (mod && e.key.toLowerCase() === 'y') {
        e.preventDefault()
        editor.redo()
      } else if (mod && (e.key === '=' || e.key === '+')) {
        e.preventDefault()
        editor.setZoom(editor.zoom * 1.2)
      } else if (mod && e.key === '-') {
        e.preventDefault()
        editor.setZoom(editor.zoom / 1.2)
      } else if (mod && e.key === '0') {
        e.preventDefault()
        fitToScreen(editor)
      } else if (mod && id && (e.key === ']' || e.key === '[')) {
        e.preventDefault()
        const up = e.key === ']'
        editor.reorder(id, e.altKey ? (up ? 'front' : 'back') : up ? 'forward' : 'backward')
        editor.commit()
      } else if (sel && (e.key === 'Delete' || e.key === 'Backspace') && !(sel as { isEditing?: boolean }).isEditing) {
        e.preventDefault()
        editor.deleteSelected()
      } else if (id && e.key.startsWith('Arrow')) {
        e.preventDefault()
        const step = e.shiftKey ? NUDGE_BIG : NUDGE
        const s = editor.summary().elements.find((el) => el.id === id)!
        const dx = e.key === 'ArrowLeft' ? -step : e.key === 'ArrowRight' ? step : 0
        const dy = e.key === 'ArrowUp' ? -step : e.key === 'ArrowDown' ? step : 0
        editor.update(id, { x: s.x + dx, y: s.y + dy })
        editor.canvas.requestRenderAll()
        editor.commit()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [editor, fitToScreen])

  const selected = editor?.selected()

  return (
    <div className="app">
      <Header editor={editor} />
      <div className="body">
        <LeftPanel editor={editor} onFit={() => editor && fitToScreen(editor)} />
        {editor && menu && <ContextMenu editor={editor} x={menu.x} y={menu.y} target={menu.target} onClose={closeMenu} />}
        <main className="workspace">
          <ContextToolbar editor={editor} selected={selected} />
          <div className="stage" ref={stageRef} onMouseDown={(e) => e.target === e.currentTarget && editor?.canvas.discardActiveObject() && editor.canvas.requestRenderAll()}>
            <div className="page">
              <canvas ref={canvasEl} />
              {editor && selected && !transforming && <SelectionMiniBar editor={editor} selected={selected} />}
            </div>
            {badge && (
              <div className="badge" style={{ left: badge.x, top: badge.y }}>
                {badge.text}
              </div>
            )}
          </div>
          <ZoomBar editor={editor} onFit={() => editor && fitToScreen(editor)} />
        </main>
      </div>
    </div>
  )
}
