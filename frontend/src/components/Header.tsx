import { Check, CloudOff, Download, Home, Loader2, Redo2, Undo2 } from 'lucide-react'
import type { Editor } from '../editor/Editor'
import { goHome } from '../designs'

interface Props {
  editor: Editor | null
  name: string
  onRename: (name: string) => void
  status: 'loading' | 'saved' | 'saving' | 'error'
}

const STATUS = {
  loading: { icon: <Loader2 size={14} className="spin" />, text: 'Opening…' },
  saving: { icon: <Loader2 size={14} className="spin" />, text: 'Saving…' },
  saved: { icon: <Check size={14} />, text: 'Saved' },
  error: { icon: <CloudOff size={14} />, text: 'Not saved' },
}

export function Header({ editor, name, onRename, status }: Props) {
  const download = () => {
    if (!editor) return
    const a = document.createElement('a')
    a.href = editor.exportPNG()
    a.download = `${name || 'design'}.png`
    a.click()
  }

  return (
    <header className="header">
      <button className="logo" onClick={goHome} title="All designs">makeIt</button>
      <button className="icon-btn light" title="All designs" onClick={goHome}>
        <Home size={18} />
      </button>
      <span className="divider" />
      <button className="icon-btn light" title="Undo (⌘Z)" disabled={!editor?.canUndo()} onClick={() => editor?.undo()}>
        <Undo2 size={18} />
      </button>
      <button className="icon-btn light" title="Redo (⇧⌘Z)" disabled={!editor?.canRedo()} onClick={() => editor?.redo()}>
        <Redo2 size={18} />
      </button>
      <span className="save-status">
        {STATUS[status].icon} {STATUS[status].text}
      </span>
      <input
        className="name-input"
        value={name}
        placeholder="Untitled design"
        aria-label="Design name"
        onChange={(e) => onRename(e.target.value)}
        onKeyDown={(e) => e.key === 'Enter' && e.currentTarget.blur()}
        onBlur={(e) => !e.target.value.trim() && onRename('Untitled design')}
      />
      <span className="dims">{editor?.width ?? 1080} × {editor?.height ?? 1080} px</span>
      <button className="share" onClick={download}>
        <Download size={16} /> Download
      </button>
    </header>
  )
}
