import type { SolvedLayout } from './editor/importLayout'

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

export interface SavedDesign {
  name: string
  state: DesignState | null
  /** Solved layout from the ad pipeline; turned into layers on first open. */
  layout?: SolvedLayout
  /** Designer flow: one finished PNG; opened as a full-canvas image layer on first open. */
  image?: string
  /** Canvas size in px; set alongside `image`. */
  width?: number
  height?: number
  /** The ad this design was generated from. */
  inspiration?: string | null
  /** All pages, top first. Absent on designs saved before pages existed. */
  pages?: SavedPage[]
}

export interface SavedPage {
  state: DesignState
  thumbnail: string
}

/** null only when the design genuinely doesn't exist (404). Any other failure throws, so a
 *  backend hiccup is never mistaken for a new, empty design (which autosave would then write). */
export async function getDesign(id: string): Promise<SavedDesign | null> {
  const res = await fetch(`/api/designs/${id}`)
  if (res.status === 404) return null
  if (!res.ok) throw new Error(`Couldn't load design (${res.status})`)
  return res.json()
}

/** `state` + `thumbnail` are page 1 (home grid); `pages` holds every page when given. */
export async function saveDesign(id: string, name: string, state: DesignState, thumbnail: string, pages?: SavedPage[]) {
  const first = pages?.[0]
  const res = await fetch(`/api/designs/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, state: first?.state ?? state, thumbnail: first?.thumbnail ?? thumbnail, pages }),
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
