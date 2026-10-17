import { useEffect, useState } from 'react'
import { EditorPage } from './EditorPage'
import { HomePage } from './HomePage'
import { CreatePage } from './CreatePage'

type Route = { page: 'home' } | { page: 'design'; id: string } | { page: 'create'; id: string }

const parseRoute = (): Route => {
  const m = window.location.hash.match(/^#\/(design|create)\/([A-Za-z0-9_-]+)$/)
  return m ? { page: m[1] as 'design' | 'create', id: m[2] } : { page: 'home' }
}

/** Screens: designs list (#/), editor (#/design/<id>), ad → designs job (#/create/<jobId>). */
export function App() {
  const [route, setRoute] = useState(parseRoute)

  useEffect(() => {
    const onHash = () => setRoute(parseRoute())
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])

  if (route.page === 'design') return <EditorPage key={route.id} designId={route.id} />
  if (route.page === 'create') return <CreatePage key={route.id} jobId={route.id} />
  return <HomePage />
}
