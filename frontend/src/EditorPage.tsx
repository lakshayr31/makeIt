import { useCallback, useEffect, useRef, useState } from 'react'
import type { TPointerEventInfo } from 'fabric'
import { Editor } from './editor/Editor'
import { getDesign, saveDesign, type DesignState } from './designs'
import { Header } from './components/Header'
import { ContextToolbar } from './components/ContextToolbar'
import { SelectionMiniBar } from './components/SelectionMiniBar'
import { LeftPanel } from './components/LeftPanel'
import { importLayout } from './editor/importLayout'
import { ZoomBar } from './components/ZoomBar'
import { ContextMenu } from './components/ContextMenu'
import type { FabricObject } from 'fabric'
import { PageHeader } from './components/PagesColumn'
import { ChatPanel } from './components/ChatPanel'
import type { ChatContext } from './agent'

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

const LOAD_RETRY_MS = 1500
const AUTOSAVE_DELAY_MS = 800
const DEFAULT_NAME = 'Untitled design'

type SaveStatus = 'loading' | 'saved' | 'saving' | 'error'

/** One page of the design. The active page lives in Fabric; its entry here is refreshed on leave/save. */
interface Page {
  key: string
  state: DesignState
  thumbnail: string
}

const PAGE_HEADER_H = 40
const PAGE_BLOCK_MIN_W = 240
const NEW_VERSION_LABEL_MS = 4000
let pageSeq = 0
const pageKey = () => `p${++pageSeq}`

const blankState = (w: number, h: number): DesignState => ({ w, h, canvas: { objects: [], background: '#ffffff' } })

export function EditorPage({ designId }: { designId: string }) {
  const canvasEl = useRef<HTMLCanvasElement>(null)
  const stageRef = useRef<HTMLDivElement>(null)
  const [editor, setEditor] = useState<Editor | null>(null)
  const [inspiration, setInspiration] = useState<string | null>(null)
  const [, setTick] = useState(0)
  const [badge, setBadge] = useState<Badge | null>(null)
  const [transforming, setTransforming] = useState(false)
  const [menu, setMenu] = useState<{ x: number; y: number; target?: FabricObject } | null>(null)
  const closeMenu = useCallback(() => setMenu(null), [])
  const [name, setName] = useState(DEFAULT_NAME)
  const [status, setStatus] = useState<SaveStatus>('loading')
  const savedRef = useRef({ version: -1, name: '', pagesRev: 0 })

  // Pages: refs hold the latest values for async handlers; state drives rendering.
  const [pages, setPagesState] = useState<Page[]>([])
  const pagesRef = useRef<Page[]>([])
  const [active, setActiveState] = useState(0)
  const activeRef = useRef(0)
  const [pagesRev, setPagesRev] = useState(0)
  const [newPageKey, setNewPageKey] = useState<string | null>(null)
  const switchingRef = useRef(false)
  const liveRef = useRef<HTMLDivElement>(null)

  const [chatOpen, setChatOpen] = useState(false)
  const [chatContext, setChatContext] = useState<ChatContext>(null)
  const [areaMode, setAreaMode] = useState(false)

  const setPages = useCallback((next: Page[], nextActive: number) => {
    pagesRef.current = next
    activeRef.current = nextActive
    setPagesState(next)
    setActiveState(nextActive)
    setPagesRev((r) => r + 1)
  }, [])

  const fitToScreen = useCallback((ed: Editor) => {
    const stage = stageRef.current
    if (!stage) return
    ed.fit(stage.clientWidth - STAGE_PADDING * 2, stage.clientHeight - STAGE_PADDING * 2 - PAGE_HEADER_H)
  }, [])

  /** Pages with the active one refreshed from the live canvas. */
  const currentPages = useCallback((ed: Editor): Page[] => {
    const i = activeRef.current
    return pagesRef.current.map((p, j) => (j === i ? { ...p, state: ed.state(), thumbnail: ed.thumbnail() } : p))
  }, [])

  const scrollToLive = useCallback(() => {
    requestAnimationFrame(() => liveRef.current?.scrollIntoView({ block: 'start', behavior: 'smooth' }))
  }, [])

  /** Save the active page, then make `next` (with `nextActive`) current, loading it into Fabric if it changed. */
  const goTo = useCallback(
    async (ed: Editor, next: Page[], nextActive: number) => {
      if (switchingRef.current) return
      switchingRef.current = true
      try {
        const keyBefore = pagesRef.current[activeRef.current]?.key
        ed.canvas.discardActiveObject()
        if (next[nextActive].key !== keyBefore) await ed.load(next[nextActive].state) // load() also resets undo history
        setPages(next, nextActive)
        scrollToLive()
      } finally {
        switchingRef.current = false
      }
    },
    [setPages, scrollToLive],
  )

  const selectPage = useCallback(
    (i: number) => {
      if (!editor || i === activeRef.current) return
      void goTo(editor, currentPages(editor), i)
    },
    [editor, goTo, currentPages],
  )

  const addPage = useCallback(
    (after: number) => {
      if (!editor) return
      const next = currentPages(editor)
      next.splice(after + 1, 0, { key: pageKey(), state: blankState(editor.width, editor.height), thumbnail: '' })
      void goTo(editor, next, after + 1)
    },
    [editor, goTo, currentPages],
  )

  const duplicatePage = useCallback(
    (i: number) => {
      if (!editor) return
      const next = currentPages(editor)
      next.splice(i + 1, 0, { ...next[i], key: pageKey() })
      setPages(next, activeRef.current > i ? activeRef.current + 1 : activeRef.current)
    },
    [editor, currentPages, setPages],
  )

  const deletePage = useCallback(
    (i: number) => {
      if (!editor || pagesRef.current.length < 2) return
      const next = currentPages(editor)
      next.splice(i, 1)
      const a = activeRef.current
      if (i === a) void goTo(editor, next, Math.min(i, next.length - 1))
      else setPages(next, i < a ? a - 1 : a)
    },
    [editor, currentPages, goTo, setPages],
  )

  const movePage = useCallback(
    (i: number, dir: -1 | 1) => {
      if (!editor) return
      const j = i + dir
      const next = currentPages(editor)
      if (j < 0 || j >= next.length) return
      ;[next[i], next[j]] = [next[j], next[i]]
      const a = activeRef.current
      setPages(next, a === i ? j : a === j ? i : a)
    },
    [editor, currentPages, setPages],
  )

  /** Contract: copy the current page as a new page ABOVE it, make it active, apply `mutate` there. */
  const onNewVersion = useCallback(
    async (mutate: (editor: Editor) => Promise<void>) => {
      if (!editor) return
      const next = currentPages(editor)
      const a = activeRef.current
      const copy: Page = { ...next[a], key: pageKey() }
      next.splice(a, 0, copy)
      // Same content is already on canvas; reload only to start a fresh undo history for the new page.
      await editor.load(copy.state)
      setPages(next, a)
      setNewPageKey(copy.key)
      setTimeout(() => setNewPageKey((k) => (k === copy.key ? null : k)), NEW_VERSION_LABEL_MS)
      scrollToLive()
      await mutate(editor)
      editor.commit()
    },
    [editor, currentPages, setPages, scrollToLive],
  )

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
    let cancelled = false
    let raf = 0
    let retry = 0
    // Keep retrying until the backend answers; autosave stays off while status is 'loading'.
    const fetchDesign = async (): Promise<Awaited<ReturnType<typeof getDesign>>> => {
      for (;;) {
        try {
          return await getDesign(designId)
        } catch {
          if (cancelled) throw new Error('cancelled')
          await new Promise((r) => (retry = window.setTimeout(r, LOAD_RETRY_MS)))
        }
      }
    }
    fetchDesign().then(async (saved) => {
      if (cancelled) return
      let loaded: Page[] | null = null
      if (saved) {
        if (saved.pages?.length) {
          loaded = saved.pages.map((p) => ({ key: pageKey(), state: p.state, thumbnail: p.thumbnail }))
          await ed.load(loaded[0].state)
        } else if (saved.state) await ed.load(saved.state)
        savedRef.current = { version: ed.version, name: saved.name, pagesRev: 0 }
        // Generated from an ad and never opened: build its layers; autosave then stores them.
        if (!saved.state && !loaded && saved.layout) await importLayout(ed, saved.layout)
        // Designer flow: one finished image becomes a full-canvas layer the user can build on.
        else if (!saved.state && !loaded && saved.image) {
          const w = saved.width ?? DESIGN_W
          const h = saved.height ?? DESIGN_H
          ed.reset(w, h, '#ffffff')
          await ed.addImage({ id: 'ad', name: 'Generated ad', src: saved.image, x: 0, y: 0, width: w, height: h })
          ed.commit()
        }
        setName(saved.name)
        setInspiration(saved.inspiration ?? null)
      }
      if (cancelled) return
      const initial = loaded ?? [{ key: pageKey(), state: ed.state(), thumbnail: '' }]
      pagesRef.current = initial
      activeRef.current = 0
      setPagesState(initial)
      setActiveState(0)
      raf = requestAnimationFrame(() => fitToScreen(ed))
      setStatus('saved')
    }, () => {})
    return () => {
      cancelled = true
      clearTimeout(retry)
      cancelAnimationFrame(raf)
      off()
      ed.canvas.dispose()
    }
  }, [fitToScreen, designId])

  // Autosave shortly after any content or name change.
  const version = editor?.version ?? 0
  useEffect(() => {
    if (!editor || status === 'loading') return
    const dirty =
      version !== savedRef.current.version || name !== savedRef.current.name || pagesRev !== savedRef.current.pagesRev
    if (!dirty) return
    const timer = setTimeout(async () => {
      if (switchingRef.current) return
      setStatus('saving')
      const snapshot = { version: editor.version, name, pagesRev }
      try {
        const all = currentPages(editor)
        pagesRef.current = all
        await saveDesign(
          designId,
          name,
          editor.state(),
          editor.thumbnail(),
          all.map((p) => ({ state: p.state, thumbnail: p.thumbnail })),
        )
        savedRef.current = snapshot
        setStatus('saved')
      } catch {
        setStatus('error')
      }
    }, AUTOSAVE_DELAY_MS)
    return () => clearTimeout(timer)
  }, [editor, version, name, status, designId, pagesRev, currentPages])

  // Re-fit when the chat panel opens/closes (stage width changes).
  useEffect(() => {
    if (!editor) return
    const raf = requestAnimationFrame(() => fitToScreen(editor))
    return () => cancelAnimationFrame(raf)
  }, [chatOpen, editor, fitToScreen])

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
  // Header row needs room for its buttons even at tiny zoom.
  const blockWidth = Math.max((editor?.width ?? DESIGN_W) * (editor?.zoom ?? 1), PAGE_BLOCK_MIN_W)

  return (
    <div className="app">
      <Header editor={editor} name={name} onRename={setName} status={status} />
      <div className="body">
        <LeftPanel editor={editor} inspiration={inspiration} onFit={() => editor && fitToScreen(editor)} />
        {editor && menu && (
          <ContextMenu
            editor={editor}
            x={menu.x}
            y={menu.y}
            target={menu.target}
            onClose={closeMenu}
            onAsk={(id) => {
              const el = id ? editor.summary().elements.find((e) => e.id === id) : undefined
              setChatContext(id ? { kind: 'element', id, name: el?.name ?? id } : null)
              setChatOpen(true)
            }}
            onSelectArea={() => setAreaMode(true)}
          />
        )}
        <main className="workspace">
          <ContextToolbar editor={editor} selected={selected} />
          <div className="stage" ref={stageRef} onMouseDown={(e) => e.target === e.currentTarget && editor?.canvas.discardActiveObject() && editor.canvas.requestRenderAll()}>
            <div className="page-list">
              {/* The live canvas block never moves in the React tree (Fabric wraps the <canvas>); CSS `order` places it. */}
              <div className="page-block page-block-active" style={{ order: active, width: blockWidth }} ref={liveRef}>
                {editor && pages[active] && (
                  <PageHeader
                    index={active}
                    count={pages.length}
                    name={name}
                    active
                    isNew={pages[active].key === newPageKey}
                    onMove={(d) => movePage(active, d)}
                    onDuplicate={() => duplicatePage(active)}
                    onDelete={() => deletePage(active)}
                    onAdd={() => addPage(active)}
                  />
                )}
                <div className="page">
                  <canvas ref={canvasEl} />
                  {editor && selected && !transforming && <SelectionMiniBar editor={editor} selected={selected} />}
                </div>
              </div>
              {editor &&
                pages.map((p, i) =>
                  i === active ? null : (
                    <div key={p.key} className="page-block" style={{ order: i, width: blockWidth }}>
                      <PageHeader
                        index={i}
                        count={pages.length}
                        name={name}
                        active={false}
                        isNew={p.key === newPageKey}
                        onMove={(d) => movePage(i, d)}
                        onDuplicate={() => duplicatePage(i)}
                        onDelete={() => deletePage(i)}
                        onAdd={() => addPage(i)}
                      />
                      <button
                        className="page-thumb"
                        title={`Edit page ${i + 1}`}
                        style={{ width: p.state.w * editor.zoom, height: p.state.h * editor.zoom }}
                        onClick={() => selectPage(i)}
                      >
                        {p.thumbnail && <img src={p.thumbnail} alt={`Page ${i + 1}`} draggable={false} />}
                      </button>
                    </div>
                  ),
                )}
            </div>
            {badge && (
              <div className="badge" style={{ left: badge.x, top: badge.y }}>
                {badge.text}
              </div>
            )}
          </div>
          <ZoomBar editor={editor} onFit={() => editor && fitToScreen(editor)} />
        </main>
        {editor && (
          <ChatPanel
            editor={editor}
            context={chatContext}
            setContext={setChatContext}
            open={chatOpen}
            setOpen={setChatOpen}
            areaMode={areaMode}
            setAreaMode={setAreaMode}
            onNewVersion={onNewVersion}
          />
        )}
      </div>
    </div>
  )
}
