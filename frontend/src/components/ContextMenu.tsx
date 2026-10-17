import { useEffect, useRef, type ReactNode } from 'react'
import {
  AlignCenterHorizontal,
  AlignCenterVertical,
  AlignEndHorizontal,
  AlignEndVertical,
  AlignStartHorizontal,
  AlignStartVertical,
  ArrowDown,
  ArrowDownToLine,
  ArrowUp,
  ArrowUpToLine,
  ChevronRight,
  Clipboard,
  Copy,
  CopyPlus,
  Download,
  Layers,
  Lock,
  LockOpen,
  Trash2,
  Wallpaper,
  Shapes,
  AlignLeft,
  Sparkles,
  SquareDashedMousePointer,
} from 'lucide-react'
import { FabricImage, type FabricObject } from 'fabric'
import type { Editor } from '../editor/Editor'

interface Props {
  editor: Editor
  x: number
  y: number
  target?: FabricObject
  onClose: () => void
  onAsk?: (id: string | null) => void
  onSelectArea?: () => void
}

const MENU_WIDTH = 290
const MENU_MAX_HEIGHT = 520

/** Canva-style right-click menu, limited to what the editor supports today. */
export function ContextMenu({ editor, x, y, target, onClose, onAsk, onSelectArea }: Props) {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const onDown = (e: MouseEvent) => !ref.current?.contains(e.target as Node) && onClose()
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    window.addEventListener('resize', onClose)
    return () => {
      document.removeEventListener('mousedown', onDown)
      document.removeEventListener('keydown', onKey)
      window.removeEventListener('resize', onClose)
    }
  }, [onClose])

  // Keep the menu on screen.
  const left = Math.min(x, window.innerWidth - MENU_WIDTH - 8)
  const top = Math.min(y, window.innerHeight - MENU_MAX_HEIGHT - 8)
  const run = (fn: () => unknown) => () => {
    fn()
    onClose()
  }

  const id = target?.get('id') as string | undefined
  const locked = id ? editor.isLocked(id) : false

  const download = () => {
    const url = id && editor.exportElement(id)
    if (!url) return
    const a = document.createElement('a')
    a.href = url
    a.download = `${id}.png`
    a.click()
  }

  return (
    <div className="ctxmenu" ref={ref} style={{ left: Math.max(8, left), top: Math.max(8, top) }} onContextMenu={(e) => e.preventDefault()}>
      {onAsk && target && id && <Item icon={<Sparkles size={18} />} label="Ask makeIt about this" onClick={run(() => onAsk(id))} />}
      {onSelectArea && <Item icon={<SquareDashedMousePointer size={18} />} label="Select area & ask…" onClick={run(onSelectArea)} />}
      {((onAsk && target && id) || onSelectArea) && <hr />}
      {target && id ? (
        <>
          <Item icon={<Copy size={18} />} label="Copy" keys="⌘C" onClick={run(() => editor.copySelected())} />
          <Item icon={<Clipboard size={18} />} label="Paste" keys="⌘V" disabled={!editor.canPaste()} onClick={run(() => editor.paste())} />
          <Item icon={<CopyPlus size={18} />} label="Duplicate" keys="⌘D" onClick={run(() => editor.duplicateSelected())} />
          <Item icon={<Trash2 size={18} />} label="Delete" keys="DELETE" onClick={run(() => editor.deleteSelected())} />
          <hr />
          <Sub icon={<Layers size={18} />} label="Layer">
            <Item icon={<ArrowUp size={16} />} label="Bring forward" keys="⌘]" onClick={run(() => { editor.reorder(id, 'forward'); editor.commit() })} />
            <Item icon={<ArrowUpToLine size={16} />} label="Bring to front" keys="⌥⌘]" onClick={run(() => { editor.reorder(id, 'front'); editor.commit() })} />
            <Item icon={<ArrowDown size={16} />} label="Send backward" keys="⌘[" onClick={run(() => { editor.reorder(id, 'backward'); editor.commit() })} />
            <Item icon={<ArrowDownToLine size={16} />} label="Send to back" keys="⌥⌘[" onClick={run(() => { editor.reorder(id, 'back'); editor.commit() })} />
          </Sub>
          <Sub icon={<AlignLeft size={18} />} label="Align to page">
            <Item icon={<AlignStartVertical size={16} />} label="Left" onClick={run(() => editor.alignToPage(id, 'left'))} />
            <Item icon={<AlignCenterVertical size={16} />} label="Center" onClick={run(() => editor.alignToPage(id, 'center'))} />
            <Item icon={<AlignEndVertical size={16} />} label="Right" onClick={run(() => editor.alignToPage(id, 'right'))} />
            <Item icon={<AlignStartHorizontal size={16} />} label="Top" onClick={run(() => editor.alignToPage(id, 'top'))} />
            <Item icon={<AlignCenterHorizontal size={16} />} label="Middle" onClick={run(() => editor.alignToPage(id, 'middle'))} />
            <Item icon={<AlignEndHorizontal size={16} />} label="Bottom" onClick={run(() => editor.alignToPage(id, 'bottom'))} />
          </Sub>
          <hr />
          <Item
            icon={locked ? <LockOpen size={18} /> : <Lock size={18} />}
            label={locked ? 'Unlock' : 'Lock'}
            keys="⌥⇧L"
            onClick={run(() => editor.toggleLock(id))}
          />
          {target instanceof FabricImage && (
            <Item icon={<Wallpaper size={18} />} label="Set image as background" onClick={run(() => editor.setAsBackground(id))} />
          )}
          {editor.isMasked(id) && (
            <Item icon={<Shapes size={18} />} label="Release from shape" onClick={run(() => editor.releaseMask(id))} />
          )}
          <Item icon={<Download size={18} />} label="Download selection" onClick={run(download)} />
        </>
      ) : (
        <Item icon={<Clipboard size={18} />} label="Paste" keys="⌘V" disabled={!editor.canPaste()} onClick={run(() => editor.paste())} />
      )}
    </div>
  )
}

function Item({ icon, label, keys, disabled, onClick }: { icon: ReactNode; label: string; keys?: string; disabled?: boolean; onClick: () => void }) {
  return (
    <button className="cm-item" disabled={disabled} onClick={onClick}>
      <span className="cm-icon">{icon}</span>
      <span className="cm-label">{label}</span>
      {keys && <kbd>{keys}</kbd>}
    </button>
  )
}

function Sub({ icon, label, children }: { icon: ReactNode; label: string; children: ReactNode }) {
  return (
    <div className="cm-sub">
      <button className="cm-item">
        <span className="cm-icon">{icon}</span>
        <span className="cm-label">{label}</span>
        <ChevronRight size={16} />
      </button>
      <div className="cm-flyout">{children}</div>
    </div>
  )
}
