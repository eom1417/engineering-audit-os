// The Studio's routes on hash history, so a link like #/problems?card=TASK-001 restores its view and works from a
// file. Unbuilt sections have no route unless the developer flag is on (shell/sections.ts).
import { createHashHistory, createRootRoute, createRoute, createRouter, redirect, useSearch } from '@tanstack/react-router'
import { ChangePage } from './pages/Change'
import { BridgePage } from './pages/change/BridgePage'
import { OpPage, StepPage, TaskPage } from './pages/change/DetailPages'
import { GapPage, GapsPage } from './pages/change/GapsPage'
import { PlanPage, PlansPage } from './pages/change/PlansPage'
import { DataPathsPage } from './pages/data/DataPaths'
import { InfraLensPage } from './pages/infra/InfraLens'
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
import { HiddenPage } from './pages/system/hidden/HiddenPage'
import { JourneysPage } from './pages/system/journeys/JourneysPage'
import { RunPage } from './pages/runs/RunPage'
import { RunsPage } from './pages/runs/RunsPage'
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

/** #/system shows the territory map, or the lens the address names (?lens=infra). */
function SystemRoute() {
  const { lens } = useSearch({ strict: false }) as { lens?: string }
  return lens === 'infra' ? <InfraLensPage /> : <SystemMapPage />
}

function devOnly(id: string, dev: () => boolean) {
  return () => {
    if (!SECTIONS.find((s) => s.id === id)?.built && !dev()) throw redirect({ to: '/' })
  }
}

export function makeRouter(dev: () => boolean) {
  const tree = root.addChildren([
    createRoute({ getParentRoute: () => root, path: '/', component: HomePage }),
    createRoute({ getParentRoute: () => root, path: '/system', component: SystemRoute, validateSearch: params('focus', 'view', 'show', 'op', 'hidden', 'lens', 'item') }),
    createRoute({ getParentRoute: () => root, path: '/system/paths', component: PathsPage, validateSearch: params('view', 'cluster', 'q', 'filter', 'file', 'part') }),
    createRoute({ getParentRoute: () => root, path: '/system/journeys', component: JourneysPage, validateSearch: params('view', 'show', 'task', 'focus', 'hidden', 'flag', 'area') }),
    createRoute({ getParentRoute: () => root, path: '/system/hidden', component: HiddenPage, validateSearch: params('focus', 'only', 'hidden') }),
    createRoute({ getParentRoute: () => root, path: '/system/data', component: DataPathsPage, validateSearch: params('view', 'store', 'show', 'reads') }),
    createRoute({ getParentRoute: () => root, path: '/system/pipeline', component: PipelinePage, validateSearch: params('p', 'view', 'show', 'stage', 'hidden', 'follow') }),
    createRoute({ getParentRoute: () => root, path: '/flows/$pathId', component: FlowPage, validateSearch: params('view', 'show', 'node', 'traced') }),
    createRoute({ getParentRoute: () => root, path: '/problems', component: ProblemsPage, validateSearch: params('card', 'who', 'severity', 'component', 'q') }),
    createRoute({ getParentRoute: () => root, path: '/change', component: ChangePage, validateSearch: params('focus', 'side') }),
    createRoute({ getParentRoute: () => root, path: '/change/timeline', component: TimelinePage, validateSearch: params('step', 'wave') }),
    createRoute({ getParentRoute: () => root, path: '/change/bridge', component: BridgePage, validateSearch: params('view') }),
    createRoute({ getParentRoute: () => root, path: '/change/gaps', component: GapsPage, validateSearch: params('relation') }),
    createRoute({ getParentRoute: () => root, path: '/change/gaps/$gapId', component: GapPage }),
    createRoute({ getParentRoute: () => root, path: '/plans', component: PlansPage }),
    createRoute({ getParentRoute: () => root, path: '/plans/$planId', component: PlanPage, validateSearch: params('view') }),
    createRoute({ getParentRoute: () => root, path: '/plans/$planId/$stepId', component: StepPage }),
    createRoute({ getParentRoute: () => root, path: '/tasks/$taskId', component: TaskPage }),
    createRoute({ getParentRoute: () => root, path: '/ops/$opId', component: OpPage }),
    createRoute({ getParentRoute: () => root, path: '/decisions', component: DecisionsPage, validateSearch: params('demo') }),
    createRoute({ getParentRoute: () => root, path: '/runs', component: RunsPage, validateSearch: params('q', 'show', 'demo') }),
    createRoute({ getParentRoute: () => root, path: '/runs/$runId', component: RunPage, validateSearch: params('demo') }),
    createRoute({ getParentRoute: () => root, path: '/library', component: LibraryPage, beforeLoad: devOnly('library', dev) }),
    createRoute({ getParentRoute: () => root, path: '/_gallery', component: GalleryPage, validateSearch: params('view', 'card') }),
    createRoute({ getParentRoute: () => root, path: '/_gallery/paths', component: PathsGalleryPage }),
    createRoute({ getParentRoute: () => root, path: '/_gallery/pipeline', component: PipelineGalleryPage }),
  ])
  return createRouter({ routeTree: tree, history: createHashHistory(), defaultNotFoundComponent: () => { throw redirect({ to: '/' }) }, scrollRestoration: false })
}
