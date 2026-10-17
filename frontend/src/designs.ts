/** Saved designs live on the backend: one JSON + PNG thumbnail each. */

export interface DesignSummary {
  id: string
  name: string
  updated_at: number
  width: number
  height: number
  thumbnail: string
}

export interface DesignState {
  w: number
  h: number
  canvas: object
}

export const listDesigns = (): Promise<DesignSummary[]> => fetch('/api/designs').then((r) => r.json())

export async function getDesign(id: string): Promise<{ name: string; state: DesignState } | null> {
  const res = await fetch(`/api/designs/${id}`)
  return res.ok ? res.json() : null
}

export async function saveDesign(id: string, name: string, state: DesignState, thumbnail: string) {
  const res = await fetch(`/api/designs/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, state, thumbnail }),
  })
  if (!res.ok) throw new Error(`Save failed: ${res.status}`)
}

export const deleteDesign = (id: string) => fetch(`/api/designs/${id}`, { method: 'DELETE' })

export const newDesignId = () => `d-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 6)}`

/** Hash routes: #/ (home) and #/design/<id>. */
export const goHome = () => (window.location.hash = '#/')
export const openDesign = (id: string) => (window.location.hash = `#/design/${id}`)

export function timeAgo(seconds: number) {
  const diff = Date.now() / 1000 - seconds
  if (diff < 60) return 'Edited just now'
  if (diff < 3600) return `Edited ${Math.floor(diff / 60)} min ago`
  if (diff < 86400) return `Edited ${Math.floor(diff / 3600)} h ago`
  return `Edited ${new Date(seconds * 1000).toLocaleDateString()}`
}
