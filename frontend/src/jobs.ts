import type { SolvedLayout } from './editor/importLayout'

/** "Create a design from an ad": start a job, then stream its progress over SSE. */

export interface JobStep {
  id: string
  label: string
}

/** Brand check of one variant: plain-English messages. */
export interface VariantReview {
  fixed: string[] // auto-fixed by the agent
  issues: string[] // still open, need the user
  suggestions: string[] // softer notes
}

/** Art direction behind one variant: the brand-guideline choices made. */
export interface VariantDirection {
  axis: string
  changes: string[] // what moved vs the closest match
  funnel: 'top' | 'mid' | 'bottom'
  background: { type: string; text_area?: string }
  layout: string
  text_holder: string
  visual: { type: string; subject?: string; style?: string; treatment?: string }
  blooms: { colour: string; scale: number; bleed: string[]; role: string }[]
  proof: string
  logo: { corner: string; on: string; pill: boolean }
  charms: number
  reasons: string[] // guidelines followed, plain English
}

export type JobEvent = (
  | { type: 'start'; steps: JobStep[]; source: string; n?: number }
  | { type: 'step'; id: string; status: 'running' | 'done' | 'error'; detail?: string; secs?: number }
  // review is null until the background brand check reports (see 'review').
  | { type: 'variant'; index: number; axis: string; name: string; design_id: string; layout: SolvedLayout; review?: VariantReview | null; direction?: VariantDirection }
  // Background brand check of one variant; null review = the check failed. layout = fixed design.
  | { type: 'review'; index: number; design_id: string; review: VariantReview | null; layout?: SolvedLayout }
  | { type: 'done'; error?: boolean }
) & { t?: number } // server time, epoch seconds

export const MOCK_JOB = 'mock'

export const readAsDataUrl = (file: File) =>
  new Promise<string>((resolve, reject) => {
    const r = new FileReader()
    r.onload = () => resolve(r.result as string)
    r.onerror = () => reject(r.error)
    r.readAsDataURL(file)
  })

/** Start a job. 3 versions unless the prompt asks for another number; the backend decides. */
export async function createJob(image: string, prompt = ''): Promise<string> {
  const res = await fetch('/api/jobs', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ image, prompt, format: '4:5' }),
  })
  if (!res.ok) throw new Error(`Couldn't start (${res.status})`)
  const body: { id: string; n?: number } = await res.json()
  const { id } = body
  const n = body.n ?? 3
  try {
    sessionStorage.setItem(`job-n:${id}`, String(n))
  } catch {
    /* storage blocked: page falls back to 3 slots */
  }
  return id
}

/** How many variants a job will make: start event, else what this tab asked for. */
export function expectedVariants(jobId: string, fromStart?: number): number {
  if (fromStart) return fromStart
  try {
    return Number(sessionStorage.getItem(`job-n:${jobId}`)) || 3
  } catch {
    return 3
  }
}

/** Subscribe to a job's events (past ones are replayed). Returns an unsubscribe. */
export function watchJob(jobId: string, onEvent: (e: JobEvent) => void): () => void {
  if (jobId === MOCK_JOB) return mockJob(onEvent)
  const es = new EventSource(`/api/jobs/${jobId}/events`)
  es.onmessage = (m) => {
    const e = JSON.parse(m.data) as JobEvent
    onEvent(e)
    if (e.type === 'done') es.close()
  }
  es.onerror = () => {
    // Closed by the server after `done`, or the job is gone.
    if (es.readyState === EventSource.CLOSED) onEvent({ type: 'done', error: true })
  }
  return () => es.close()
}

// ---- mock (#/create/mock): replays a real run with fake timings ----------

// Real layouts from backend/runs/spotify_car (extra fields like `lines` are ignored).
const MOCK_RAW = [{"axis":"faithful","background_colour":"#FFFFFF","layers":[{"id":"background","role":"background","type":"image","x":0.0,"y":-283.7564766839379,"w":1080,"h":1917.5129533678758,"z":0,"props":{"src":"/assets/brand-kit/24_Background_Templates/24_Background_Templates/16_fe4ed594-a50e-4a9e-8839-49216794802a.png","clip":[0,0,1080,1350]}},{"id":"shape1","role":"shape","type":"image","x":-89.64,"y":507.68366197183093,"w":1260.3600000000001,"h":1233.732676056338,"z":1,"props":{"src":"/assets/brand-kit/parts/blooms/04/blue.png","clip":null}},{"id":"card","role":"card","type":"rect","x":41.64,"y":837.8,"w":995.64,"h":479.20000000000005,"z":1.5,"props":{"fill":"#FFFFFF","radius":40}},{"id":"hero","role":"hero","type":"image","x":-50.28749999999991,"y":5.684341886080802e-14,"w":1180.5749999999998,"h":787.0499999999998,"z":2,"props":{"src":"/generated/54e4fcb3533a1e92.png","clip":[0.0,0.0,1080.0,787.05]}},{"id":"accent1","role":"accent","type":"image","x":450.35999999999996,"y":254.08824324324326,"w":180.36,"h":168.1735135135135,"z":3,"props":{"src":"/assets/brand-kit/parts/charms/07/yellow.png","clip":null}},{"id":"headline","role":"headline","type":"text","x":89.64,"y":885.8,"w":899.64,"h":259.20000000000005,"z":4,"props":{"text":"Every tool you need to manage your business, free for 30 days.","font_size":80,"weight":"bold","colour":"#000856","lines":["Every tool you need to","manage your business,","free for 30 days."]}},{"id":"cta","role":"cta","type":"text","x":359.64000000000004,"y":1177.0,"w":375.96875,"h":92,"z":5,"props":{"text":"Try Xero for free","font_size":36,"weight":"bold","colour":"#FFFFFF","fill":"#000856","pill":true,"lines":["Try Xero for free"]}},{"id":"logo","role":"logo","type":"image","x":89.64,"y":1193.0,"w":210.0,"h":60,"z":6,"props":{"src":"/assets/brand-kit/10_Logo/10_Logo/02_2f020a69-e294-4971-b448-760f8b1827ad.png","pill":false}}]},{"axis":"hero","background_colour":"#FFFFFF","layers":[{"id":"background","role":"background","type":"image","x":0.0,"y":-283.7564766839379,"w":1080,"h":1917.5129533678758,"z":0,"props":{"src":"/assets/brand-kit/24_Background_Templates/24_Background_Templates/16_fe4ed594-a50e-4a9e-8839-49216794802a.png","clip":[0,0,1080,1350]}},{"id":"shape1","role":"shape","type":"image","x":-89.64,"y":507.68366197183093,"w":1260.3600000000001,"h":1233.732676056338,"z":1,"props":{"src":"/assets/brand-kit/parts/blooms/04/blue.png","clip":null}},{"id":"card","role":"card","type":"rect","x":41.64,"y":837.8,"w":995.64,"h":479.20000000000005,"z":1.5,"props":{"fill":"#FFFFFF","radius":40}},{"id":"hero","role":"hero","type":"image","x":198.21594294770205,"y":112.05000000000001,"w":682.4881141045959,"h":675.0,"z":2,"props":{"src":"/assets/brand-kit/07_Illustration/07_Illustration/06_7dcd5cfc-92b3-4d4d-bf31-74b5683ba887.png","clip":null}},{"id":"accent1","role":"accent","type":"image","x":450.35999999999996,"y":254.08824324324326,"w":180.36,"h":168.1735135135135,"z":3,"props":{"src":"/assets/brand-kit/parts/charms/07/yellow.png","clip":null}},{"id":"headline","role":"headline","type":"text","x":89.64,"y":885.8,"w":899.64,"h":259.20000000000005,"z":4,"props":{"text":"Every tool you need to manage your business, free for 30 days.","font_size":80,"weight":"bold","colour":"#000856","lines":["Every tool you need to","manage your business,","free for 30 days."]}},{"id":"cta","role":"cta","type":"text","x":359.64000000000004,"y":1177.0,"w":375.96875,"h":92,"z":5,"props":{"text":"Try Xero for free","font_size":36,"weight":"bold","colour":"#FFFFFF","fill":"#000856","pill":true,"lines":["Try Xero for free"]}},{"id":"logo","role":"logo","type":"image","x":89.64,"y":1193.0,"w":210.0,"h":60,"z":6,"props":{"src":"/assets/brand-kit/10_Logo/10_Logo/02_2f020a69-e294-4971-b448-760f8b1827ad.png","pill":false}}]},{"axis":"palette","background_colour":"#000856","layers":[{"id":"background","role":"background","type":"image","x":-135.0,"y":0.0,"w":1350.0,"h":1350.0,"z":0,"props":{"src":"/assets/brand-kit/24_Background_Templates/24_Background_Templates/05_85cd075f-f534-491c-b16d-e4561a00aa9d.png","clip":[0,0,1080,1350]}},{"id":"shape1","role":"shape","type":"image","x":-89.64,"y":507.68366197183093,"w":1260.3600000000001,"h":1233.732676056338,"z":1,"props":{"src":"/assets/brand-kit/parts/blooms/04/blue.png","clip":null}},{"id":"card","role":"card","type":"rect","x":41.64,"y":852.45,"w":995.64,"h":412.0999999999999,"z":1.5,"props":{"fill":"#000856","radius":40}},{"id":"hero","role":"hero","type":"image","x":-50.28749999999991,"y":5.684341886080802e-14,"w":1180.5749999999998,"h":787.0499999999998,"z":2,"props":{"src":"/generated/54e4fcb3533a1e92.png","clip":[0.0,0.0,1080.0,787.05]}},{"id":"accent1","role":"accent","type":"image","x":450.35999999999996,"y":254.08824324324326,"w":180.36,"h":168.1735135135135,"z":3,"props":{"src":"/assets/brand-kit/parts/charms/07/yellow.png","clip":null}},{"id":"headline","role":"headline","type":"text","x":89.64,"y":900.45,"w":899.64,"h":120.96000000000001,"z":4,"props":{"text":"Every tool you need to manage your business, free for 30 days.","font_size":56,"weight":"bold","colour":"#FFFFFF","lines":["Every tool you need to manage","your business, free for 30 days."]}},{"id":"cta","role":"cta","type":"text","x":359.64000000000004,"y":1124.55,"w":375.96875,"h":92,"z":5,"props":{"text":"Try Xero for free","font_size":36,"weight":"bold","colour":"#000856","fill":"#00B8E4","pill":true,"lines":["Try Xero for free"]}},{"id":"logo","role":"logo","type":"image","x":89.64,"y":1140.55,"w":210.0,"h":60,"z":6,"props":{"src":"/assets/brand-kit/10_Logo/10_Logo/01_0f4c5387-a60d-4a27-93e8-9f5223676154.png","pill":false}}]}]
const MOCK_LAYOUTS = MOCK_RAW as SolvedLayout[]

const MOCK_NAMES = ['Closest match', 'Hero image', 'Brand palette']

const MOCK_DIRECTIONS: VariantDirection[] = [
  {
    axis: 'faithful', changes: [], funnel: 'top', background: { type: 'template', text_area: 'bottom' }, layout: 'image_top',
    text_holder: 'white_card', visual: { type: 'generated_scene', subject: 'small business owner', style: 'photo', treatment: 'in_bloom' },
    blooms: [{ colour: 'blue', scale: 1.2, bleed: ['left', 'right'], role: 'frame' }], proof: 'none',
    logo: { corner: 'bottom_left', on: 'white', pill: false }, charms: 1,
    reasons: ['Top-of-funnel ads lead with a lifestyle photo', 'Photos sit inside a bloom, never a hard rectangle', 'Headline on a white card for contrast over the template'],
  },
  {
    axis: 'hero', changes: ['illustration instead of photo', 'framed bloom'], funnel: 'top', background: { type: 'white' }, layout: 'image_top',
    text_holder: 'none', visual: { type: 'generated_scene', style: 'flat_illustration', treatment: 'framed_bloom_break' },
    blooms: [{ colour: 'blue', scale: 1, bleed: ['right'], role: 'frame' }], proof: 'none',
    logo: { corner: 'bottom_left', on: 'white', pill: false }, charms: 1,
    reasons: ['Illustrations may break out of a framed bloom', 'White background needs no text card'],
  },
  {
    axis: 'palette', changes: ['navy background', 'navy card'], funnel: 'mid', background: { type: 'navy' }, layout: 'image_top',
    text_holder: 'navy_card', visual: { type: 'product_ui', treatment: 'plain' },
    blooms: [{ colour: 'blue', scale: 1.1, bleed: ['left'], role: 'accent' }], proof: 'free_trial',
    logo: { corner: 'bottom_left', on: 'navy', pill: false }, charms: 0,
    reasons: ['Mid-funnel ads show the product', 'On navy, the CTA uses brand blue', 'White logo on dark backgrounds'],
  },
]

const MOCK_REVIEWS: VariantReview[] = [
  { fixed: ['Logo moved off the image edge', 'Headline set in brand navy'], issues: [], suggestions: ['Try a shorter headline'] },
  { fixed: ['CTA pill recoloured to brand navy'], issues: ['Illustration is not from the brand kit'], suggestions: [] },
  { fixed: [], issues: [], suggestions: [] },
]

function mockJob(onEvent: (e: JobEvent) => void) {
  const script: [number, JobEvent][] = [
    [100, { type: 'start', n: 3, source: '/assets/competitors/spotify_car.webp', steps: [
      { id: 'analyse', label: 'Reading the ad' },
      { id: 'direct', label: 'Art directing Xero versions' },
      { id: 'match', label: 'Matching Xero brand assets' },
      { id: 'build', label: 'Building images' },
      { id: 'publish', label: 'Saving editable designs' },
      { id: 'review', label: 'Checking brand rules and fixing' },
    ] }],
    [300, { type: 'step', id: 'analyse', status: 'running' }],
    [1800, { type: 'step', id: 'analyse', status: 'done', secs: 1.5, detail: 'Car hero, headline top, CTA pill' }],
    [1850, { type: 'step', id: 'direct', status: 'running' }],
    [2400, { type: 'step', id: 'direct', status: 'done', secs: 0.5, detail: '3 directions' }],
    [2450, { type: 'step', id: 'match', status: 'running' }],
    [3000, { type: 'step', id: 'match', status: 'done', secs: 1.1, detail: '12 assets matched' }],
    [3100, { type: 'step', id: 'build', status: 'running' }],
    [5000, { type: 'step', id: 'build', status: 'done', secs: 1.9, detail: '3 hero images' }],
    [5100, { type: 'step', id: 'publish', status: 'running' }],
  ]
  MOCK_LAYOUTS.forEach((layout, index) =>
    script.push([5200 + index * 600, {
      type: 'variant', index, axis: layout.axis, name: `Spotify car · ${MOCK_NAMES[index]}`,
      design_id: `d-ad-spotify-car-${index}`, layout, review: null, direction: MOCK_DIRECTIONS[index],
    }]),
  )
  script.push([6500, { type: 'step', id: 'publish', status: 'done', secs: 1.4, detail: '3 designs saved' }])
  script.push([6600, { type: 'step', id: 'review', status: 'running' }])
  MOCK_LAYOUTS.forEach((layout, index) =>
    script.push([8100 + index * 700, {
      type: 'review', index, design_id: `d-ad-spotify-car-${index}`, review: MOCK_REVIEWS[index],
      // Fresh copy stands in for the fixed layout, so the preview re-renders.
      ...(index === 0 ? { layout: { ...layout } } : {}),
    }]),
  )
  script.push([9800, { type: 'step', id: 'review', status: 'done', secs: 3.2, detail: '3 fixed · 1 need you' }])
  script.push([9900, { type: 'done' }])
  const timers = script.map(([ms, e]) => setTimeout(() => onEvent(e), ms))
  return () => timers.forEach(clearTimeout)
}
