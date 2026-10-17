import { useEffect, useRef, useState } from 'react'
import { Shapes, Upload } from 'lucide-react'
import type { Editor } from '../editor/Editor'

type Tab = 'elements' | 'uploads'

const pretty = (group: string) => group.replace('brand-kit/', '').replace(/^\d+_/, '').replace(/_/g, ' ')

export function LeftPanel({ editor }: { editor: Editor | null }) {
  const [tab, setTab] = useState<Tab>('elements')
  const [groups, setGroups] = useState<Record<string, string[]>>({})
  const [uploads, setUploads] = useState<string[]>([])
  const fileRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    fetch('/api/assets')
      .then((r) => r.json())
      .then(setGroups)
      .catch(() => setGroups({}))
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
        {tab === 'uploads' && (
          <>
            <button className="upload-btn" onClick={() => fileRef.current?.click()}>
              <Upload size={16} /> Upload files
            </button>
            <input ref={fileRef} type="file" accept="image/*" multiple hidden onChange={(e) => onFiles(e.target.files)} />
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
