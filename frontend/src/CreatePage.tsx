import { useEffect, useRef, useState } from 'react'
import { AlertCircle, Check, Circle, Loader2, MessageCircleQuestion, PenLine } from 'lucide-react'
import { Editor } from './editor/Editor'
import { importLayout, type SolvedLayout } from './editor/importLayout'
import {
  answerJob,
  expectedVariants,
  watchJob,
  type JobEvent,
  type JobStep,
  type VariantDirection,
  type VariantReview,
} from './jobs'

const DESIGN_W = 1080
const DESIGN_H = 1350

type StepStatus = 'pending' | 'running' | 'done' | 'error'
interface StepState extends JobStep {
  status: StepStatus
  detail?: string
  secs?: number
  startedAt?: number
}
type Variant = Extract<JobEvent, { type: 'variant' }> & {
  reviewFailed?: boolean
}
type ReviewPhase = 'none' | 'pending' | 'unchecked'

const WAITING_HINT = 'Waiting for your answers'

/** Live progress of one ad → Xero designs job. */
export function CreatePage({ jobId }: { jobId: string }) {
  const [source, setSource] = useState<string | null>(null)
  const [steps, setSteps] = useState<StepState[]>([])
  const [variants, setVariants] = useState<Variant[]>([])
  const [questions, setQuestions] = useState<string[] | null>(null)
  const [answers, setAnswers] = useState<string[] | null>(null)
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
          setQuestions(null)
          setAnswers(null)
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
        } else if (e.type === 'questions') {
          setQuestions(e.questions)
        } else if (e.type === 'answered') {
          setAnswers(e.answers)
        } else if (e.type === 'variant') {
          setVariants((all) => [...all.filter((v) => v.index !== e.index), e].sort((a, b) => a.index - b.index))
        } else if (e.type === 'review') {
          setVariants((all) =>
            all.map((v) =>
              v.index !== e.index
                ? v
                : {
                    ...v,
                    review: e.review,
                    reviewFailed: !e.review,
                    layout: e.layout ?? v.layout,
                  },
            ),
          )
        } else if (e.type === 'done') {
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
  // The art director asked and nobody has answered yet: the job is paused on the user.
  const awaiting = !!questions && !answers && !done
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
          <div className="create-source">{source ? <img src={source} alt="Your ad" /> : <div className="shimmer" />}</div>
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
            {awaiting && (
              <li className="step waiting">
                <MessageCircleQuestion size={18} className="step-icon" />
                <div className="step-text">
                  <div className="step-label">{WAITING_HINT}</div>
                </div>
              </li>
            )}
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

          {questions && !answers && !failed && <QuestionsCard jobId={jobId} questions={questions} />}
          {questions && answers && <AnswersCard questions={questions} answers={answers} />}

          <div className="variant-grid">
            {Array.from({ length: slots }, (_, i) => {
              const v = variants.find((x) => x.index === i) ?? variants[i]
              if (v) return <VariantCard key={v.design_id} variant={v} reviewPhase={reviewPhase(v)} />
              if (failed) return null
              return (
                <div key={`slot-${i}`} className="variant-card">
                  <div className="variant-preview shimmer">
                    <span>{awaiting ? `${WAITING_HINT}…` : running ? `${running.label}…` : 'Waiting…'}</span>
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

/** The art director's questions: one input each. Inputs lock while sending; the `answered`
 *  event (not the POST response) swaps this for the read-only view, so replay stays in sync. */
function QuestionsCard({ jobId, questions }: { jobId: string; questions: string[] }) {
  const [drafts, setDrafts] = useState<string[]>(() => questions.map(() => ''))
  const [sending, setSending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const send = async (answers: string[]) => {
    setSending(true)
    setError(null)
    try {
      await answerJob(jobId, answers)
      // Stay disabled: the `answered` event replaces this card.
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't send answers")
      setSending(false)
    }
  }

  return (
    <form
      className="questions-card"
      onSubmit={(e) => {
        e.preventDefault()
        void send(drafts)
      }}
    >
      <div className="questions-title">
        <MessageCircleQuestion size={18} />
        The art director has a few questions
      </div>
      <p className="muted questions-hint">Your answers shape the copy and pictures. Skip if you'd rather let it decide.</p>
      <ol className="questions-list">
        {questions.map((q, i) => (
          <li key={i}>
            <label>
              <span className="question-text">{q}</span>
              <input
                type="text"
                value={drafts[i]}
                disabled={sending}
                placeholder="Your answer"
                onChange={(e) => setDrafts((d) => d.map((x, j) => (j === i ? e.target.value : x)))}
              />
            </label>
          </li>
        ))}
      </ol>
      {error && (
        <div className="questions-error">
          <AlertCircle size={16} /> {error}
        </div>
      )}
      <div className="questions-actions">
        <button type="submit" className="upload-btn" disabled={sending}>
          {sending ? <Loader2 size={16} className="spin" /> : null}
          {sending ? 'Sending…' : 'Send answers'}
        </button>
        <button type="button" className="link-btn" disabled={sending} onClick={() => void send(questions.map(() => ''))}>
          Skip
        </button>
      </div>
    </form>
  )
}

/** Read-only questions + answers once they've been sent. */
function AnswersCard({ questions, answers }: { questions: string[]; answers: string[] }) {
  return (
    <div className="questions-card answered">
      <div className="questions-title">
        <Check size={18} />
        Your answers to the art director
      </div>
      <ol className="questions-list">
        {questions.map((q, i) => {
          const a = answers[i]?.trim()
          return (
            <li key={i}>
              <span className="question-text">{q}</span>
              <span className={`answer-text${a ? '' : ' skipped'}`}>{a || 'skipped'}</span>
            </li>
          )
        })}
      </ol>
    </div>
  )
}

function VariantCard({ variant, reviewPhase }: { variant: Variant; reviewPhase: ReviewPhase }) {
  return (
    <div className="variant-card ready">
      {variant.image ? (
        <div className="variant-preview">
          <img src={variant.image} alt={variant.name} width={variant.width} height={variant.height} />
        </div>
      ) : variant.layout ? (
        <LayoutPreview layout={variant.layout} />
      ) : (
        <div className="variant-preview shimmer" />
      )}
      <div className="variant-meta">
        <div className="design-name">{variant.name}</div>
        {variant.direction && <DirectionSummary direction={variant.direction} />}
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

const TREATMENTS: Record<string, string> = {
  in_bloom: 'in bloom',
  framed_bloom_break: 'framed, bloom breaks frame',
  cutout_on_bloom: 'cut-out on bloom',
  plain: '',
}
const BACKGROUNDS: Record<string, string> = {
  template: 'Wave template',
  navy: 'Navy background',
  white: 'White background',
  pattern: 'Bloom pattern',
}
const TEXT_HOLDERS: Record<string, string> = {
  none: 'No card',
  white_card: 'White card',
  navy_card: 'Navy card',
}
const FUNNELS: Record<string, string> = {
  top: 'Top of funnel',
  mid: 'Mid funnel',
  bottom: 'Bottom of funnel',
}

/** Unknown enum value → readable words. */
const humanize = (v: string) => {
  const s = v.replace(/_/g, ' ').trim()
  return s.charAt(0).toUpperCase() + s.slice(1)
}

/** Enum field → label via a lookup table, or humanized; '' when the field is absent. */
const labelOf = (table: Record<string, string>, v: string | undefined) => (v ? (table[v] ?? humanize(v)) : '')

function visualLabel(visual: VariantDirection['visual']): string {
  const { type, style, treatment } = visual ?? {}
  if (!type) return ''
  if (type === 'charms_only') return 'Charms only'
  if (type === 'none') return 'Text only'
  const base =
    type === 'generated_scene'
      ? style === 'photo'
        ? 'Photo'
        : style === 'flat_illustration'
          ? 'Illustration'
          : 'Scene'
      : type === 'product_ui'
        ? 'Product UI'
        : humanize(type)
  const how = treatment ? (TREATMENTS[treatment] ?? treatment.replace(/_/g, ' ')) : ''
  return how ? `${base} ${how}` : base
}

/** Art-direction chips; click for the guidelines behind them. Every field is optional. */
function DirectionSummary({ direction: d }: { direction: VariantDirection }) {
  const reasons = d.reasons ?? []
  const changes = d.changes ?? []
  const chips = [
    visualLabel(d.visual),
    labelOf(BACKGROUNDS, d.background?.type),
    labelOf(TEXT_HOLDERS, d.text_holder),
    labelOf(FUNNELS, d.funnel),
  ].filter(Boolean)
  const hasDetail = reasons.length > 0 || changes.length > 0
  if (chips.length === 0 && !hasDetail) return null
  const summary = (
    <span className="review-chips">
      {chips.map((c) => (
        <span key={c} className="review-chip design-chip">
          {c}
        </span>
      ))}
    </span>
  )
  const title = <span className="review-list-title design-title">How it was designed</span>
  if (!hasDetail)
    return (
      <div className="review">
        {title}
        {summary}
      </div>
    )
  return (
    <details className="review">
      <summary>
        {title}
        {summary}
      </summary>
      {reasons.length > 0 && (
        <div className="review-list">
          <div className="review-list-title">Guidelines followed</div>
          <ul>
            {reasons.map((r, i) => (
              <li key={i}>{r}</li>
            ))}
          </ul>
        </div>
      )}
      {changes.length > 0 && <div className="review-list">Changed from closest match: {changes.join(', ')}</div>}
    </details>
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
