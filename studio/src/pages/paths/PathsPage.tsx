// #/system/paths: every code path at once. Desktop: the overview (clusters in the seven lanes, Current / Target /
// Change) beside the list of paths and where EAOS stopped; choosing a cluster shows its steps and paths. Phone: the
// list first, the overview as a preview that opens full screen. ?view=, ?cluster=, ?q=, ?filter=gaps|screens|server,
// ?file= or ?part= (the paths through a file or a part: the links from a card, a component or a function).
import { useNavigate, useSearch } from '@tanstack/react-router'
import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { Dialog, Heading, Modal, ModalOverlay } from 'react-aria-components'
import { Button, IconButton } from '../../components/Button'
import { SearchField, Segmented } from '../../components/Controls'
import { Go } from '../../components/Go'
import { Panel, Section, Skeleton, StateMessage } from '../../components/Panel'
import { Sheet } from '../../components/Sheet'
import { script } from '../../data/load'
import type { StudioData } from '../../data/types'
import { usePrefs } from '../../i18n/prefs'
import { Id, N } from '../../i18n/text'
import { usePageChrome } from '../../shell/chrome'
import { layout, MissingBanner, WithData } from '../../shell/Layout'
import { usePhone } from '../SystemMap'
import { drawOverview } from './draw'
import { ModeSwitch } from './FlowPage'
import { ClusterInspector } from './Inspector'
import { Lanes } from './Lanes'
import { indexOf, LANES, PATH_MODES, pathsThrough, usePaths, type CodePath, type GapReason, type PathMode, type PathsData } from './model'
import { GAP_WORD, LANE_WORD, usePathWords } from './words'
import css from './paths.module.css'

interface PathsSearch { view?: string; cluster?: string; q?: string; filter?: string; file?: string; part?: string }
type Filter = 'all' | 'gaps' | 'screens' | 'server'
const REASONS: GapReason[] = ['no_server_route', 'trace_stopped', 'component_not_found', 'handler_not_found']

interface CoverageRow { section: string; state: string; detail: string; step: string | null; parts?: { id: string; state: string; detail?: string }[] }

/** The coverage row of the paths section (studio/coverage.json), loaded on demand, for the designed empty state. */
function useCoverageRow(data: StudioData, section: string): CoverageRow | undefined {
  const listed = data.manifest.sections.some((s) => (s.name as string) === 'coverage')
  const read = () => ((window.EAOS_STUDIO?.coverage as { sections?: CoverageRow[] } | undefined)?.sections ?? []).find((r) => r.section === section)
  const [row, setRow] = useState<CoverageRow | undefined>(read)
  useEffect(() => {
    if (!listed || row) return
    let live = true
    script('coverage').then(() => { if (live) setRow(read()) })
    return () => { live = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [listed])
  return row
}

/** The designed state when a report has no code paths: what is missing, why, and which step produces it. */
export function NoPaths({ data }: { data: StudioData }) {
  const w = usePathWords()
  const row = useCoverageRow(data, 'paths')
  return (
    <div className={layout.page}>
      <Panel>
        <StateMessage title={w('noPaths')} sub={<>{row?.detail ?? w('noPathsSub')}{row?.step && <> · <Id value={row.step} /></>}</>} />
      </Panel>
    </div>
  )
}

function Reach({ n }: { n: number }) {
  return <span className={css.reach} aria-hidden="true">{LANES.map((_, i) => <i key={i} data-on={i <= n ? '' : undefined} />)}</span>
}

export function PathRow({ path }: { path: CodePath }) {
  const w = usePathWords()
  return (
    <Go to={`/flows/${path.id}`} className={css.pathRow}>
      <span className={css.pathTitle}><Id value={path.title} />{path.handler && <span className={css.muted}><Id value={path.handler} /></span>}<Reach n={path.reach} /></span>
      <span className={css.pathMeta}>
        <span>{w('stepsN', { n: path.steps.length })}</span>
        {path.gaps > 0 && <span className={css.gapN}>{w('gapsN', { n: path.gaps })}</span>}
        <span>{w('reaches', { lane: w(LANE_WORD[LANES[path.reach]]) })}</span>
      </span>
    </Go>
  )
}

function Stopped({ paths, onFilter }: { paths: PathsData; onFilter?: () => void }) {
  const w = usePathWords()
  const rows = REASONS.map((r) => [r, paths.counts[r]?.value ?? 0] as const).filter(([, n]) => n > 0)
  if (!rows.length) return null
  return (
    <section className={css.stopped} aria-labelledby="h-stopped">
      <h2 className={css.insH} id="h-stopped">{w('whereStopped')}</h2>
      {rows.map(([r, n]) => <div key={r} className={css.stopRow}><span>{w(GAP_WORD[r].title)}</span><N value={n} /></div>)}
      {onFilter && <Button variant="ghost" onPress={onFilter}>{w('filterGaps')}</Button>}
    </section>
  )
}

function PathList({ paths, search, go, fold = 40 }: { paths: PathsData; search: PathsSearch; go: (patch: Partial<PathsSearch>) => void; fold?: number }) {
  const w = usePathWords()
  const { t } = usePrefs()
  const index = useMemo(() => indexOf(paths), [paths])
  const filter: Filter = (['gaps', 'screens', 'server'] as Filter[]).find((f) => f === search.filter) ?? 'all'
  const q = (search.q ?? '').trim().toLowerCase()
  const shown = useMemo(() => {
    let rows = search.file || search.part ? pathsThrough(paths, index, { file: search.file, part: search.part }) : paths.paths
    if (filter === 'gaps') rows = rows.filter((p) => p.gaps > 0)
    if (filter === 'screens') rows = rows.filter((p) => p.surface === 'page')
    if (filter === 'server') rows = rows.filter((p) => p.surface !== 'page')
    if (q) rows = rows.filter((p) => p.title.toLowerCase().includes(q) || p.columns.flat().some((id) => {
      const n = index.node.get(id)
      return !!n && (n.label.toLowerCase().includes(q) || (n.path ?? '').toLowerCase().includes(q))
    }))
    return rows
  }, [paths, index, filter, q, search.file, search.part])
  const [more, setMore] = useState(false)
  const first = more ? shown : shown.slice(0, fold)
  return (
    <div className={css.filters}>
      <SearchField label={w('findPath')} placeholder={w('findPath')} value={search.q ?? ''} onChange={(v) => go({ q: v || undefined })} />
      <Segmented label={w('allPaths')} value={filter} onChange={(f) => go({ filter: f === 'all' ? undefined : f })} options={[
        { id: 'all', label: w('filterAll') }, { id: 'gaps', label: w('filterGaps') }, { id: 'screens', label: w('filterScreens') }, { id: 'server', label: w('filterServer') },
      ]} />
      {(search.file || search.part) && (
        <Go to="/system/paths" search={{ view: search.view }} className={css.back}><Id value={search.file ?? search.part ?? ''} keep={2} /> ×</Go>
      )}
      <ul className={css.list} aria-label={w('allPaths')}>
        {first.map((p) => <li key={p.id}><PathRow path={p} /></li>)}
      </ul>
      {shown.length > first.length && <Button variant="ghost" onPress={() => setMore(true)}>{t('showAllN', { n: shown.length })}</Button>}
    </div>
  )
}

function PathsView({ data, paths }: { data: StudioData; paths: PathsData }) {
  const w = usePathWords()
  const { t } = usePrefs()
  const phone = usePhone()
  const navigate = useNavigate()
  const search = useSearch({ strict: false }) as PathsSearch
  const index = useMemo(() => indexOf(paths), [paths])
  const mode: PathMode = PATH_MODES.includes(search.view as PathMode) ? (search.view as PathMode) : 'current'
  const cluster = paths.overview.clusters.some((c) => c.id === search.cluster) ? search.cluster : undefined
  const [full, setFull] = useState(false)
  const [sheet, setSheet] = useState(false)
  const go = (patch: Partial<PathsSearch>) => navigate({
    to: '/system/paths', replace: true,
    search: (prev: PathsSearch) => Object.fromEntries(Object.entries({ ...prev, ...patch }).filter(([, v]) => v !== undefined && v !== '')) as PathsSearch,
  })
  const pick = (id: string) => { go({ cluster: id === cluster ? undefined : id }); if (phone) setSheet(id !== cluster) }
  const drawn = useMemo(() => drawOverview(paths, mode, w), [paths, mode, w])
  const label = w('overviewAria', { n: paths.overview.clusters.length })
  const count = (key: string) => paths.counts[key]?.value ?? 0
  const lead = (
    <p className={css.lead}>{w('pathsCount', { p: count('paths'), l: count('links'), g: count('gaps') })}</p>
  )
  const newParts = paths.new.length > 0 && <p className={css.muted}>{w('newParts', { n: paths.new.length })}</p>
  const setMode = (m: PathMode) => go({ view: m === 'current' ? undefined : m })
  const list = <PathList paths={paths} search={search} go={go} fold={phone ? 8 : 40} />

  if (!paths.paths.length) {
    return <div className={layout.page}><Panel><StateMessage title={w('codePaths')} sub={w('pathsEmpty')} /></Panel></div>
  }
  if (phone) {
    return (
      <div className={css.phone}>
        <MissingBanner data={data} />
        <h1 className={css.largeTitle}>{w('codePaths')}</h1>
        {lead}
        <p className={css.lead}>{w('pathsLead')}</p>
        <figure>
          <button type="button" className={css.preview} onClick={() => setFull(true)} aria-label={w('openDiagram')}>
            <OverviewPreview paths={paths} />
          </button>
          <figcaption className={css.previewCap}><span>{w('overview')}</span><Button variant="ghost" onPress={() => setFull(true)}>{w('openDiagram')}</Button></figcaption>
        </figure>
        <Panel pad><Stopped paths={paths} onFilter={() => go({ filter: 'gaps' })} /></Panel>
        <Section title={w('allPaths')} count={paths.paths.length}>{list}</Section>
        {newParts}
        <Sheet isOpen={sheet && !!cluster} onOpenChange={setSheet} title={t('inspector')}>
          {cluster && <ClusterInspector data={paths} index={index} id={cluster} />}
        </Sheet>
        <ModalOverlay isOpen={full} onOpenChange={setFull} isDismissable className={css.sheetOverlay}>
          <Modal className={css.sheetModal}>
            <Dialog className={css.sheetDialog} aria-label={w('overview')}>
              {({ close }) => (
                <>
                  <Lanes columns={paths.overview.columns} nodes={drawn.nodes} edges={drawn.edges} mode={mode} selected={cluster} onSelect={(id) => go({ cluster: id })}
                    label={label} legend="none"
                    title={<div className={css.titleRow}><IconButton icon="x" label={w('closeDiagram')} onPress={close} /><Heading slot="title" className={css.sheetTitle}>{w('overview')}</Heading></div>}
                    head={<ModeSwitch mode={mode} onChange={setMode} comfortable />} />
                  {cluster && (
                    <div className={css.sheetBar} role="status">
                      <Id value={paths.overview.clusters.find((c) => c.id === cluster)?.label ?? ''} />
                      <Button variant="primary" onPress={() => { close(); setSheet(true) }}>{t('inspector')}</Button>
                    </div>
                  )}
                </>
              )}
            </Dialog>
          </Modal>
        </ModalOverlay>
      </div>
    )
  }

  const title: ReactNode = <div className={css.titleRow}><h1 className={css.title}>{w('codePaths')}</h1><span className={css.level}>{w('overview')}</span></div>
  return (
    <div className={css.split}>
      <section className={css.canvasCol} aria-label={w('overview')}>
        <MissingBanner data={data} />
        <Lanes columns={paths.overview.columns} nodes={drawn.nodes} edges={drawn.edges} mode={mode} selected={cluster} onSelect={pick} label={label}
          title={title} head={<ModeSwitch mode={mode} onChange={setMode} />} />
        <p className={css.note}>{w('overviewHint')}</p>
      </section>
      <aside className={css.side} aria-label={t('inspector')}>
        {cluster ? <ClusterInspector data={paths} index={index} id={cluster} /> : (
          <>
            {lead}
            <p className={css.lead}>{w('pathsLead')}</p>
            <Stopped paths={paths} />
            {newParts}
            <Section title={w('allPaths')} count={paths.paths.length}>{list}</Section>
          </>
        )}
      </aside>
    </div>
  )
}

/** The overview as a small picture for the phone: each cluster a bar in its lane, gaps marked. */
function OverviewPreview({ paths }: { paths: PathsData }) {
  const columns = paths.overview.columns
  const tallest = Math.max(1, ...columns.map((c) => c.length))
  const step = Math.min(16, 220 / tallest)
  const gap = new Set(paths.overview.clusters.filter((c) => c.kind === 'gap').map((c) => c.id))
  return (
    <svg viewBox={`0 0 ${LANES.length * 50} ${tallest * step + 20}`} aria-hidden="true">
      {columns.map((column, i) => column.map((id, r) => (
        <rect key={id} x={i * 50 + 9} y={10 + r * step} width={32} height={Math.max(3, step - 5)} rx={3} className={gap.has(id) ? css.miniGap : css.miniBox} />
      )))}
    </svg>
  )
}

function PathsBody({ data }: { data: StudioData }) {
  const { t } = usePrefs()
  const w = usePathWords()
  const state = usePaths(data)
  usePageChrome(w('codePaths'), undefined, data.manifest.project.name)
  if (state.kind === 'loading') return <div className={layout.page}><Panel><Skeleton label={t('loading')} /></Panel></div>
  if (state.kind === 'absent') return <NoPaths data={data} />
  return <PathsView data={data} paths={state.paths} />
}

export function PathsPage() {
  return <WithData>{(data) => <PathsBody data={data} />}</WithData>
}
