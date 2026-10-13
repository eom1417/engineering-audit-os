// #/system/pipeline: the pipeline map (docs/STUDIO.md D9). Desktop: the flowchart (Current / Ideal / Gap, or the
// steps) beside the inspector. Phone: the steps first, the flowchart as a preview that opens full screen, top to
// bottom, with pan and pinch. When the project holds no pipeline the page says so, with what EAOS looked for.
// ?p=<pipeline>, ?view=current|ideal|gap, ?show=map|steps, ?stage=<id>, ?hidden=1, ?follow=<data name>.
import { useSearch } from '@tanstack/react-router'
import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { Button as AriaButton, Dialog, Heading, Modal, ModalOverlay } from 'react-aria-components'
import { Button, IconButton } from '../../components/Button'
import { Segmented } from '../../components/Controls'
import { Panel, Section, Skeleton, StateMessage } from '../../components/Panel'
import { Sheet } from '../../components/Sheet'
import { script } from '../../data/load'
import type { StudioData } from '../../data/types'
import { usePrefs } from '../../i18n/prefs'
import { Id, N, Txt } from '../../i18n/text'
import { usePageChrome } from '../../shell/chrome'
import { layout, MissingBanner, WithData } from '../../shell/Layout'
import { useSearchPatch } from '../../shell/search'
import { usePhone } from '../SystemMap'
import { Flowchart, Legend } from './Flowchart'
import { GapPanel, LookedFor, PipelineSummary, PipelineTree, StageInspector } from './Inspector'
import { dataNames, firstPipeline, follow, scopeOf, trail, usePipeline, VIEWS, type PipelineData, type Scope, type View } from './model'
import { StepList } from './Steps'
import { pipelineTitle } from './names'
import { usePipelineWords, VIEW_WORD } from './words'
import frame from '../paths/paths.module.css'
import css from './panels.module.css'

interface PipelineSearch { p?: string; view?: string; show?: string; stage?: string; hidden?: string; follow?: string }
type Show = 'map' | 'steps'

function ViewSwitch({ view, onChange, comfortable }: { view: View; onChange: (v: View) => void; comfortable?: boolean }) {
  const w = usePipelineWords()
  return <Segmented label={w('view')} value={view} onChange={onChange} comfortable={comfortable} options={VIEWS.map((v) => ({ id: v, label: w(VIEW_WORD[v]) }))} />
}

function ShowSwitch({ show, onChange, comfortable }: { show: Show; onChange: (s: Show) => void; comfortable?: boolean }) {
  const w = usePipelineWords()
  return <Segmented label={w('showAs')} value={show} onChange={onChange} comfortable={comfortable} options={[{ id: 'map', label: w('asMap') }, { id: 'steps', label: w('asSteps') }]} />
}

function HiddenSwitch({ on, n, onChange }: { on: boolean; n: number; onChange: (on: boolean) => void }) {
  const w = usePipelineWords()
  if (!n) return null
  return <label className={frame.check}><input type="checkbox" checked={on} onChange={(e) => onChange(e.target.checked)} />{w('showHidden', { n })}</label>
}

function FollowPicker({ names, value, onChange }: { names: string[]; value?: string; onChange: (name: string | undefined) => void }) {
  const w = usePipelineWords()
  if (!names.length) return null
  return (
    <label className={css.follow}>
      <span>{w('followData')}</span>
      <select aria-label={w('followData')} value={value ?? ''} onChange={(e) => onChange(e.target.value || undefined)} dir="ltr">
        <option value="">{w('followNone')}</option>
        {names.map((n) => <option key={n} value={n}>{n}</option>)}
      </select>
    </label>
  )
}

/** The page's head: where this pipeline sits, its title, the verdict and its facts, each from pipeline.json. */
function Head({ data, scope, onEnter, compact }: { data: PipelineData; scope: Scope; onEnter: (id: string) => void; compact?: boolean }) {
  const w = usePipelineWords()
  const { lang } = usePrefs()
  const path = trail(data, scope.pipeline.id)
  const counts = scope.pipeline.counts ?? {}
  const gaps = scope.gap.length
  return (
    <div className={css.head}>
      {path.length > 1 && (
        <nav className={css.crumbs} aria-label={w('pipelines')}>
          {path.map((p, i) => i < path.length - 1
            ? <span key={p.id}><AriaButton className={css.crumb} onPress={() => onEnter(p.id)}><Id value={p.title} /></AriaButton> ›</span>
            : <span key={p.id} className={css.crumbOn} aria-current="page"><Id value={p.title} /></span>)}
        </nav>
      )}
      <div className={frame.titleRow}>
        {compact ? <h1 className={frame.title}>{w('pipeline')}</h1> : <h1 className={frame.largeTitle}>{w('pipeline')}</h1>}
        <span className={frame.level}><span>{pipelineTitle(scope.pipeline, lang)}</span> · {w.known('pk_', scope.pipeline.kind)}</span>
      </div>
      {!compact && <p className={css.verdict}><Txt>{data.verdict}</Txt></p>}
      <p className={css.facts}>
        <span>{w('counts', { s: counts.stages ?? scope.pipeline.stages.length, e: counts.edges ?? scope.edges.length, g: gaps })}</span>
        <span>{w('confidence')} <strong><N value={Math.round(scope.pipeline.confidence * 100)} />%</strong></span>
        {scope.pipeline.entry.path && <span>{w('entry')} <Id value={`${scope.pipeline.entry.path}${scope.pipeline.entry.line ? `:${scope.pipeline.entry.line}` : ''}`} keep={2} /></span>}
      </p>
    </div>
  )
}

interface ViewCtx {
  studio: StudioData; data: PipelineData; scope: Scope; id: string; view: View; show: Show; stage?: string; hidden: boolean
  names: string[]; followed?: string; lit: ReturnType<typeof follow> | null; label: string
  go: (patch: Partial<PipelineSearch>) => void; pick: (sid: string) => void; enter: (pid: string) => void
  setFollow: (name: string | undefined) => void; setView: (v: View) => void; setShow: (s: Show) => void; setHidden: (on: boolean) => void
}

function PipelineView({ studio, data }: { studio: StudioData; data: PipelineData }) {
  const w = usePipelineWords()
  const { t } = usePrefs()
  const phone = usePhone()
  const search = useSearch({ strict: false }) as PipelineSearch
  const id = search.p && data.pipelines.some((p) => p.id === search.p) ? search.p : firstPipeline(data)!
  const scope = useMemo(() => scopeOf(data, id)!, [data, id])
  const view: View = VIEWS.includes(search.view as View) ? (search.view as View) : 'current'
  const show: Show = search.show === 'map' || search.show === 'steps' ? search.show : 'map'
  const stage = search.stage && (scope.stage.has(search.stage) || scope.ideal.has(search.stage)) ? search.stage : undefined
  const hidden = search.hidden === '1'
  const names = useMemo(() => dataNames(scope), [scope])
  const followed = search.follow && names.includes(search.follow) ? search.follow : undefined
  const lit = useMemo(() => (followed ? follow(scope, followed) : null), [scope, followed])
  const [full, setFull] = useState(false)
  const [sheet, setSheet] = useState(false)
  usePageChrome(w('pipeline'), { to: '/system', label: t('system') }, studio.manifest.project.name)
  const go = useSearchPatch<PipelineSearch>('/system/pipeline', { replace: true })
  const pick = (sid: string) => { go({ stage: sid === stage ? undefined : sid }); if (phone) setSheet(sid !== stage) }
  const enter = (pid: string) => { go({ p: pid === firstPipeline(data) ? undefined : pid, stage: undefined, follow: undefined }); setSheet(false) }
  const setFollow = (name: string | undefined) => { go({ follow: name }); setSheet(false) }
  const setView = (v: View) => go({ view: v === 'current' ? undefined : v })
  const setShow = (s: Show) => go({ show: s === 'map' ? undefined : s })
  const setHidden = (on: boolean) => go({ hidden: on ? '1' : undefined })
  const label = w('countsAria', { t: scope.pipeline.title, s: scope.stages.length, e: scope.edges.length })
  const c: ViewCtx = { studio, data, scope, id, view, show, stage, hidden, names, followed, lit, label, go, pick, enter, setFollow, setView, setShow, setHidden }
  if (phone) return <PhonePipeline c={c} sheet={sheet} setSheet={setSheet} full={full} setFull={setFull} />
  return <DesktopPipeline c={c} />
}

/** The choice of pipeline, each with its number of stages. */
function PipelinePicker({ c }: { c: ViewCtx }) {
  const w = usePipelineWords()
  const { lang } = usePrefs()
  return (
    <label className={css.pipelinePicker}>
      <span>{w('pipelines')}</span>
      <select aria-label={w('pipelines')} value={c.id} onChange={(event) => c.enter(event.target.value)}>
        {c.data.pipelines.map((pipeline) => <option key={pipeline.id} value={pipeline.id}>{pipelineTitle(pipeline, lang)} · {pipeline.counts?.stages ?? pipeline.stages.length} {w('kind_stage')}</option>)}
      </select>
    </label>
  )
}

/** The data name being followed, with the way to stop following it. */
function FollowBar({ followed, onClear }: { followed: string; onClear: () => void }) {
  const w = usePipelineWords()
  return (
    <div className={css.followBar} role="status">
      <span>{w('followOn')} <Id value={followed} /></span>
      <Button variant="ghost" onPress={onClear}>{w('clearFollow')}</Button>
    </div>
  )
}

/** The phone: the steps first, the flowchart as a preview that opens full screen, the inspector as a sheet. */
function PhonePipeline({ c, sheet, setSheet, full, setFull }: { c: ViewCtx; sheet: boolean; setSheet: (open: boolean) => void; full: boolean; setFull: (open: boolean) => void }) {
  const w = usePipelineWords()
  const { lang } = usePrefs()
  const { studio, data, scope, view, show, stage, hidden, names, followed, lit, label, go, pick, enter, setFollow, setView, setShow, setHidden } = c
  return (
      <div className={frame.phone}>
        <MissingBanner data={studio} />
        <Head data={data} scope={scope} onEnter={enter} compact />
        <PipelinePicker c={c} />
        <div className={css.mobileControls}><ViewSwitch view={view} onChange={setView} comfortable /><ShowSwitch show={show} onChange={setShow} comfortable /></div>
        <details className={css.explore}><summary>{lang === 'ar' ? 'تتبّع البيانات والمسارات الخفية' : 'Trace data and hidden paths'}</summary>
          <HiddenSwitch on={hidden} n={scope.hidden.length} onChange={setHidden} />
          <FollowPicker names={names} value={followed} onChange={setFollow} />
        </details>
        {followed && <FollowBar followed={followed} onClear={() => setFollow(undefined)} />}
        {show === 'map' && (
          <div className={css.mobileDiagram}>
            <Flowchart scope={scope} view={view} down selected={stage} onSelect={pick} hidden={hidden} lit={lit} label={label} legend={false}
              head={<Button variant="ghost" onPress={() => setFull(true)}>{w('openDiagram')}</Button>} />
          </div>
        )}
        <p className={css.guide}>{w('diagramGuide')}</p>
        {show === 'map' && <Legend kinds={new Set(scope.stages.map((s) => s.kind))} scope={scope} view={view} hidden={hidden || view === 'gap'} inline />}
        {view === 'gap' && <Section title={w('gap')} count={scope.gap.length}><GapPanel data={data} scope={scope} onSelect={pick} /></Section>}
        {show === 'steps' && <Section title={w('asSteps')} count={lit ? lit.stages.size : scope.stages.length}>
          <Panel pad><StepList scope={scope} view={view} selected={stage} onSelect={pick} lit={lit} first={12} /></Panel>
        </Section>}
        <details className={css.explore}><summary>{w('pipelines')}</summary><PipelineTree data={data} current={scope.pipeline.id} onEnter={enter} /></details>
        <Sheet isOpen={sheet && !!stage} onOpenChange={setSheet} title={w('inspector')}>
          {stage && <StageInspector data={data} scope={scope} id={stage} view={view} onSelect={(s) => go({ stage: s })} onEnter={enter} onFollow={setFollow} />}
        </Sheet>
        <FullDiagram c={c} open={full} onOpenChange={setFull} onInspect={() => setSheet(true)} />
      </div>
  )
}

/** The phone's flowchart full screen, top to bottom, with pan and pinch; the chosen stage opens the inspector. */
function FullDiagram({ c, open, onOpenChange, onInspect }: { c: ViewCtx; open: boolean; onOpenChange: (open: boolean) => void; onInspect: () => void }) {
  const w = usePipelineWords()
  const { scope, view, stage, hidden, lit, label, go, setView } = c
  return (
    <ModalOverlay isOpen={open} onOpenChange={onOpenChange} isDismissable className={frame.sheetOverlay}>
      <Modal className={frame.sheetModal}>
        <Dialog className={frame.sheetDialog} aria-label={w('pipeline')}>
          {({ close }) => (
            <>
              <Flowchart scope={scope} view={view} down selected={stage} onSelect={(s) => go({ stage: s })} hidden={hidden} lit={lit} label={label} legend={false}
                title={<div className={frame.titleRow}><IconButton icon="x" label={w('closeDiagram')} onPress={close} /><Heading slot="title" className={frame.sheetTitle}><Id value={scope.pipeline.title} /></Heading></div>}
                head={<ViewSwitch view={view} onChange={setView} comfortable />} />
              {stage && (
                <div className={frame.sheetBar} role="status">
                  <Id value={scope.stage.get(stage)?.label ?? scope.ideal.get(stage)?.label ?? stage} />
                  <Button variant="primary" onPress={() => { close(); onInspect() }}>{w('inspector')}</Button>
                </div>
              )}
            </>
          )}
        </Dialog>
      </Modal>
    </ModalOverlay>
  )
}

/** The desktop: the flowchart or the steps beside the inspector. */
function DesktopPipeline({ c }: { c: ViewCtx }) {
  const w = usePipelineWords()
  const { studio, data, scope, view, show, stage, hidden, names, followed, lit, label, pick, enter, setFollow, setView, setShow, setHidden } = c
  const inspector = stage
    ? <StageInspector data={data} scope={scope} id={stage} view={view} onSelect={pick} onEnter={enter} onFollow={setFollow} />
    : <PipelineSummary data={data} scope={scope} view={view} onSelect={pick} onEnter={enter} />
  const long = scope.stages.length > 200
  const head: ReactNode = (
    <>
      <PipelinePicker c={c} />
      <ViewSwitch view={view} onChange={setView} />
      <ShowSwitch show={show} onChange={setShow} />
      <HiddenSwitch on={hidden} n={scope.hidden.length} onChange={setHidden} />
      <FollowPicker names={names} value={followed} onChange={setFollow} />
    </>
  )
  const title = <><Head data={data} scope={scope} onEnter={enter} compact /><p className={css.guide}>{w('diagramGuide')}</p></>
  return (
    <div className={frame.split}>
      <section className={frame.canvasCol} aria-label={w('pipeline')}>
        <MissingBanner data={studio} />
        {show === 'map' ? (
          <Flowchart scope={scope} view={view} down={false} selected={stage} onSelect={pick} hidden={hidden} lit={lit} label={label} title={title} head={head} />
        ) : (
          <div className={frame.canvasWrap}>
            <div className={frame.toolbar}>{title}<div className={frame.toolRow}>{head}</div></div>
            <div className={frame.seqWrap}><div className={frame.phone}><StepList scope={scope} view={view} selected={stage} onSelect={pick} lit={lit} /></div></div>
          </div>
        )}
        {(followed || long) && <div className={frame.note}>{followed && <FollowBar followed={followed} onClear={() => setFollow(undefined)} />}{long && show === 'map' && <span>{w('partOfLong')}</span>}</div>}
      </section>
      <aside className={frame.side} aria-label={w('inspector')}>
        {!stage && <p className={css.verdict}><Txt>{data.verdict}</Txt></p>}
        {inspector}
      </aside>
    </div>
  )
}

/** The project holds no pipeline: said plainly, with what EAOS looked for. */
function NoPipeline({ studio, data }: { studio: StudioData; data: PipelineData }) {
  const w = usePipelineWords()
  return (
    <div className={layout.page}>
      <MissingBanner data={studio} />
      <h1 className={layout.largeTitle}>{w('pipeline')}</h1>
      <Panel>
        <StateMessage title={w('noPipeline')} sub={<Txt>{data.verdict}</Txt>} />
      </Panel>
      <p className={layout.lead}>{w('noPipelineLead')}</p>
      <Section title={w('lookedFor')} count={data.looked_for.length}>
        <Panel pad><LookedFor data={data} /></Panel>
      </Section>
    </div>
  )
}

interface CoverageRow { section: string; state: string; detail?: string; step?: string | null }

/** The report carries no pipeline map at all: its coverage row says why and which step writes it. */
function NoMap({ studio }: { studio: StudioData }) {
  const w = usePipelineWords()
  const listed = studio.manifest.sections.some((s) => (s.name as string) === 'coverage')
  const [row, setRow] = useState<CoverageRow | undefined>()
  useEffect(() => {
    if (!listed) return
    let live = true
    const find = () => ((window.EAOS_STUDIO?.coverage as { sections?: CoverageRow[] } | undefined)?.sections ?? []).find((r) => r.section === 'pipeline')
    const ready = find()
    if (ready) { setRow(ready); return }
    script('coverage').then(() => { if (live) setRow(find()) })
    return () => { live = false }
  }, [listed])
  return (
    <div className={layout.page}>
      <MissingBanner data={studio} />
      <h1 className={layout.largeTitle}>{w('pipeline')}</h1>
      <Panel><StateMessage title={w('absent')} sub={<>{row?.detail ? <Txt>{row.detail}</Txt> : w('absentSub')}</>} /></Panel>
    </div>
  )
}

function PipelineBody({ data }: { data: StudioData }) {
  const { t } = usePrefs()
  const state = usePipeline(data)
  if (state.kind === 'loading') return <Chrome data={data}><div className={layout.page}><Panel><Skeleton label={t('loading')} /></Panel></div></Chrome>
  if (state.kind === 'absent') return <Chrome data={data}><NoMap studio={data} /></Chrome>
  if (!state.data.pipelines.length) return <Chrome data={data}><NoPipeline studio={data} data={state.data} /></Chrome>
  return <PipelineView studio={data} data={state.data} />
}

/** The top bar's title and way back for the page's states that are not the map. */
function Chrome({ data, children }: { data: StudioData; children: ReactNode }) {
  const { t } = usePrefs()
  const w = usePipelineWords()
  usePageChrome(w('pipeline'), { to: '/system', label: t('system') }, data.manifest.project.name)
  return <>{children}</>
}

export function PipelinePage() {
  return <WithData>{(data) => <PipelineBody data={data} />}</WithData>
}
