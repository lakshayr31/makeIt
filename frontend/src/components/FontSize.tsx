import { useEffect, useState } from 'react'
import { Minus, Plus } from 'lucide-react'
import type { Editor } from '../editor/Editor'

const MIN = 6
const MAX = 800

/** Canva-style "− 78 +" font size stepper; type a number or step by 1. */
export function FontSize({ editor, id, value }: { editor: Editor; id: string; value: number }) {
  const [draft, setDraft] = useState(String(Math.round(value)))
  useEffect(() => setDraft(String(Math.round(value))), [value])

  const apply = (size: number) => {
    if (!Number.isFinite(size)) return setDraft(String(Math.round(value)))
    const clamped = Math.min(MAX, Math.max(MIN, Math.round(size)))
    editor.update(id, { fontSize: clamped })
    editor.canvas.requestRenderAll()
    editor.commit()
    setDraft(String(clamped))
  }

  return (
    <div className="fontsize" title="Font size">
      <button onClick={() => apply(value - 1)}><Minus size={14} /></button>
      <input
        value={draft}
        inputMode="numeric"
        onChange={(e) => setDraft(e.target.value.replace(/[^0-9]/g, ''))}
        onBlur={() => apply(Number(draft))}
        onKeyDown={(e) => e.key === 'Enter' && (e.currentTarget as HTMLInputElement).blur()}
      />
      <button onClick={() => apply(value + 1)}><Plus size={14} /></button>
    </div>
  )
}
