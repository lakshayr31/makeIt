import { Maximize, Minus, Plus } from 'lucide-react'
import { MAX_ZOOM, MIN_ZOOM, type Editor } from '../editor/Editor'

export function ZoomBar({ editor, onFit }: { editor: Editor | null; onFit: () => void }) {
  const zoom = editor?.zoom ?? 1
  return (
    <div className="zoombar">
      <button className="icon-btn" title="Zoom out (⌘−)" onClick={() => editor?.setZoom(zoom / 1.2)}><Minus size={16} /></button>
      <input
        type="range"
        min={MIN_ZOOM * 100}
        max={MAX_ZOOM * 100}
        value={Math.round(zoom * 100)}
        onChange={(e) => editor?.setZoom(Number(e.target.value) / 100)}
      />
      <button className="icon-btn" title="Zoom in (⌘+)" onClick={() => editor?.setZoom(zoom * 1.2)}><Plus size={16} /></button>
      <span className="zoom-pct">{Math.round(zoom * 100)}%</span>
      <button className="fit" title="Fit to screen (⌘0)" onClick={onFit}><Maximize size={14} /> Fit</button>
    </div>
  )
}
