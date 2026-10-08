// System: the project as a territory (DESIGN.md §6). One switch shows today (dots coloured by findings), the change
// (today's dots coloured by their operation) or the target architecture (its components coloured by how they come
// about). Desktop: the canvas (zoom, pan, fit, legend, minimap) beside a 360px inspector; or the ranked list in its
// place. Phone: the map's preview, a full-screen explorer, the focused component and the ranked list. A report with
// no map (studio/system.json) keeps the list page (pages/System.tsx).
import { useNavigate, useSearch } from '@tanstack/react-router'
import { useEffect, useMemo, useRef, useState } from 'react'
import { Dialog, Heading, Modal, ModalOverlay } from 'react-aria-components'
import { Button, IconButton } from '../components/Button'
import { Segmented } from '../components/Controls'
import { Go } from '../components/Go'
import { Panel, Section } from '../components/Panel'
import type { Operation, SystemMap } from '../data/system'
import type { StudioData } from '../data/types'
import { usePrefs } from '../i18n/prefs'
import { N } from '../i18n/text'
import { FocusField } from '../map/FocusField'
import { MODES, type MapMode } from '../map/model'
import { Inspector, Legend, MapCanvas, RankedList } from '../map/parts'
import { TerritoryMap } from '../map/TerritoryMap'
import { OP_WORD, useMapWords } from '../map/words'
import { usePageChrome } from '../shell/chrome'
import { MissingBanner, WithData } from '../shell/Layout'
import { SystemPage } from './System'
import css from './SystemMap.module.css'

interface SystemSearch { focus?: string; view?: string; show?: string; op?: string }

export function usePhone(): boolean {
  const query = '(max-width: 767px)'
  const [phone, setPhone] = useState(() => typeof window !== 'undefined' && window.matchMedia(query).matches)
  useEffect(() => {
    const list = window.matchMedia(query)
    const on = () => setPhone(list.matches)
    list.addEventListener('change', on)
    return () => list.removeEventListener('change', on)
  }, [])
  return phone
}

function modeOf(view: string | undefined): MapMode {
  return MODES.includes(view as MapMode) ? (view as MapMode) : 'current'
}

function ModeSwitch({ mode, onChange, comfortable }: { mode: MapMode; onChange: (m: MapMode) => void; comfortable?: boolean }) {
  const w = useMapWords()
  return (
    <Segmented label={w('mapView')} value={mode} onChange={onChange} comfortable={comfortable} options={[
      { id: 'current', label: w('mapToday') }, { id: 'change', label: w('mapChange') }, { id: 'target', label: w('mapTarget') },
    ]} />
  )
}

/** The regions of the shown map, each a link to its largest component, when nothing is focused. */
function Overview({ system, mode, onFocus }: { system: SystemMap; mode: MapMode; onFocus: (id: string) => void }) {
  const w = useMapWords()
  const { lang } = usePrefs()
  const view = mode === 'target' ? system.target : system.current
  return (
    <div className={css.overview}>
      <p className={css.hint}>{w('chooseOnMap')}</p>
      <table className={css.regions}>
        <thead>
          <tr><th scope="col">{w('region')}</th><th scope="col">{w('componentsShort')}</th><th scope="col">{w('filesShort')}</th>
            {mode !== 'target' && <th scope="col">{w('findingsShort')}</th>}</tr>
        </thead>
        <tbody>
          {view.regions.map((r) => (
            <tr key={r.id}>
              <th scope="row">
                <button type="button" className={css.regLink} onClick={() => onFocus(r.lead)}>
                  {r.name.ident ? <bdi dir="ltr" className="id">{r.name[lang]}</bdi> : r.name[lang]}
                </button>
              </th>
              <td><N value={r.components} /></td><td><N value={r.files} /></td>
              {mode !== 'target' && <td className={css.strong}><N value={r.findings ?? 0} /></td>}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function SystemMapBody({ data, system }: { data: StudioData; system: SystemMap }) {
  const { t } = usePrefs()
  const w = useMapWords()
  const phone = usePhone()
  const search = useSearch({ strict: false }) as SystemSearch
  const navigate = useNavigate()
  const mode = modeOf(search.view)
  const view = mode === 'target' ? system.target : system.current
  const focus = view.nodes.some((n) => n.id === search.focus) ? search.focus : undefined
  const only = (['retain', 'modify', 'rebuild', 'delete', 'merge', 'introduce'] as Operation[]).find((op) => op === search.op)
  const list = search.show === 'list'
  const [centre, setCentre] = useState<string | undefined>()
  const [explore, setExplore] = useState(false)
  const focusCard = useRef<HTMLDivElement>(null)
  usePageChrome(t('system'), undefined, data.manifest.project.name)

  const go = (patch: Partial<SystemSearch>) => navigate({
    to: '/system', search: (prev: SystemSearch) => {
      const next = { ...prev, ...patch }
      return Object.fromEntries(Object.entries(next).filter(([, v]) => v !== undefined && v !== '')) as SystemSearch
    },
  })
  const setFocus = (id: string) => go({ focus: id === focus ? undefined : id })
  const pick = (id: string) => { go({ focus: id }); setCentre(id) }
  const setMode = (m: MapMode) => go({ view: m === 'current' ? undefined : m, focus: undefined, op: undefined })
  const ids = useMemo(() => view.nodes.map((n) => n.id).sort(), [view])
  const counts = mode === 'target'
    ? w('targetCount', { r: system.target.regions.length, c: system.target.nodes.length, e: system.target.edges.length })
    : w('regionsCount', { r: system.current.regions.length, c: system.current.nodes.length, e: system.current.edges.length })

  // a focus chosen on this page brings its card into view; the focus a link opened with does not move the page
  const first = useRef(true)
  useEffect(() => {
    if (first.current) { first.current = false; return }
    if (phone && focus && !explore) focusCard.current?.scrollIntoView({ block: 'start', behavior: 'smooth' })
  }, [phone, focus, explore])

  if (phone) {
    return (
      <div className={css.phone}>
        <MissingBanner data={data} />
        <h1 className={css.largeTitle}>{w('systemMap')}</h1>
        <ModeSwitch mode={mode} onChange={setMode} comfortable />
        <figure className={css.preview}>
          <button type="button" className={css.previewBtn} onClick={() => setExplore(true)} aria-label={w('exploreMap')}>
            <TerritoryMap view={view} mode={mode} variant="preview" focus={focus} only={only} />
          </button>
          <figcaption className={css.cap}>
            <span>{counts}</span>
            <Button variant="ghost" onPress={() => setExplore(true)}>{w('exploreMap')}</Button>
          </figcaption>
        </figure>
        <Legend system={system} mode={mode} view={view} inline />
        <FocusField ids={ids} label={w('findComponent')} onPick={pick} comfortable />
        {focus && (
          <div ref={focusCard} className={css.focusCard}>
            <Panel pad><Inspector system={system} mode={mode} id={focus} onFocus={pick} touch /></Panel>
          </div>
        )}
        <Section title={w('allComponents')} count={view.nodes.length} unit={mode === 'target' ? undefined : w('bySeverityWeight')}>
          <RankedList system={system} mode={mode} focus={focus} onFocus={pick} />
        </Section>
        <ModalOverlay isOpen={explore} onOpenChange={setExplore} isDismissable className={css.exploreOverlay}>
          <Modal className={css.exploreModal}>
            <Dialog className={css.exploreDialog} aria-label={w('systemMap')}>
              {({ close }) => (
                <>
                  <MapCanvas system={system} mode={mode} focus={focus} only={only} onFocus={setFocus} legend={false} minimap={false}
                    className={css.exploreCanvas}
                    head={<><IconButton icon="x" label={w('closeMap')} onPress={close} /><Heading slot="title" className={css.exploreTitle}>{w('systemMap')}</Heading></>} />
                  {focus && (
                    <div className={css.exploreBar} role="status">
                      <bdi dir="ltr" className="id">{focus}</bdi>
                      <Button variant="primary" onPress={close}>{w('seeDetails')}</Button>
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

  const title = <h1 className={css.title} id="h-map">{w('systemMap')}<span className={css.level}>{counts}</span></h1>
  const head = (
    <>
      <ModeSwitch mode={mode} onChange={setMode} />
      <Segmented label={w('showAs')} value={list ? 'list' : 'map'} onChange={(v) => go({ show: v === 'list' ? 'list' : undefined })}
        options={[{ id: 'map', label: w('asMap') }, { id: 'list', label: w('asList') }]} />
      <FocusField ids={ids} label={w('focusComponent')} onPick={pick} />
      {only && <Go to="/system" search={{ view: search.view }} className={css.only} label={w('showAll')}>{w(OP_WORD[only])}<span aria-hidden="true">×</span></Go>}
    </>
  )
  return (
    <div className={css.sys}>
      <section className={css.canvasCol} aria-labelledby="h-map">
        <MissingBanner data={data} />
        <MapCanvas key={list ? 'list' : 'map'} system={system} mode={mode} focus={focus} only={only} onFocus={setFocus} centreOn={centre} title={title} head={head}
          className={css.canvasBox}
          replace={list ? <div className={css.listView}><RankedList system={system} mode={mode} focus={focus} onFocus={setFocus} first={60} /></div> : undefined} />
        {(system.capped ?? 0) > 0 && <p className={css.capped}>{w('capped', { n: system.current.nodes.length })}</p>}
      </section>
      <aside className={css.inspector} aria-label={t('inspector')}>
        {focus ? <Inspector system={system} mode={mode} id={focus} onFocus={pick} /> : <Overview system={system} mode={mode} onFocus={pick} />}
      </aside>
    </div>
  )
}

export function SystemMapPage() {
  return <WithData>{(data) => data.system && data.system.current.nodes.length > 0
    ? <SystemMapBody data={data} system={data.system} />
    : <SystemPage />}</WithData>
}
