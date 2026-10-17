import { useEffect, useState } from 'react'
import { EditorPage } from './EditorPage'
import { HomePage } from './HomePage'
import { CreatePage } from './CreatePage'
import { BrandPage } from './BrandPage'

type Route =
  | { page: 'home' }
  | { page: 'design'; id: string }
  | { page: 'create'; id: string }
  | { page: 'brand'; topic?: string }

const parseRoute = (): Route => {
  const b = window.location.hash.match(/^#\/brand(?:\/([A-Za-z0-9_-]+))?\/?$/)
  if (b) return { page: 'brand', topic: b[1] }
  const m = window.location.hash.match(/^#\/(design|create)\/([A-Za-z0-9_-]+)$/)
  return m ? { page: m[1] as 'design' | 'create', id: m[2] } : { page: 'home' }
}

/** Screens: designs list (#/), editor (#/design/<id>), ad → designs job (#/create/<jobId>),
 *  brand guidelines (#/brand[/<topicId>]). */
export function App() {
  const [route, setRoute] = useState(parseRoute)

  useEffect(() => {
    const onHash = () => setRoute(parseRoute())
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])

  if (route.page === 'design') return <EditorPage key={route.id} designId={route.id} />
  if (route.page === 'create') return <CreatePage key={route.id} jobId={route.id} />
  if (route.page === 'brand') return <BrandPage initialTopic={route.topic} />
  return <HomePage />
}
