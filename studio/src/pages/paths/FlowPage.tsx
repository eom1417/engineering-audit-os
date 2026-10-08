// #/flows/<path>: one code path. Diagram (the swimlanes, Current / Target / Change), Sequence (lifelines and messages
// in order) or Steps (the linear list, the phone's default and the screen reader's view); the inspector shows the
// evidence of what is chosen. ?view=current|target|change, ?show=diagram|sequence|steps, ?node=<id>, ?traced=1.
import { useNavigate, useParams, useSearch } from '@tanstack/react-router'
import { useMemo, useState, type ReactNode } from 'react'
import { Dialog, Heading, Modal, ModalOverlay } from 'react-aria-components'
import { Button, IconButton } from '../../components/Button'
import { Segmented } from '../../components/Controls'
import { Go } from '../../components/Go'
import { Icon } from '../../components/Icon'
import { Panel, Section, Skeleton, StateMessage } from '../../components/Panel'
import { Sheet } from '../../components/Sheet'
import type { StudioData } from '../../data/types'
import { usePrefs } from '../../i18n/prefs'
import { Id } from '../../i18n/text'
import { usePageChrome } from '../../shell/chrome'
import { MissingBanner, WithData } from '../../shell/Layout'
import { usePhone } from '../SystemMap'
import { drawPath } from './draw'
import { NodeInspector } from './Inspector'
import { Lanes, Legend, type DrawNode } from './Lanes'
import { indexOf, LANES, PATH_MODES, possible, usePaths, where, type CodePath, type PathMode, type PathOp, type PathsData } from './model'
import { ModeSwitch } from './ModeSwitch'
import { NoPaths } from './PathsPage'
import { SequenceDiagram, StepList } from './Sequence'
import { GAP_WORD, LANE_WORD, usePathWords } from './words'
import css from './paths.module.css'

interface FlowSearch { view?: string; show?: string; node?: string; traced?: string }
type Show = 'diagram' | 'sequence' | 'steps'

function ShowSwitch({ show, onChange, comfortable }: { show: Show; onChange: (s: Show) => void; comfortable?: boolean }) {
  const w = usePathWords()
  return <Segmented label={w('showAs')} value={show} onChange={onChange} comfortable={comfortable}
    options={[{ id: 'diagram', label: w('asDiagram') }, { id: 'sequence', label: w('asSequence') }, { id: 'steps', label: w('asSteps') }]} />
}

function Traced({ on, onChange }: { on: boolean; onChange: (on: boolean) => void }) {
  const w = usePathWords()
  return <label className={css.check}><input type="checkbox" checked={on} onChange={(e) => onChange(e.target.checked)} />{w('onlyTraced')}</label>
}

function PathHead({ path, compact }: { path: CodePath; compact?: boolean }) {
  const w = usePathWords()
  return (
    <div className={css.titleRow}>
      {compact ? <h1 className={css.titleId}><Id value={path.title} /></h1> : <h1 className={css.largeTitle}><Id value={path.title} /></h1>}
      <span className={css.level}>
        {w('stepsN', { n: path.steps.length })}{path.gaps > 0 && <> · <span className={css.gapN}>{w('gapsN', { n: path.gaps })}</span></>}
        {' · '}{w('reaches', { lane: w(LANE_WORD[LANES[path.reach]]) })}
      </span>
    </div>
  )
}

function FlowView({ data, paths, path }: { data: StudioData; paths: PathsData; path: CodePath }) {
  const w = usePathWords()
  const { t } = usePrefs()
  const phone = usePhone()
  const navigate = useNavigate()
  const search = useSearch({ strict: false }) as FlowSearch
  const index = useMemo(() => indexOf(paths), [paths])
  const mode: PathMode = PATH_MODES.includes(search.view as PathMode) ? (search.view as PathMode) : 'current'
  const show: Show = (['diagram', 'sequence', 'steps'] as Show[]).find((s) => s === search.show) ?? (phone ? 'steps' : 'diagram')
  const traced = search.traced === '1'
  const node = search.node && index.node.has(search.node) && path.columns.some((c) => c.includes(search.node!)) ? search.node : undefined
  const [full, setFull] = useState(false)
  const [sheet, setSheet] = useState(false)
  usePageChrome(path.title, { to: '/system/paths', label: w('codePaths') }, data.manifest.project.name)
  const go = (patch: Partial<FlowSearch>) => navigate({
    to: '/flows/$pathId', params: { pathId: path.id }, replace: true,
    search: (prev: FlowSearch) => Object.fromEntries(Object.entries({ ...prev, ...patch }).filter(([, v]) => v !== undefined && v !== '')) as FlowSearch,
  })
  const pick = (id: string) => { go({ node: id === node ? undefined : id }); if (phone) setSheet(id !== node) }
  const drawn = useMemo(() => drawPath(paths, index, path, mode, w, traced), [paths, index, path, mode, w, traced])
  const label = w('diagramAria', { t: path.title, n: path.columns.flat().length, l: path.columns.filter((c) => c.length).length, g: path.gaps })
  const maybe = useMemo(() => possible(paths, path), [paths, path])
  const setMode = (m: PathMode) => go({ view: m === 'current' ? undefined : m })
  const setShow = (s: Show) => go({ show: s === (phone ? 'steps' : 'diagram') ? undefined : s })
  const back = <Go to="/system/paths" className={css.back}><Icon name="back" />{w('allPaths')}</Go>
  const notes = (
    <>
      {path.capped > 0 && <p className={css.note}>{w('capped', { n: path.capped })}</p>}
      {show !== 'diagram' && <p className={css.note}>{w('sourceOrder')}</p>}
    </>
  )

  if (phone) {
    return (
      <div className={css.phone}>
        <MissingBanner data={data} />
        {back}
        <PathHead path={path} />
        <ModeSwitch mode={mode} onChange={setMode} comfortable />
        <ShowSwitch show={show} onChange={setShow} comfortable />
        {show === 'diagram' && (
          <figure>
            <button type="button" className={css.preview} onClick={() => setFull(true)} aria-label={w('openDiagram')}>
              <MiniLanes path={path} />
            </button>
            <figcaption className={css.previewCap}>
              <span>{label}</span>
              <Button variant="ghost" onPress={() => setFull(true)}>{w('openDiagram')}</Button>
            </figcaption>
          </figure>
        )}
        {show === 'diagram' && <Legend mode={mode} ops={opsOf(drawn.nodes)} possible={maybe.edges.size > 0} gap={path.gaps > 0} inline />}
        {show === 'sequence' && <Panel><SequenceDiagram data={paths} index={index} path={path} selected={node} onSelect={pick} /></Panel>}
        {(show === 'steps' || show === 'diagram') && (
          <Section title={w('asSteps')} count={path.steps.length + 1}>
            <Panel pad><StepList data={paths} index={index} path={path} selected={node} onSelect={pick} first={12} /></Panel>
          </Section>
        )}
        {notes}
        <Sheet isOpen={sheet && !!node} onOpenChange={setSheet} title={t('inspector')}>
          {node && <NodeInspector data={paths} index={index} id={node} path={path} />}
        </Sheet>
        <ModalOverlay isOpen={full} onOpenChange={setFull} isDismissable className={css.sheetOverlay}>
          <Modal className={css.sheetModal}>
            <Dialog className={css.sheetDialog} aria-label={path.title}>
              {({ close }) => (
                <>
                  <Lanes columns={path.columns} nodes={drawn.nodes} edges={drawn.edges} mode={mode} selected={node} onSelect={(id) => go({ node: id })}
                    label={label} legend="none"
                    title={<div className={css.titleRow}><IconButton icon="x" label={w('closeDiagram')} onPress={close} /><Heading slot="title" className={css.sheetTitle}><Id value={path.title} /></Heading></div>}
                    head={<ModeSwitch mode={mode} onChange={setMode} comfortable />} />
                  {node && (
                    <div className={css.sheetBar} role="status">
                      <Id value={index.node.get(node)?.label ?? node} />
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

  const head: ReactNode = (
    <>
      <ModeSwitch mode={mode} onChange={setMode} />
      <ShowSwitch show={show} onChange={setShow} />
      {show === 'diagram' && maybe.edges.size > 0 && <Traced on={traced} onChange={(on) => go({ traced: on ? '1' : undefined })} />}
    </>
  )
  const title = <div className={css.toolRow}>{back}<PathHead path={path} compact /></div>
  return (
    <div className={css.split}>
      <section className={css.canvasCol} aria-label={path.title}>
        <MissingBanner data={data} />
        {show === 'diagram' ? (
          <Lanes columns={path.columns} nodes={drawn.nodes} edges={drawn.edges} mode={mode} selected={node} onSelect={pick} label={label} title={title} head={head} />
        ) : (
          <div className={css.canvasWrap}>
            <div className={css.toolbar}>{title}<div className={css.toolRow}>{head}</div></div>
            {show === 'sequence'
              ? <SequenceDiagram data={paths} index={index} path={path} selected={node} onSelect={pick} />
              : <div className={css.seqWrap}><div className={css.phone}><StepList data={paths} index={index} path={path} selected={node} onSelect={pick} /></div></div>}
          </div>
        )}
        {notes}
      </section>
      <aside className={css.side} aria-label={t('inspector')}>
        {node ? <NodeInspector data={paths} index={index} id={node} path={path} /> : <PathSummary paths={paths} path={path} />}
      </aside>
    </div>
  )
}

function opsOf(nodes: Map<string, DrawNode>): PathOp[] {
  return [...new Set([...nodes.values()].map((n) => n.op).filter((op): op is PathOp => !!op))]
}

/** The phone's preview of a path: its lanes as rows of dots, the gaps marked (the full diagram opens on tap). */
function MiniLanes({ path }: { path: CodePath }) {
  const rows = path.columns
  const tallest = Math.max(1, ...rows.map((c) => c.length))
  const step = Math.min(18, 300 / tallest)
  return (
    <svg viewBox={`0 0 ${LANES.length * 50} ${Math.max(60, tallest * step + 20)}`} aria-hidden="true">
      {rows.map((column, i) => column.map((id, r) => (
        <rect key={id} x={i * 50 + 9} y={10 + r * step} width={32} height={Math.max(4, step - 6)} rx={3}
          className={id.startsWith('G:') ? css.miniGap : css.miniBox} />
      )))}
    </svg>
  )
}

/** The inspector before a step is chosen: where the path starts, its flow, and where EAOS stopped on it. */
function PathSummary({ paths, path }: { paths: PathsData; path: CodePath }) {
  const w = usePathWords()
  const entry = paths.nodes.find((n) => n.id === path.entry)
  const gaps = path.columns.flat().map((id) => paths.nodes.find((n) => n.id === id)).filter((n) => n?.kind === 'gap')
  const reasons = [...new Set(gaps.map((n) => n!.reason))]
  return (
    <div className={css.inspect}>
      <p className={css.lead}>{w('chooseNode')}</p>
      <dl className={css.evid}>
        {entry?.path && <><dt>{w('file')}</dt><dd><Id value={where(entry.path, entry.line) ?? ''} /></dd></>}
        {path.fact && <><dt>{w('fact')}</dt><dd><Id value={path.fact} /></dd></>}
        {path.flow && <><dt>{w('flow')}</dt><dd><Id value={path.flow} /></dd></>}
      </dl>
      {reasons.length > 0 && (
        <section className={css.stopped}>
          <h2 className={css.insH}>{w('whereStopped')}</h2>
          {reasons.map((r) => r && <div key={r} className={css.stopRow}><span>{w(GAP_WORD[r].title)}</span><span>{gaps.filter((n) => n!.reason === r).length}</span></div>)}
        </section>
      )}
      <Legend mode="current" ops={[]} possible={possible(paths, path).edges.size > 0} gap={path.gaps > 0} inline />
    </div>
  )
}

/** A state of the page that is not a path (loading, no paths, an unknown path), titled like the paths. */
function Titled({ data, children }: { data: StudioData; children: ReactNode }) {
  const w = usePathWords()
  usePageChrome(w('codePaths'), { to: '/system/paths', label: w('codePaths') }, data.manifest.project.name)
  return <>{children}</>
}

function FlowBody({ data }: { data: StudioData }) {
  const w = usePathWords()
  const { t } = usePrefs()
  const { pathId } = useParams({ strict: false }) as { pathId?: string }
  const state = usePaths(data)
  if (state.kind === 'loading') return <Titled data={data}><div className={css.phone}><Panel><Skeleton label={t('loading')} /></Panel></div></Titled>
  if (state.kind === 'absent') return <Titled data={data}><NoPaths data={data} /></Titled>
  const path = state.paths.paths.find((p) => p.id === pathId)
  if (!path) {
    return (
      <Titled data={data}>
        <div className={css.phone}>
          <Panel><StateMessage title={w('pathMissing')} action={<Go to="/system/paths" className={css.back}><Icon name="back" />{w('allPaths')}</Go>} /></Panel>
        </div>
      </Titled>
    )
  }
  return <FlowView data={data} paths={state.paths} path={path} />
}

export function FlowPage() {
  return <WithData>{(data) => <FlowBody data={data} />}</WithData>
}
