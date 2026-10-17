import { useEffect, useRef, useState } from 'react'
import { ArrowDown, ArrowDownToLine, ArrowUp, ArrowUpToLine, ChevronDown } from 'lucide-react'
import type { FabricObject } from 'fabric'
import type { Editor } from '../editor/Editor'

type Order = 'front' | 'back' | 'forward' | 'backward'

const LAYER_ACTIONS: { to: Order; label: string; keys: string; Icon: typeof ArrowUp }[] = [
  { to: 'forward', label: 'Bring forward', keys: '⌘]', Icon: ArrowUp },
  { to: 'front', label: 'Bring to front', keys: '⌥⌘]', Icon: ArrowUpToLine },
  { to: 'backward', label: 'Send backward', keys: '⌘[', Icon: ArrowDown },
  { to: 'back', label: 'Send to back', keys: '⌥⌘[', Icon: ArrowDownToLine },
]

const KIND: Record<string, string> = { image: 'Image', textbox: 'Text', rect: 'Shape', circle: 'Shape' }

export function ContextToolbar({ editor, selected }: { editor: Editor | null; selected?: FabricObject }) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const close = (e: MouseEvent) => !ref.current?.contains(e.target as Node) && setOpen(false)
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [])

  if (!editor || !selected) {
    return (
      <div className="ctx-toolbar empty">
        <span className="muted">Select an element to move, resize, rotate or layer it</span>
      </div>
    )
  }

  const id = selected.get('id') as string
  const angle = Math.round(((selected.angle % 360) + 360) % 360)
  const order = (to: Order) => {
    editor.reorder(id, to)
    editor.commit()
  }
  const straighten = () => {
    selected.rotate(0)
    selected.setCoords()
    editor.canvas.requestRenderAll()
    editor.commit()
  }

  return (
    <div className="ctx-toolbar">
      <span className="chip">{KIND[selected.type.toLowerCase()] ?? 'Element'}</span>
      <span className="sep" />
      <span className="stat">W {Math.round(selected.getScaledWidth())}</span>
      <span className="stat">H {Math.round(selected.getScaledHeight())}</span>
      <button className="tb-btn" title="Reset rotation" onClick={straighten} disabled={angle === 0}>
        ↻ {angle}°
      </button>
      <span className="sep" />
      <div className="popover-wrap" ref={ref}>
        <button className={`tb-btn ${open ? 'on' : ''}`} onClick={() => setOpen((o) => !o)}>
          Position <ChevronDown size={14} />
        </button>
        {open && (
          <div className="popover">
            <div className="pop-title">Layer order</div>
            {LAYER_ACTIONS.map(({ to, label, keys, Icon }) => (
              <button key={to} className="pop-item" onClick={() => order(to)}>
                <Icon size={16} /> <span>{label}</span> <kbd>{keys}</kbd>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
