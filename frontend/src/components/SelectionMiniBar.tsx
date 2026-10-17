import { ArrowDown, ArrowUp, ArrowDownToLine, ArrowUpToLine, Trash2 } from 'lucide-react'
import type { FabricObject } from 'fabric'
import type { Editor } from '../editor/Editor'

const BAR_GAP = 14

/** Floating quick-actions pill above the selection, like Canva's. */
export function SelectionMiniBar({ editor, selected }: { editor: Editor; selected: FabricObject }) {
  const box = selected.getBoundingRect()
  const z = editor.zoom
  const left = (box.left + box.width / 2) * z
  const top = Math.max(box.top * z - BAR_GAP, 0)
  const id = selected.get('id') as string
  const order = (to: 'front' | 'back' | 'forward' | 'backward') => {
    editor.reorder(id, to)
    editor.commit()
  }

  return (
    <div className="minibar" style={{ left, top }} onMouseDown={(e) => e.stopPropagation()}>
      <button title="Bring forward" onClick={() => order('forward')}><ArrowUp size={16} /></button>
      <button title="Send backward" onClick={() => order('backward')}><ArrowDown size={16} /></button>
      <span className="sep" />
      <button title="Bring to front" onClick={() => order('front')}><ArrowUpToLine size={16} /></button>
      <button title="Send to back" onClick={() => order('back')}><ArrowDownToLine size={16} /></button>
      <span className="sep" />
      <button className="del" title="Delete (Del)" onClick={() => editor.deleteSelected()}><Trash2 size={16} /></button>
    </div>
  )
}
