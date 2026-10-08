// System → Data (STUDIO-COMPLETE: the data paths map). Desktop: the seven links of every write with what each knows,
// the map (who writes and reads → where it is kept, gaps hatched) or its steps view, beside a 360px inspector with the
// chosen store's chain. Phone: the links, the steps view and the chosen store; the map opens as a full-screen sheet
// with pan and pinch. ?view=current|change|target, ?store=<id>, ?show=steps, ?reads=1.
import { useNavigate, useSearch } from '@tanstack/react-router'
import { useMemo, useRef, useState } from 'react'
import { Button as AriaButton, Dialog, Heading, Modal, ModalOverlay } from 'react-aria-components'
import { Button, IconButton } from '../../components/Button'
import { Segmented } from '../../components/Controls'
import { Panel, Section, StateMessage } from '../../components/Panel'
import type { DataPaths } from '../../data/dataMap'
import type { StudioData } from '../../data/types'
import { FocusField } from '../../map/FocusField'
import { useZoom } from '../../map/useZoom'
import mapCss from '../../map/parts.module.css'
import { usePageChrome } from '../../shell/chrome'
import { MissingBanner, WithData } from '../../shell/Layout'
import { usePhone } from '../SystemMap'
import { DataLegend, DataMap } from './DataMap'
import { isCluster, membersOf, modeOf, ranked, viewOf, type Mode } from './model'
import { StepsList, StoreInspector, TierStrip } from './parts'
import { useDataWords } from './words'
import css from './Data.module.css'

interface DataSearch { view?: string; store?: string; show?: string; reads?: string }

function ModeSwitch({ dp, mode, onChange, comfortable }: { dp: DataPaths; mode: Mode; onChange: (m: Mode) => void; comfortable?: boolean }) {
  const w = useDataWords()
  if (!dp.target) return null
  return <Segmented label={w('view')} value={mode} onChange={onChange} comfortable={comfortable}
    options={[{ id: 'current', label: w('today') }, { id: 'change', label: w('change') }, { id: 'target', label: w('target') }]} />
}

function ReadsSwitch({ on, onChange }: { on: boolean; onChange: (on: boolean) => void }) {
  const w = useDataWords()
  return (
    <AriaButton className={css.switch} onPress={() => onChange(!on)} aria-pressed={on}>
      <span className={css.track} aria-hidden="true"><span className={css.thumb} /></span>{w('showReads')}
    </AriaButton>
  )
}

/** A cluster's members, each a link to focus it; or the stores that need attention first. */
function Overview({ dp, mode, focus, onFocus }: { dp: DataPaths; mode: Mode; focus?: string; onFocus: (id: string) => void }) {
  const w = useDataWords()
  const view = viewOf(dp, mode)
  const stores = new Map(dp.stores.map((s) => [s.id, s]))
  const members = focus && isCluster(focus) ? membersOf(view, focus).filter((m) => stores.has(m)) : null
  const shown = members ? ranked(members.map((m) => stores.get(m)!)) : ranked(dp.stores).filter((s) => s.multi_writer)
  return (
    <div className={css.overview}>
      {members ? <p className={css.hint}>{w('clusterOf', { n: members.length })}</p> : <p className={css.hint}>{w('chooseStore')}</p>}
      <p className={css.gapsLine}>{w('gapsCounted', { n: dp.counts.gaps?.value ?? 0 })}</p>
      <Section title={members ? w('members') : w('topStores')} count={shown.length}>
        <StepsList dp={{ ...dp, stores: shown }} mode={mode} onFocus={onFocus} first={8} />
      </Section>
    </div>
  )
}

function DataBody({ data, dp }: { data: StudioData; dp: DataPaths }) {
  const w = useDataWords()
  const phone = usePhone()
  const navigate = useNavigate()
  const search = useSearch({ strict: false }) as DataSearch
  const mode = modeOf(search.view, dp)
  const stores = useMemo(() => new Map(dp.stores.map((s) => [s.id, s])), [dp])
  const view = viewOf(dp, mode)
  const focus = search.store && (stores.has(search.store) || view.place[search.store]) ? search.store : undefined
  const store = focus ? stores.get(focus) : undefined
  const steps = search.show === 'steps'
  const reads = search.reads === '1'
  const [explore, setExplore] = useState(false)
  const svg = useRef<SVGSVGElement>(null)
  const zoom = useZoom(svg, explore)
  usePageChrome(w('dataTitle'), { to: '/system', label: w('lensMap') }, data.manifest.project.name)

  const go = (patch: Partial<DataSearch>) => navigate({
    to: '/system/data', search: (prev: DataSearch) => Object.fromEntries(Object.entries({ ...prev, ...patch })
      .filter(([, v]) => v !== undefined && v !== '')) as DataSearch,
  })
  const pick = (id: string) => go({ store: id === focus ? undefined : id })
  const names = useMemo(() => dp.stores.map((s) => s.name), [dp])
  const byName = (name: string) => dp.stores.find((s) => s.name === name)?.id
  const counts = w('dataCounts', { s: dp.counts.stores?.value ?? dp.stores.length, e: dp.counts.endpoints?.value ?? 0, w: dp.counts.writers?.value ?? 0 })
  const many = (dp.counts.multi_writer_endpoints?.value ?? 0) + (dp.counts.multi_writer_tables?.value ?? 0)
  const setMode = (m: Mode) => go({ view: m === 'current' ? undefined : m })

  if (!dp.stores.length) {
    return <div className={css.page}><h1 className={css.title}>{w('dataTitle')}</h1><Panel><StateMessage title={w('dataTitle')} sub={w('nothingStored')} /></Panel></div>
  }

  if (phone) {
    return (
      <div className={css.phone}>
        <MissingBanner data={data} />
        <h1 className={css.largeTitle}>{w('dataTitle')}</h1>
        <p className={css.lead}>{counts}{many > 0 && <> · <strong className={css.many}>{w('manyWriters', { n: many })}</strong></>}</p>
        <ModeSwitch dp={dp} mode={mode} onChange={setMode} comfortable />
        <Panel pad><Section title={w('chain')}><TierStrip dp={dp} vertical /></Section></Panel>
        <Button variant="secondary" onPress={() => setExplore(true)}>{w('exploreMap')}</Button>
        <FocusField ids={names} label={w('findStore')} onPick={(n) => { const id = byName(n); if (id) go({ store: id }) }} comfortable />
        {store && <Panel pad><StoreInspector dp={dp} store={store} mode={mode} /></Panel>}
        <Section title={w('allStores')} count={dp.stores.length}>
          <Panel><StepsList dp={dp} mode={mode} focus={focus} onFocus={pick} first={8} /></Panel>
        </Section>
        <ModalOverlay isOpen={explore} onOpenChange={setExplore} isDismissable className={css.exploreOverlay}>
          <Modal className={css.exploreModal}>
            <Dialog className={css.exploreDialog} aria-label={w('dataTitle')}>
              {({ close }) => (
                <>
                  <div className={css.exploreHead}>
                    <IconButton icon="x" label={w('closeMap')} onPress={close} />
                    <Heading slot="title" className={css.exploreTitle}>{w('dataTitle')}</Heading>
                    <span className={css.spacer} />
                    <div className={mapCss.zoom} role="group" aria-label={w('zoomFit')}>
                      <AriaButton className={mapCss.zoomBtn} onPress={() => zoom.zoomBy(1.4)} aria-label={w('zoomIn')}>+</AriaButton>
                      <AriaButton className={mapCss.zoomBtn} onPress={() => zoom.zoomBy(1 / 1.4)} aria-label={w('zoomOut')}>−</AriaButton>
                      <AriaButton className={mapCss.zoomBtn} onPress={zoom.fit} aria-label={w('zoomFit')}>⤢</AriaButton>
                    </div>
                  </div>
                  <div className={css.exploreCanvas}>
                    <DataMap dp={dp} mode={mode} focus={focus} reads={reads} onFocus={pick} svgRef={svg}
                      transform={`translate(${zoom.t.x},${zoom.t.y}) scale(${zoom.t.k})`} className={css.exploreSvg} />
                  </div>
                  {store && (
                    <div className={css.exploreBar} role="status">
                      <span className={css.exploreName}>{store.name}</span>
                      <Button variant="primary" onPress={close}>{w('seeChain')}</Button>
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

  return (
    <div className={css.sys}>
      <section className={css.canvasCol} aria-labelledby="h-data">
        <MissingBanner data={data} />
        <div className={css.toolbar}>
          <h1 className={css.title} id="h-data">{w('dataTitle')}<span className={css.level}>{counts}</span>
            {many > 0 && <span className={css.many}>{w('manyWriters', { n: many })}</span>}</h1>
          <div className={css.toolRow}>
            <ModeSwitch dp={dp} mode={mode} onChange={setMode} />
            <Segmented label={w('showAs')} value={steps ? 'steps' : 'map'} onChange={(v) => go({ show: v === 'steps' ? 'steps' : undefined })}
              options={[{ id: 'map', label: w('asMap') }, { id: 'steps', label: w('asSteps') }]} />
            {!steps && <ReadsSwitch on={reads} onChange={(on) => go({ reads: on ? '1' : undefined })} />}
            <span className={css.spacer} />
            <FocusField ids={names} label={w('findStore')} onPick={(n) => { const id = byName(n); if (id) go({ store: id }) }} />
          </div>
          <TierStrip dp={dp} />
        </div>
        <div className={css.scroll} data-scroll-y="">
          {steps
            ? <div className={css.stepsPage}><Panel><StepsList dp={dp} mode={mode} focus={focus} onFocus={pick} first={60} /></Panel></div>
            : <>
                <DataMap dp={dp} mode={mode} focus={focus} reads={reads} onFocus={pick} className={css.fitSvg} />
                <div className={css.legendRow}><DataLegend mode={mode} inline /></div>
              </>}
        </div>
      </section>
      <aside className={css.inspector} aria-label={w('evidence')}>
        {store ? <StoreInspector dp={dp} store={store} mode={mode} /> : <Overview dp={dp} mode={mode} focus={focus} onFocus={pick} />}
      </aside>
    </div>
  )
}

export function DataPathsPage() {
  const w = useDataWords()
  return (
    <WithData>{(data) => data.data_paths
      ? <DataBody data={data} dp={data.data_paths} />
      : <div className={css.page}><Panel><StateMessage title={w('noData')} sub={w('noDataSub')} /></Panel></div>}
    </WithData>
  )
}
