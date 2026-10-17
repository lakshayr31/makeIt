import { useEffect, useRef, useState } from 'react'
import { ArrowUp, ImagePlus, Loader2, Plus, X } from 'lucide-react'
import { createJob, readAsDataUrl } from '../jobs'

const EXAMPLES = [
  'Make it about Xero payroll: pay your team in a few clicks',
  'Show a plumber sending a quote from their van',
  'Swap the illustration for a café owner checking invoices',
  'Navy background with a cyan "Try Xero free" button',
  'Headline under 6 words, e.g. "Get paid twice as fast"',
  'Just 1 version, as close to the original as possible',
]
const EXAMPLE_MS = 3500

/** Start screen for creating: attach an ad, optionally say what you want, get 3 Xero versions. */
export function UploadDialog({ onClose }: { onClose: () => void }) {
  const [image, setImage] = useState<string | null>(null)
  const [prompt, setPrompt] = useState('')
  const [dragging, setDragging] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const fileInput = useRef<HTMLInputElement>(null)
  const textInput = useRef<HTMLTextAreaElement>(null)
  const [example, setExample] = useState(0)

  // One example prompt at a time, rotating, so people see what they can ask for.
  useEffect(() => {
    const timer = setInterval(() => setExample((i) => (i + 1) % EXAMPLES.length), EXAMPLE_MS)
    return () => clearInterval(timer)
  }, [])

  const takeFile = async (file: File | undefined | null) => {
    if (!file) return
    if (!file.type.startsWith('image/')) return setError('That file isn’t an image.')
    setError(null)
    setImage(await readAsDataUrl(file))
    textInput.current?.focus()
  }

  // Paste an image from the clipboard; Esc closes.
  useEffect(() => {
    const onPaste = (e: ClipboardEvent) => {
      const item = [...(e.clipboardData?.items ?? [])].find((i) => i.type.startsWith('image/'))
      if (item) takeFile(item.getAsFile())
    }
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && !busy && onClose()
    window.addEventListener('paste', onPaste)
    window.addEventListener('keydown', onKey)
    return () => {
      window.removeEventListener('paste', onPaste)
      window.removeEventListener('keydown', onKey)
    }
  }, [busy, onClose])

  useEffect(() => textInput.current?.focus(), [])

  const submit = async () => {
    if (busy) return
    if (!image) return setError('Add an image to build from first.')
    setBusy(true)
    setError(null)
    try {
      const id = await createJob(image, prompt.trim())
      window.location.hash = `#/create/${id}`
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Something went wrong.')
      setBusy(false)
    }
  }


  return (
    <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && !busy && onClose()}>
      <div
        className={`modal start${dragging ? ' over' : ''}`}
        role="dialog"
        aria-label="What do you want to make?"
        onDragOver={(e) => {
          e.preventDefault()
          setDragging(true)
        }}
        onDragLeave={(e) => e.currentTarget === e.target && setDragging(false)}
        onDrop={(e) => {
          e.preventDefault()
          setDragging(false)
          takeFile(e.dataTransfer.files[0])
        }}
      >
        <button className="icon-btn start-close" title="Close" onClick={onClose} disabled={busy}>
          <X size={18} />
        </button>

        <h2 className="start-title">What do you want to make?</h2>
        <p className="start-sub">Add an ad or image to build from, then tell makeIt what to change.</p>

        <p className="start-example" aria-live="polite">
          Try: <span key={example}>“{EXAMPLES[example]}”</span>
        </p>

        <div className="composer">
          {image ? (
            <div className="composer-attachment">
              <img src={image} alt="Image to build from" />
              <button title="Remove image" onClick={() => setImage(null)} disabled={busy}>
                <X size={12} />
              </button>
            </div>
          ) : (
            <button className="composer-drop" onClick={() => fileInput.current?.click()} disabled={busy}>
              <ImagePlus size={18} /> Drop, paste (⌘V) or click to add an image
            </button>
          )}
          <div className="composer-row">
            <button className="composer-add" title="Add an image" onClick={() => fileInput.current?.click()} disabled={busy}>
              <Plus size={20} />
            </button>
            <textarea
              ref={textInput}
              rows={1}
              value={prompt}
              placeholder="Describe what you want (optional)"
              onChange={(e) => setPrompt(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  submit()
                }
              }}
              disabled={busy}
            />
            <button
              className="composer-send"
              title="Create Xero versions"
              onClick={submit}
              disabled={busy || !image}
            >
              {busy ? <Loader2 size={18} className="spin" /> : <ArrowUp size={20} />}
            </button>
          </div>
          <input
            ref={fileInput}
            type="file"
            accept="image/*"
            hidden
            onChange={(e) => {
              takeFile(e.target.files?.[0])
              e.target.value = ''
            }}
          />
        </div>

        {error && <p className="modal-error">{error}</p>}

        <p className="start-note">makeIt makes 3 versions. Ask for a different number in your message.</p>

      </div>
    </div>
  )
}
