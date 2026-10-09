// The Studio's routes on hash history, so a link like #/problems?card=TASK-001 restores its view and works from a
// file. Unbuilt sections have no route unless the developer flag is on (shell/sections.ts).
import { createHashHistory, createRootRoute, createRoute, createRouter, lazyRouteComponent, redirect, useSearch } from '@tanstack/react-router'
import { HomePage } from './pages/Home'
import { ProblemsPage } from './pages/problems/ProblemsPage'
import { SEARCH_KEYS as PROBLEM_KEYS } from './pages/problems/model'
import { PageLoading } from './shell/Layout'
import { Shell } from './shell/Shell'
import { SECTIONS } from './shell/sections'

// Every page but Home and Problems is its own chunk (vite.config.ts classicChunks), read when it is first opened or
// when a link to it is pointed at or touched (defaultPreload 'intent'); meanwhile the page shows its loading state.
const ChangePage = lazyRouteComponent(() => import('./pages/Change'), 'ChangePage')
const BridgePage = lazyRouteComponent(() => import('./pages/change/BridgePage'), 'BridgePage')
const OpPage = lazyRouteComponent(() => import('./pages/change/DetailPages'), 'OpPage')
const StepPage = lazyRouteComponent(() => import('./pages/change/DetailPages'), 'StepPage')
const TaskPage = lazyRouteComponent(() => import('./pages/change/DetailPages'), 'TaskPage')
const GapPage = lazyRouteComponent(() => import('./pages/change/GapsPage'), 'GapPage')
const GapsPage = lazyRouteComponent(() => import('./pages/change/GapsPage'), 'GapsPage')
const PlanPage = lazyRouteComponent(() => import('./pages/change/PlansPage'), 'PlanPage')
const PlansPage = lazyRouteComponent(() => import('./pages/change/PlansPage'), 'PlansPage')
const DataPathsPage = lazyRouteComponent(() => import('./pages/data/DataPaths'), 'DataPathsPage')
const InfraLensPage = lazyRouteComponent(() => import('./pages/infra/InfraLens'), 'InfraLensPage')
const IdealPage = lazyRouteComponent(() => import('./pages/ideal/IdealPage'), 'IdealPage')
const DecisionsPage = lazyRouteComponent(() => import('./pages/Decisions'), 'DecisionsPage')
const FunctionPage = lazyRouteComponent(() => import('./pages/functions/FunctionsPage'), 'FunctionPage')
const FunctionsPage = lazyRouteComponent(() => import('./pages/functions/FunctionsPage'), 'FunctionsPage')
const EvidencePage = lazyRouteComponent(() => import('./pages/problems/EvidencePage'), 'EvidencePage')
const DocumentPage = lazyRouteComponent(() => import('./pages/library/DocumentPage'), 'DocumentPage')
const ImagePage = lazyRouteComponent(() => import('./pages/library/ImagePage'), 'ImagePage')
const LibraryPage = lazyRouteComponent(() => import('./pages/library/LibraryPage'), 'LibraryPage')
const ComparePage = lazyRouteComponent(() => import('./pages/history/ComparePage'), 'ComparePage')
const HistoryGalleryPage = lazyRouteComponent(() => import('./pages/history/HistoryGallery'), 'HistoryGalleryPage')
const HistoryPage = lazyRouteComponent(() => import('./pages/history/HistoryPage'), 'HistoryPage')
const ScanPage = lazyRouteComponent(() => import('./pages/history/ScanPage'), 'ScanPage')
const QualityPage = lazyRouteComponent(() => import('./pages/quality/QualityPage'), 'QualityPage')
const SystemMapPage = lazyRouteComponent(() => import('./pages/SystemMap'), 'SystemMapPage')
const FlowPage = lazyRouteComponent(() => import('./pages/paths/FlowPage'), 'FlowPage')
const PathsGalleryPage = lazyRouteComponent(() => import('./pages/paths/PathsGallery'), 'PathsGalleryPage')
const PathsPage = lazyRouteComponent(() => import('./pages/paths/PathsPage'), 'PathsPage')
const PipelineGalleryPage = lazyRouteComponent(() => import('./pages/pipeline/PipelineGallery'), 'PipelineGalleryPage')
const PipelinePage = lazyRouteComponent(() => import('./pages/pipeline/PipelinePage'), 'PipelinePage')
const TimelinePage = lazyRouteComponent(() => import('./pages/paths/TimelinePage'), 'TimelinePage')
const HiddenPage = lazyRouteComponent(() => import('./pages/system/hidden/HiddenPage'), 'HiddenPage')
const JourneysPage = lazyRouteComponent(() => import('./pages/system/journeys/JourneysPage'), 'JourneysPage')
const RunPage = lazyRouteComponent(() => import('./pages/runs/RunPage'), 'RunPage')
const ScreenPage = lazyRouteComponent(() => import('./pages/screens/ScreensPage'), 'ScreenPage')
const ScreensPage = lazyRouteComponent(() => import('./pages/screens/ScreensPage'), 'ScreensPage')
const LiveCheckPage = lazyRouteComponent(() => import('./pages/scan/ScanPage'), 'ScanPage')
const RunsPage = lazyRouteComponent(() => import('./pages/runs/RunsPage'), 'RunsPage')
const BranchesPage = lazyRouteComponent(() => import('./pages/branches/BranchesPage'), 'BranchesPage')
const GalleryPage = lazyRouteComponent(() => import('./gallery/Gallery'), 'GalleryPage')

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
    createRoute({ getParentRoute: () => root, path: '/system/functions', component: FunctionsPage, validateSearch: params('q', 'sort', 'show', 'kind', 'module') }),
    createRoute({ getParentRoute: () => root, path: '/system/f/$functionId', component: FunctionPage, validateSearch: params('q', 'sort', 'show', 'kind', 'module') }),
    createRoute({ getParentRoute: () => root, path: '/screens', component: ScreensPage, validateSearch: params('show') }),
    createRoute({ getParentRoute: () => root, path: '/screens/$screenId', component: ScreenPage, validateSearch: params('vp', 'compare') }),
    createRoute({ getParentRoute: () => root, path: '/flows/$pathId', component: FlowPage, validateSearch: params('view', 'show', 'node', 'traced') }),
    createRoute({ getParentRoute: () => root, path: '/problems', component: ProblemsPage, validateSearch: params(...PROBLEM_KEYS) }),
    createRoute({ getParentRoute: () => root, path: '/evidence/$factId', component: EvidencePage }),
    createRoute({ getParentRoute: () => root, path: '/change', component: ChangePage, validateSearch: params('focus', 'side') }),
    createRoute({ getParentRoute: () => root, path: '/change/ideal', component: IdealPage, validateSearch: params('view') }),
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
    createRoute({ getParentRoute: () => root, path: '/branches', component: BranchesPage, validateSearch: params('show', 'q', 'base', 'b') }),
    createRoute({ getParentRoute: () => root, path: '/scan', component: LiveCheckPage, validateSearch: params('stage') }),
    createRoute({ getParentRoute: () => root, path: '/runs', component: RunsPage, validateSearch: params('q', 'show', 'demo') }),
    createRoute({ getParentRoute: () => root, path: '/runs/$runId', component: RunPage, validateSearch: params('demo') }),
    createRoute({ getParentRoute: () => root, path: '/library', component: LibraryPage, validateSearch: params('group', 'q'), beforeLoad: devOnly('library', dev) }),
    createRoute({ getParentRoute: () => root, path: '/library/docs', component: LibraryPage, validateSearch: params('group', 'q'), beforeLoad: devOnly('library', dev) }),
    createRoute({ getParentRoute: () => root, path: '/library/docs/$docId', component: DocumentPage, validateSearch: params('h'), beforeLoad: devOnly('library', dev) }),
    createRoute({ getParentRoute: () => root, path: '/library/images/$imageId', component: ImagePage, beforeLoad: devOnly('library', dev) }),
    createRoute({ getParentRoute: () => root, path: '/history', component: HistoryPage, beforeLoad: devOnly('history', dev) }),
    createRoute({ getParentRoute: () => root, path: '/history/compare/$range', component: ComparePage, beforeLoad: devOnly('history', dev) }),
    createRoute({ getParentRoute: () => root, path: '/history/$scanId', component: ScanPage, beforeLoad: devOnly('history', dev) }),
    createRoute({ getParentRoute: () => root, path: '/quality', component: QualityPage, beforeLoad: devOnly('quality', dev) }),
    createRoute({ getParentRoute: () => root, path: '/_gallery', component: GalleryPage, validateSearch: params('view', 'card') }),
    createRoute({ getParentRoute: () => root, path: '/_gallery/paths', component: PathsGalleryPage }),
    createRoute({ getParentRoute: () => root, path: '/_gallery/pipeline', component: PipelineGalleryPage }),
    createRoute({ getParentRoute: () => root, path: '/_gallery/history', component: HistoryGalleryPage }),
  ])
  return createRouter({ routeTree: tree, history: createHashHistory(), defaultNotFoundComponent: () => { throw redirect({ to: '/' }) }, scrollRestoration: false,
    defaultPreload: 'intent', defaultPendingComponent: PageLoading, defaultPendingMs: 100 })
}
