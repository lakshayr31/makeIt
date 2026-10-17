import { useEffect, useState } from 'react'
import { BookOpen, Plus, Trash2 } from 'lucide-react'
import { deleteDesign, listDesigns, openDesign, timeAgo, type DesignSummary } from './designs'
import { UploadDialog } from './components/UploadDialog'

export function HomePage() {
  const [designs, setDesigns] = useState<DesignSummary[] | null>(null)
  const [query, setQuery] = useState('')
  const [creating, setCreating] = useState(false)

  const refresh = () => listDesigns().then(setDesigns).catch(() => setDesigns([]))
  useEffect(() => {
    refresh()
  }, [])

  const remove = async (d: DesignSummary) => {
    if (!confirm(`Delete "${d.name}"? This can't be undone.`)) return
    await deleteDesign(d.id)
    refresh()
  }

  const shown = (designs ?? []).filter((d) => d.name.toLowerCase().includes(query.toLowerCase()))

  return (
    <div className="home">
      <header className="header">
        <span className="logo">makeIt</span>
        <input className="home-search" placeholder="Search your designs" value={query} onChange={(e) => setQuery(e.target.value)} />
        <button className="brand-nav-btn" title="Brand guidelines" onClick={() => (window.location.hash = '#/brand')}>
          <BookOpen size={16} /> <span className="share-label">Brand guidelines</span>
        </button>
        <button className="share" onClick={() => setCreating(true)}>
          <Plus size={16} /> <span className="share-label">Create a design</span>
        </button>
      </header>

      <main className="home-body">
        <div className="hero">
          <h1>What will you design today?</h1>
          <button className="hero-btn" onClick={() => setCreating(true)}>
            <Plus size={18} /> Create a design
          </button>
        </div>

        <h2>Your designs</h2>
        {designs === null ? (
          <p className="muted">Loading…</p>
        ) : shown.length === 0 ? (
          <p className="muted">{query ? 'No designs match that name.' : 'No designs yet. Create one to get started.'}</p>
        ) : (
          <div className="design-grid">
            {shown.map((d) => (
              <div key={d.id} className="design-card" onClick={() => openDesign(d.id)}>
                <div className="design-thumb">
                  <img src={d.thumbnail} alt="" onError={(e) => (e.currentTarget.style.visibility = 'hidden')} />
                </div>
                <div className="design-meta">
                  <div>
                    <div className="design-name">{d.name}</div>
                    <div className="muted">{timeAgo(d.updated_at)} · {d.width} × {d.height}</div>
                  </div>
                  <button
                    className="icon-btn del"
                    title="Delete design"
                    onClick={(e) => {
                      e.stopPropagation()
                      remove(d)
                    }}
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </main>
      {creating && <UploadDialog onClose={() => setCreating(false)} />}
    </div>
  )
}
