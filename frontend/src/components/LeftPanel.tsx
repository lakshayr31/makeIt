import { useEffect, useRef, useState } from 'react'
import { Layers, Shapes, Upload } from 'lucide-react'
import type { Editor } from '../editor/Editor'
import { importLayers, type LayerSplit } from '../editor/importLayers'

type Tab = 'elements' | 'uploads' | 'tests'

const pretty = (group: string) => group.replace('brand-kit/', '').replace(/^\d+_/, '').replace(/_/g, ' ')

export function LeftPanel({ editor, inspiration, onFit }: { editor: Editor | null; inspiration?: string | null; onFit: () => void }) {
  const [tab, setTab] = useState<Tab>('elements')
  const [groups, setGroups] = useState<Record<string, string[]>>({})
  const [uploads, setUploads] = useState<string[]>([])
  const [splits, setSplits] = useState<{ url: string; data: LayerSplit }[]>([])
  const fileRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    fetch('/api/layer-tests')
      .then((r) => r.json())
      .then((urls: string[]) => Promise.all(urls.map(async (url) => ({ url, data: (await (await fetch(url)).json()) as LayerSplit }))))
      .then(setSplits)
      .catch(() => setSplits([]))
  }, [])

  const openSplit = async (data: LayerSplit) => {
    if (!editor) return
    await importLayers(editor, data)
    onFit()
  }

  useEffect(() => {
    // Retry: the backend may be mid-reload when the editor opens.
    let tries = 0
    let timer = 0
    const load = () =>
      fetch('/api/assets')
        .then((r) => (r.ok ? r.json() : Promise.reject()))
        .then(setGroups)
        .catch(() => {
          if (++tries < 5) timer = window.setTimeout(load, 1500)
        })
    load()
    return () => clearTimeout(timer)
  }, [])

  const add = async (src: string) => {
    if (!editor) return
    const size = Math.min(editor.width, editor.height) * 0.45
    const img = await editor.addImage({ src, x: (editor.width - size) / 2, y: (editor.height - size) / 2, width: size, height: size })
    editor.canvas.setActiveObject(img)
    editor.canvas.requestRenderAll()
    editor.commit()
  }

  const onFiles = (files: FileList | null) => {
    for (const f of Array.from(files ?? [])) {
      const reader = new FileReader()
      reader.onload = () => {
        const url = String(reader.result)
        setUploads((u) => [url, ...u])
        add(url)
      }
      reader.readAsDataURL(f)
    }
  }

  const entries = Object.entries(groups).filter(([g]) => g.startsWith('brand-kit/') || g === 'references')

  return (
    <aside className="left">
      <nav className="rail">
        <button className={tab === 'elements' ? 'on' : ''} onClick={() => setTab('elements')}>
          <span className="rail-icon"><Shapes size={20} /></span>Elements
        </button>
        <button className={tab === 'uploads' ? 'on' : ''} onClick={() => setTab('uploads')}>
          <span className="rail-icon"><Upload size={20} /></span>Uploads
        </button>
        <button className={tab === 'tests' ? 'on' : ''} onClick={() => setTab('tests')}>
          <span className="rail-icon"><Layers size={20} /></span>Layer tests
        </button>
      </nav>
      <div className="panel">
        {tab === 'elements' &&
          (entries.length === 0 ? (
            <p className="muted">No assets yet — is the backend running?</p>
          ) : (
            entries.map(([group, urls]) => (
              <section key={group}>
                <h4>{pretty(group)}</h4>
                <div className="grid">
                  {urls.map((u) => (
                    <button key={u} className="thumb" onClick={() => add(u)} title="Add to page">
                      <img src={u} loading="lazy" alt="" />
                    </button>
                  ))}
                </div>
              </section>
            ))
          ))}
        {tab === 'tests' && (
          <>
            <p className="muted">AI layer splits of reference ads. Open one to get it as editable layers, then compare with the original below.</p>
            {splits.length === 0 && <p className="muted">No splits in assets/layers yet.</p>}
            {splits.map(({ url, data }) => (
              <div key={url} className="split">
                <img src={data.reference} alt="Original ad" />
                <div className="split-meta">
                  <strong>{url.split('/').pop()?.replace('.json', '')}</strong>
                  <span className="muted">{data.layers.length} layers · original above</span>
                </div>
                <button className="upload-btn" onClick={() => openSplit(data)}>
                  <Layers size={16} /> Open as layers
                </button>
              </div>
            ))}
          </>
        )}
        {tab === 'uploads' && (
          <>
            <button className="upload-btn" onClick={() => fileRef.current?.click()}>
              <Upload size={16} /> Upload files
            </button>
            <input ref={fileRef} type="file" accept="image/*" multiple hidden onChange={(e) => onFiles(e.target.files)} />
            {inspiration && (
              <section>
                <h4>Inspiration</h4>
                <p className="muted">The ad this design was made from.</p>
                <button className="thumb inspiration" onClick={() => add(inspiration)} title="Add to page">
                  <img src={inspiration} alt="Inspiration ad" />
                </button>
              </section>
            )}
            <div className="grid">
              {uploads.map((u) => (
                <button key={u.slice(-40)} className="thumb" onClick={() => add(u)}>
                  <img src={u} alt="" />
                </button>
              ))}
            </div>
          </>
        )}
      </div>
    </aside>
  )
}
