import { Download, Redo2, Undo2 } from 'lucide-react'
import type { Editor } from '../editor/Editor'

export function Header({ editor }: { editor: Editor | null }) {
  const download = () => {
    if (!editor) return
    const a = document.createElement('a')
    a.href = editor.exportPNG()
    a.download = 'makeit-design.png'
    a.click()
  }

  return (
    <header className="header">
      <div className="logo">makeIt</div>
      <span className="divider" />
      <button className="icon-btn light" title="Undo (⌘Z)" disabled={!editor?.canUndo()} onClick={() => editor?.undo()}>
        <Undo2 size={18} />
      </button>
      <button className="icon-btn light" title="Redo (⇧⌘Z)" disabled={!editor?.canRedo()} onClick={() => editor?.redo()}>
        <Redo2 size={18} />
      </button>
      <span className="title">Untitled design · {editor?.width ?? 1080} × {editor?.height ?? 1080} px</span>
      <button className="share" onClick={download}>
        <Download size={16} /> Download
      </button>
    </header>
  )
}
