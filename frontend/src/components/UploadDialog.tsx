import { useEffect, useRef, useState } from 'react'
import { ImagePlus, Loader2, Sparkles, X } from 'lucide-react'
import { createJob, readAsDataUrl } from '../jobs'
import { newDesignId, openDesign } from '../designs'

const VERSION_COUNTS = [1, 2, 3]

/** Drop in a competitor ad → start a job that makes Xero versions of it. */
export function UploadDialog({ onClose }: { onClose: () => void }) {
  const [image, setImage] = useState<string | null>(null)
  const [n, setN] = useState(3)
  const [dragging, setDragging] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const fileInput = useRef<HTMLInputElement>(null)

  const takeFile = async (file: File | undefined | null) => {
    if (!file) return
    if (!file.type.startsWith('image/')) return setError('That file isn’t an image.')
    setError(null)
    setImage(await readAsDataUrl(file))
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

  const submit = async () => {
    if (!image) return
    setBusy(true)
    setError(null)
    try {
      const id = await createJob(image, n)
      window.location.hash = `#/create/${id}`
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Something went wrong.')
      setBusy(false)
    }
  }

  return (
    <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && !busy && onClose()}>
      <div className="modal" role="dialog" aria-label="Create a design from an ad">
        <div className="modal-head">
          <h3>Create a design from an ad</h3>
          <button className="icon-btn" title="Close" onClick={onClose} disabled={busy}>
            <X size={18} />
          </button>
        </div>

        <div
          className={`dropzone${dragging ? ' over' : ''}${image ? ' has-image' : ''}`}
          onClick={() => fileInput.current?.click()}
          onDragOver={(e) => {
            e.preventDefault()
            setDragging(true)
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault()
            setDragging(false)
            takeFile(e.dataTransfer.files[0])
          }}
        >
          {image ? (
            <img src={image} alt="Your ad" />
          ) : (
            <div className="dropzone-empty">
              <ImagePlus size={32} />
              <strong>Drop an ad here</strong>
              <span className="muted">or click to choose a file, or paste with ⌘V</span>
            </div>
          )}
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
        {image && (
          <button className="link-btn" onClick={() => fileInput.current?.click()} disabled={busy}>
            Choose a different ad
          </button>
        )}

        <div className="versions">
          <span>How many versions</span>
          <div className="version-chips">
            {VERSION_COUNTS.map((c) => (
              <button key={c} className={c === n ? 'on' : ''} onClick={() => setN(c)} disabled={busy}>
                {c}
              </button>
            ))}
          </div>
        </div>

        {error && <p className="modal-error">{error}</p>}

        <button className="upload-btn" onClick={submit} disabled={!image || busy}>
          {busy ? <Loader2 size={16} className="spin" /> : <Sparkles size={16} />}
          {busy ? 'Starting…' : 'Create Xero versions'}
        </button>
        <button className="link-btn center" onClick={() => openDesign(newDesignId())} disabled={busy}>
          Start with a blank design
        </button>
      </div>
    </div>
  )
}
