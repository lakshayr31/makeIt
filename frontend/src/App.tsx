import { useEffect, useState } from 'react'
import { EditorPage } from './EditorPage'
import { HomePage } from './HomePage'

const parseRoute = () => window.location.hash.match(/^#\/design\/([a-z0-9-]+)$/)?.[1] ?? null

/** Two screens: the designs list (#/) and the editor (#/design/<id>). */
export function App() {
  const [designId, setDesignId] = useState(parseRoute)

  useEffect(() => {
    const onHash = () => setDesignId(parseRoute())
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])

  return designId ? <EditorPage key={designId} designId={designId} /> : <HomePage />
}
