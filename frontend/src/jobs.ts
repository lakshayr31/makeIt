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

/** Art direction behind one variant: the brand-guideline choices made.
 *  Every field is optional — the designer flow sends whatever it decided; render only what's there. */
export interface VariantDirection {
  axis?: string
  changes?: string[] // what moved vs the closest match
  funnel?: 'top' | 'mid' | 'bottom' | string
  background?: { type?: string; text_area?: string }
  layout?: string
  text_holder?: string
  visual?: {
    type?: string
    subject?: string
    style?: string
    treatment?: string
  }
  blooms?: {
    colour?: string
    scale?: number
    bleed?: string[]
    role?: string
  }[]
  proof?: string
  logo?: { corner?: string; on?: string; pill?: boolean }
  charms?: number
  reasons?: string[] // guidelines followed, plain English
}

export type JobEvent = (
  | { type: 'start'; steps: JobStep[]; source: string; n?: number }
  | {
      type: 'step'
      id: string
      status: 'running' | 'done' | 'error'
      detail?: string
      secs?: number
    }
  // The art director needs answers before composing; the job waits until POST /answers.
  | { type: 'questions'; questions: string[] }
  // Answers arrived (also replayed on reconnect). '' = the user skipped that question.
  | { type: 'answered'; answers: string[] }
  // review is null until the background brand check reports (see 'review').
  // Designer flow: layout is null and `image` is the finished PNG (width/height in px).
  | {
      type: 'variant'
      index: number
      axis: string
      name: string
      design_id: string
      layout: SolvedLayout | null
      image?: string
      width?: number
      height?: number
      review?: VariantReview | null
      direction?: VariantDirection
    }
  // Background brand check of one variant; null review = the check failed. layout = fixed design (absent for image designs).
  | {
      type: 'review'
      index: number
      design_id: string
      review: VariantReview | null
      layout?: SolvedLayout
    }
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

/** Send the user's answers to the art director's questions ('' = skipped). */
export async function answerJob(jobId: string, answers: string[]): Promise<void> {
  if (jobId === MOCK_JOB) return // the mock script emits `answered` on its own
  const res = await fetch(`/api/jobs/${jobId}/answers`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ answers }),
  })
  if (!res.ok) throw new Error(`Couldn't send answers (${res.status})`)
}

// ---- mock (#/create/mock): replays a designer-flow run with fake timings ----------

const MOCK_IMAGE = '/assets/competitors/spotify_car.webp' // stand-in for a finished PNG
const MOCK_AXES = ['faithful', 'hero', 'palette']
const MOCK_QUESTIONS = [
  'Which Xero product should this ad lead with?',
  'Any proof point (customer count, trial length) you want on the card?',
]
const MOCK_ANSWERS = ['Xero Payroll', '']

const MOCK_NAMES = ['Closest match', 'Hero image', 'Brand palette']

const MOCK_DIRECTIONS: VariantDirection[] = [
  {
    axis: 'faithful',
    changes: [],
    funnel: 'top',
    background: { type: 'template', text_area: 'bottom' },
    layout: 'image_top',
    text_holder: 'white_card',
    visual: {
      type: 'generated_scene',
      subject: 'small business owner',
      style: 'photo',
      treatment: 'in_bloom',
    },
    blooms: [{ colour: 'blue', scale: 1.2, bleed: ['left', 'right'], role: 'frame' }],
    proof: 'none',
    logo: { corner: 'bottom_left', on: 'white', pill: false },
    charms: 1,
    reasons: [
      'Top-of-funnel ads lead with a lifestyle photo',
      'Photos sit inside a bloom, never a hard rectangle',
      'Headline on a white card for contrast over the template',
    ],
  },
  {
    axis: 'hero',
    changes: ['illustration instead of photo', 'framed bloom'],
    funnel: 'top',
    background: { type: 'white' },
    layout: 'image_top',
    text_holder: 'none',
    visual: {
      type: 'generated_scene',
      style: 'flat_illustration',
      treatment: 'framed_bloom_break',
    },
    blooms: [{ colour: 'blue', scale: 1, bleed: ['right'], role: 'frame' }],
    proof: 'none',
    logo: { corner: 'bottom_left', on: 'white', pill: false },
    charms: 1,
    reasons: ['Illustrations may break out of a framed bloom', 'White background needs no text card'],
  },
  {
    axis: 'palette',
    changes: ['navy background', 'navy card'],
    funnel: 'mid',
    background: { type: 'navy' },
    layout: 'image_top',
    text_holder: 'navy_card',
    visual: { type: 'product_ui', treatment: 'plain' },
    blooms: [{ colour: 'blue', scale: 1.1, bleed: ['left'], role: 'accent' }],
    proof: 'free_trial',
    logo: { corner: 'bottom_left', on: 'navy', pill: false },
    charms: 0,
    reasons: ['Mid-funnel ads show the product', 'On navy, the CTA uses brand blue', 'White logo on dark backgrounds'],
  },
]

const MOCK_REVIEWS: VariantReview[] = [
  {
    fixed: ['Logo moved off the image edge', 'Headline set in brand navy'],
    issues: [],
    suggestions: ['Try a shorter headline'],
  },
  {
    fixed: ['CTA pill recoloured to brand navy'],
    issues: ['Illustration is not from the brand kit'],
    suggestions: [],
  },
  { fixed: [], issues: [], suggestions: [] },
]

function mockJob(onEvent: (e: JobEvent) => void) {
  const script: [number, JobEvent][] = [
    [
      100,
      {
        type: 'start',
        n: 3,
        source: MOCK_IMAGE,
        steps: [
          { id: 'plan', label: 'Art directing: backgrounds, pieces and copy' },
          { id: 'pictures', label: 'Making the main pictures' },
          { id: 'compose', label: 'Composing the versions' },
          { id: 'publish', label: 'Saving designs' },
          { id: 'review', label: 'Checking brand rules' },
        ],
      },
    ],
    [300, { type: 'step', id: 'plan', status: 'running' }],
    [
      1800,
      {
        type: 'step',
        id: 'plan',
        status: 'done',
        secs: 1.5,
        detail: '3 directions, 2 questions',
      },
    ],
    // The job now waits for the user; the real backend blocks until POST /answers.
    [1900, { type: 'questions', questions: MOCK_QUESTIONS }],
    [4900, { type: 'answered', answers: MOCK_ANSWERS }],
    [5000, { type: 'step', id: 'pictures', status: 'running' }],
    [
      6800,
      {
        type: 'step',
        id: 'pictures',
        status: 'done',
        secs: 1.8,
        detail: '3 hero pictures',
      },
    ],
    [6900, { type: 'step', id: 'compose', status: 'running' }],
  ]
  MOCK_AXES.forEach((axis, index) =>
    script.push([
      7200 + index * 600,
      {
        type: 'variant',
        index,
        axis,
        name: `Spotify car · ${MOCK_NAMES[index]}`,
        design_id: `d-ad-spotify-car-${index}`,
        layout: null,
        image: MOCK_IMAGE,
        width: 1024,
        height: 1024,
        review: null,
        direction: MOCK_DIRECTIONS[index],
      },
    ]),
  )
  script.push([
    8500,
    {
      type: 'step',
      id: 'compose',
      status: 'done',
      secs: 1.6,
      detail: '3 versions',
    },
  ])
  script.push([8600, { type: 'step', id: 'publish', status: 'running' }])
  script.push([
    9200,
    {
      type: 'step',
      id: 'publish',
      status: 'done',
      secs: 0.6,
      detail: '3 designs saved',
    },
  ])
  script.push([9300, { type: 'step', id: 'review', status: 'running' }])
  MOCK_AXES.forEach((_, index) =>
    script.push([
      10300 + index * 700,
      {
        type: 'review',
        index,
        design_id: `d-ad-spotify-car-${index}`,
        review: MOCK_REVIEWS[index],
      },
    ]),
  )
  script.push([
    12000,
    {
      type: 'step',
      id: 'review',
      status: 'done',
      secs: 2.7,
      detail: '3 fixed · 1 need you',
    },
  ])
  script.push([12100, { type: 'done' }])
  const timers = script.map(([ms, e]) => setTimeout(() => onEvent(e), ms))
  return () => timers.forEach(clearTimeout)
}
