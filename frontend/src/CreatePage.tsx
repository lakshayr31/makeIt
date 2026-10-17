import { useEffect, useRef, useState } from 'react'
import { AlertCircle, Check, Circle, Loader2, PenLine } from 'lucide-react'
import { Editor } from './editor/Editor'
import { importLayout, type SolvedLayout } from './editor/importLayout'
import { expectedVariants, watchJob, type JobEvent, type JobStep, type VariantReview } from './jobs'

const DESIGN_W = 1080
const DESIGN_H = 1350

type StepStatus = 'pending' | 'running' | 'done' | 'error'
interface StepState extends JobStep {
  status: StepStatus
  detail?: string
  secs?: number
  startedAt?: number
}
type Variant = Extract<JobEvent, { type: 'variant' }> & { reviewFailed?: boolean }
type ReviewPhase = 'none' | 'pending' | 'unchecked'

/** Live progress of one ad → Xero designs job. */
export function CreatePage({ jobId }: { jobId: string }) {
  const [source, setSource] = useState<string | null>(null)
  const [steps, setSteps] = useState<StepState[]>([])
  const [variants, setVariants] = useState<Variant[]>([])
  const [done, setDone] = useState<{ error: boolean } | null>(null)
  const [expected, setExpected] = useState(() => expectedVariants(jobId))
  const [, setNow] = useState(0)

  useEffect(
    () =>
      watchJob(jobId, (e) => {
        if (e.type === 'start') {
          setSource(e.source)
          setExpected(expectedVariants(jobId, e.n))
          setSteps(e.steps.map((s) => ({ ...s, status: 'pending' })))
          setVariants([])
        } else if (e.type === 'step') {
          setSteps((all) =>
            all.map((s) =>
              s.id !== e.id
                ? s
                : {
                    ...s,
                    status: e.status,
                    detail: e.detail ?? s.detail,
                    secs: e.secs ?? s.secs,
                    startedAt: e.status === 'running' ? (e.t ? e.t * 1000 : Date.now()) : s.startedAt,
                  },
            ),
          )
        } else if (e.type === 'variant') {
          setVariants((all) => [...all.filter((v) => v.index !== e.index), e].sort((a, b) => a.index - b.index))
        } else if (e.type === 'review') {
          setVariants((all) =>
            all.map((v) =>
              v.index !== e.index
                ? v
                : { ...v, review: e.review, reviewFailed: !e.review, layout: e.layout ?? v.layout },
            ),
          )
        } else {
          setDone({ error: !!e.error })
        }
      }),
    [jobId],
  )

  // Tick the running step's seconds counter.
  const running = steps.find((s) => s.status === 'running')
  useEffect(() => {
    if (!running) return
    const t = setInterval(() => setNow(Date.now()), 500)
    return () => clearInterval(t)
  }, [running])

  const failed = done?.error || steps.some((s) => s.status === 'error')
  const errorStep = steps.find((s) => s.status === 'error')
  const slots = done ? variants.length : Math.max(expected, variants.length)
  // Card chip for a variant still without a review: pending while the check can still report.
  const reviewStep = steps.find((s) => s.id === 'review')
  const reviewOver = !!done || reviewStep?.status === 'done' || reviewStep?.status === 'error'
  const reviewPhase = (v: Variant): ReviewPhase =>
    !reviewStep || v.review ? 'none' : v.reviewFailed || reviewOver ? 'unchecked' : 'pending'

  return (
    <div className="home create">
      <header className="header">
        <span className="logo" onClick={() => (window.location.hash = '#/')}>
          makeIt
        </span>
        <span className="title">Creating Xero versions</span>
      </header>

      <main className="create-body">
        <aside className="create-side">
          <div className="create-source">
            {source ? <img src={source} alt="Your ad" /> : <div className="shimmer" />}
          </div>
          <ol className="steps">
            {steps.length === 0 && <li className="muted">Connecting…</li>}
            {steps.map((s) => (
              <li key={s.id} className={`step ${s.status}`}>
                <StepIcon status={s.status} />
                <div className="step-text">
                  <div className="step-label">
                    {s.label}
                    <span className="step-secs">{stepSecs(s)}</span>
                  </div>
                  {s.detail && <div className="muted">{s.detail}</div>}
                </div>
              </li>
            ))}
          </ol>
        </aside>

        <section className="create-results">
          <h2>{done && !failed ? `${variants.length} designs ready` : failed ? 'Something went wrong' : 'Your designs'}</h2>

          {failed && (
            <div className="create-error">
              <AlertCircle size={18} />
              <div>
                <strong>{errorStep ? `${errorStep.label} failed` : 'The job stopped early'}</strong>
                {errorStep?.detail && <div>{errorStep.detail}</div>}
              </div>
              <button className="upload-btn" onClick={() => (window.location.hash = '#/')}>
                Try again
              </button>
            </div>
          )}

          <div className="variant-grid">
            {Array.from({ length: slots }, (_, i) => {
              const v = variants.find((x) => x.index === i) ?? variants[i]
              if (v) return <VariantCard key={v.design_id} variant={v} reviewPhase={reviewPhase(v)} />
              if (failed) return null
              return (
                <div key={`slot-${i}`} className="variant-card">
                  <div className="variant-preview shimmer">
                    <span>{running ? `${running.label}…` : 'Waiting…'}</span>
                  </div>
                  <div className="variant-meta muted">Version {i + 1}</div>
                </div>
              )
            })}
          </div>
        </section>
      </main>
    </div>
  )
}

function stepSecs(s: StepState) {
  if (s.secs != null) return `${s.secs.toFixed(1)}s`
  if (s.status === 'running' && s.startedAt) return `${Math.floor((Date.now() - s.startedAt) / 1000)}s`
  return ''
}

function StepIcon({ status }: { status: StepStatus }) {
  if (status === 'running') return <Loader2 size={18} className="spin step-icon" />
  if (status === 'done') return <Check size={18} className="step-icon" />
  if (status === 'error') return <AlertCircle size={18} className="step-icon" />
  return <Circle size={18} className="step-icon" />
}

function VariantCard({ variant, reviewPhase }: { variant: Variant; reviewPhase: ReviewPhase }) {
  return (
    <div className="variant-card ready">
      <LayoutPreview layout={variant.layout} />
      <div className="variant-meta">
        <div className="design-name">{variant.name}</div>
        {variant.review && <ReviewSummary review={variant.review} />}
        {reviewPhase === 'pending' && (
          <div className="review">
            <span className="review-chip pending">
              <span className="pulse-dot" /> Checking brand rules…
            </span>
          </div>
        )}
        {reviewPhase === 'unchecked' && (
          <div className="review">
            <span className="review-chip muted-chip">Not checked</span>
          </div>
        )}
        <button className="upload-btn" onClick={() => (window.location.hash = `#/design/${variant.design_id}`)}>
          <PenLine size={16} /> Open in editor
        </button>
      </div>
    </div>
  )
}

/** Brand-check chips; click to see the messages behind them. */
function ReviewSummary({ review }: { review: VariantReview }) {
  const fixed = review.fixed.length
  const open = review.issues.length
  const lists: [string, string[]][] = [
    ['Fixed', review.fixed],
    ['Needs you', review.issues],
    ['Suggestions', review.suggestions],
  ]
  const hasDetail = lists.some(([, items]) => items.length > 0)
  const chips = (
    <span className="review-chips">
      {fixed > 0 && <span className="review-chip ok">✓ {fixed} fixed</span>}
      {open > 0 && <span className="review-chip warn">{open} need you</span>}
      {fixed === 0 && open === 0 && <span className="review-chip ok">Passes brand check</span>}
    </span>
  )
  if (!hasDetail) return <div className="review">{chips}</div>
  return (
    <details className="review">
      <summary>{chips}</summary>
      {lists.map(([title, items]) =>
        items.length === 0 ? null : (
          <div key={title} className="review-list">
            <div className="review-list-title">{title}</div>
            <ul>
              {items.map((m, i) => (
                <li key={i}>{m}</li>
              ))}
            </ul>
          </div>
        ),
      )}
    </details>
  )
}

/** A read-only Fabric render of a solved layout, scaled to its box. */
function LayoutPreview({ layout }: { layout: SolvedLayout }) {
  const box = useRef<HTMLDivElement>(null)
  const [ready, setReady] = useState(false)

  useEffect(() => {
    const host = box.current!
    // Fabric wraps the <canvas> in its own div, so keep it out of React's tree.
    const el = document.createElement('canvas')
    host.appendChild(el)
    const ed = new Editor(el, DESIGN_W, DESIGN_H)
    const wrapper = host.lastElementChild // Fabric's wrapper around el
    ed.canvas.selection = false
    setReady(false)
    const fit = () => ed.fit(host.clientWidth, host.clientHeight)
    fit()
    const ro = new ResizeObserver(fit)
    ro.observe(host)

    let cancelled = false
    importLayout(ed, layout)
      .then(() => {
        if (cancelled) return
        ed.canvas.getObjects().forEach((o) => o.set({ selectable: false, evented: false }))
        ed.canvas.requestRenderAll()
        setReady(true)
      })
      .catch(() => !cancelled && setReady(true))

    return () => {
      cancelled = true
      ro.disconnect()
      // Remove only our nodes (dispose restores el): a newer layout may already be mounted.
      ed.canvas.dispose().finally(() => {
        wrapper?.remove()
        el.remove()
      })
    }
  }, [layout])

  return <div ref={box} className={`variant-preview${ready ? '' : ' shimmer'}`} />
}
