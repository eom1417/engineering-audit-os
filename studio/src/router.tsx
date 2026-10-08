// The Studio's routes on hash history, so a link like #/problems?card=TASK-001 restores its view and works from a
// file. Unbuilt sections have no route unless the developer flag is on (shell/sections.ts).
import { createHashHistory, createRootRoute, createRoute, createRouter, redirect } from '@tanstack/react-router'
import { ChangePage } from './pages/Change'
import { DecisionsPage } from './pages/Decisions'
import { HomePage } from './pages/Home'
import { LibraryPage } from './pages/Library'
import { ProblemsPage } from './pages/Problems'
import { SystemMapPage } from './pages/SystemMap'
import { FlowPage } from './pages/paths/FlowPage'
import { PathsGalleryPage } from './pages/paths/PathsGallery'
import { PathsPage } from './pages/paths/PathsPage'
import { PipelineGalleryPage } from './pages/pipeline/PipelineGallery'
import { PipelinePage } from './pages/pipeline/PipelinePage'
import { TimelinePage } from './pages/paths/TimelinePage'
import { GalleryPage } from './gallery/Gallery'
import { Shell } from './shell/Shell'
import { SECTIONS } from './shell/sections'

type Params = Record<string, string | undefined>

/** Keeps the known search params as strings and drops the rest. */
function params(...names: string[]) {
  return (raw: Record<string, unknown>): Params => {
    const out: Params = {}
    for (const name of names) if (raw[name] !== undefined && raw[name] !== '') out[name] = String(raw[name])
    return out
  }
}

const root = createRootRoute({ component: Shell })

function devOnly(id: string, dev: () => boolean) {
  return () => {
    if (!SECTIONS.find((s) => s.id === id)?.built && !dev()) throw redirect({ to: '/' })
  }
}

export function makeRouter(dev: () => boolean) {
  const tree = root.addChildren([
    createRoute({ getParentRoute: () => root, path: '/', component: HomePage }),
    createRoute({ getParentRoute: () => root, path: '/system', component: SystemMapPage, validateSearch: params('focus', 'view', 'show', 'op') }),
    createRoute({ getParentRoute: () => root, path: '/system/paths', component: PathsPage, validateSearch: params('view', 'cluster', 'q', 'filter', 'file', 'part') }),
    createRoute({ getParentRoute: () => root, path: '/system/pipeline', component: PipelinePage, validateSearch: params('p', 'view', 'show', 'stage', 'hidden', 'follow') }),
    createRoute({ getParentRoute: () => root, path: '/flows/$pathId', component: FlowPage, validateSearch: params('view', 'show', 'node', 'traced') }),
    createRoute({ getParentRoute: () => root, path: '/problems', component: ProblemsPage, validateSearch: params('card', 'who', 'severity', 'component', 'q') }),
    createRoute({ getParentRoute: () => root, path: '/change', component: ChangePage, validateSearch: params('focus', 'side') }),
    createRoute({ getParentRoute: () => root, path: '/change/timeline', component: TimelinePage, validateSearch: params('step', 'wave') }),
    createRoute({ getParentRoute: () => root, path: '/decisions', component: DecisionsPage }),
    createRoute({ getParentRoute: () => root, path: '/library', component: LibraryPage, beforeLoad: devOnly('library', dev) }),
    createRoute({ getParentRoute: () => root, path: '/_gallery', component: GalleryPage, validateSearch: params('view', 'card') }),
    createRoute({ getParentRoute: () => root, path: '/_gallery/paths', component: PathsGalleryPage }),
    createRoute({ getParentRoute: () => root, path: '/_gallery/pipeline', component: PipelineGalleryPage }),
  ])
  return createRouter({ routeTree: tree, history: createHashHistory(), defaultNotFoundComponent: () => { throw redirect({ to: '/' }) }, scrollRestoration: false })
}
