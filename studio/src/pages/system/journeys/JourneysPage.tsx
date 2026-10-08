// System -> User journeys (#/system/journeys): the screens a person opens and the links between them, the main tasks
// as paths from the start, and the screens that are broken, out of reach, dead ends or duplicates. Today / Change /
// Target; Map or Steps; a task; "show hidden". Desktop: the canvas beside a 360px inspector. Phone: the map's preview
// (opening a full-screen sheet with pan and pinch), then the task and its steps, or every screen by clicks from the
// start. The URL holds the view: ?view=&show=&task=&focus=&hidden=1&flag=.
import { useNavigate, useSearch } from '@tanstack/react-router'
import { useMemo, useState } from 'react'
import { Dialog, Heading, Modal, ModalOverlay } from 'react-aria-components'
import { Button, IconButton } from '../../../components/Button'
import { Segmented } from '../../../components/Controls'
import { Panel, StateMessage } from '../../../components/Panel'
import type { Journeys, ScreenFlag } from '../../../data/journeys'
import type { StudioData } from '../../../data/types'
import { usePrefs } from '../../../i18n/prefs'
import { Id } from '../../../i18n/text'
import { usePageChrome } from '../../../shell/chrome'
import { MissingBanner, WithData } from '../../../shell/Layout'
import { usePhone } from '../../SystemMap'
import { HiddenSwitch, SystemViews } from '../SystemViews'
import { useJourneyWords } from '../words'
import { FLAGS, JOURNEY_MODES, unseenBy, type JourneyMode } from './model'
import { FlagFilter, JourneyCanvas, Legend, MenuPanel, Missing, Overview, ScreenPanel, StepsView, TaskPanel } from './parts'
import { JourneyMap } from './JourneyMap'
import css from './Journeys.module.css'

interface JourneySearch { view?: string; show?: string; task?: string; focus?: string; hidden?: string; flag?: string }

function ModeSwitch({ mode, onChange, comfortable }: { mode: JourneyMode; onChange: (m: JourneyMode) => void; comfortable?: boolean }) {
  const w = useJourneyWords()
  return (
    <Segmented label={w('mapView')} value={mode} onChange={onChange} comfortable={comfortable} options={[
      { id: 'current', label: w('mapToday') }, { id: 'change', label: w('mapChange') }, { id: 'target', label: w('mapTarget') },
    ]} />
  )
}

function TaskSelect({ j, value, onChange }: { j: Journeys; value?: string; onChange: (id: string | undefined) => void }) {
  const w = useJourneyWords()
  const { lang } = usePrefs()
  return (
    <label className={css.select}>
      <span className="sr">{w('task')}</span>
      <select value={value ?? ''} onChange={(e) => onChange(e.target.value || undefined)}>
        <option value="">{w('noTask')}</option>
        {j.tasks.filter((t) => !t.dead).map((t) => <option key={t.id} value={t.id}>{t.name[lang]}</option>)}
      </select>
    </label>
  )
}

function JourneysBody({ data, j }: { data: StudioData; j: Journeys }) {
  const { t } = usePrefs()
  const w = useJourneyWords()
  const phone = usePhone()
  const search = useSearch({ strict: false }) as JourneySearch
  const navigate = useNavigate()
  const [explore, setExplore] = useState(false)
  const mode: JourneyMode = JOURNEY_MODES.includes(search.view as JourneyMode) ? (search.view as JourneyMode) : 'current'
  const steps = search.show === 'steps'
  const task = j.tasks.find((x) => x.id === search.task)
  const showHidden = search.hidden === '1'
  const flag = FLAGS.find((f) => f === search.flag)
  const ids = new Set([...j.screens.filter((s) => showHidden || s.kind === 'page').map((s) => s.id), ...j.menus.map((m) => m.id)])
  const focus = search.focus && ids.has(search.focus) ? search.focus : undefined
  usePageChrome(w('journeys'), undefined, data.manifest.project.name)

  const unseen = useMemo(() => {
    const per = new Map<string, number>()
    for (const l of data.hidden?.links ?? []) if (l.to !== 'dead' && l.to !== 'build' && l.to !== 'screens') per.set(l.from, (per.get(l.from) ?? 0) + l.count)
    return unseenBy(j, per)
  }, [data.hidden, j])

  const go = (patch: Partial<JourneySearch>) => navigate({
    to: '/system/journeys', search: (prev: JourneySearch) => {
      const next = { ...prev, ...patch }
      return Object.fromEntries(Object.entries(next).filter(([, v]) => v !== undefined && v !== '')) as JourneySearch
    },
  })
  const setFocus = (id: string) => go({ focus: id === focus ? undefined : id, task: undefined })
  const pick = (id: string) => go({ focus: id, task: undefined })
  const setTask = (id: string | undefined) => go({ task: id, focus: undefined, flag: undefined })
  const setFlag = (f: ScreenFlag | undefined) => go({ flag: f, focus: undefined, task: undefined })
  const setMode = (m: JourneyMode) => go({ view: m === 'current' ? undefined : m })
  const setHidden = (on: boolean) => go({ hidden: on ? '1' : undefined })
  const count: Record<ScreenFlag, number> = {
    broken_link: j.counts.broken.value ?? 0, no_way_in: j.counts.no_way_in.value ?? 0, dead_end: j.counts.dead_ends.value ?? 0, duplicate: j.counts.duplicates.value ?? 0,
  }
  const counts = w('journeysCount', { s: j.counts.screens.value ?? 0, l: j.counts.links.value ?? 0, t: j.tasks.filter((x) => !x.dead).length })
  const inspector = task ? <TaskPanel j={j} task={task} onFocus={pick} />
    : focus?.startsWith('menu:') ? <MenuPanel j={j} id={focus} onFocus={pick} />
    : focus ? <ScreenPanel j={j} hidden={data.hidden} id={focus} onFocus={pick} onTask={(id) => setTask(id)} />
    : <Overview j={j} flag={flag} onFlag={setFlag} onTask={(id) => setTask(id)} />

  if (phone) {
    return (
      <div className={css.phone}>
        <MissingBanner data={data} />
        <SystemViews current="journeys" />
        <h1 className={css.largeTitle}>{w('journeys')}</h1>
        <p className={css.lead}>{w('journeysLead', { s: j.counts.screens.value ?? 0, l: j.counts.links.value ?? 0, t: j.tasks.filter((x) => !x.dead).length })}</p>
        <ModeSwitch mode={mode} onChange={setMode} comfortable />
        <figure className={css.preview}>
          <button type="button" className={css.previewBtn} onClick={() => setExplore(true)} aria-label={w('exploreMap')}>
            <JourneyMap journeys={j} mode={mode} variant="preview" focus={focus} task={task} flag={flag} showHidden={showHidden} unseen={unseen} />
          </button>
          <figcaption className={css.cap}>
            <span>{counts}</span>
            <Button variant="ghost" onPress={() => setExplore(true)}>{w('exploreMap')}</Button>
          </figcaption>
        </figure>
        <HiddenSwitch on={showHidden} onChange={setHidden} />
        <Legend mode={mode} showHidden={showHidden} />
        <TaskSelect j={j} value={task?.id} onChange={setTask} />
        <FlagFilter count={count} flag={flag} onFlag={setFlag} />
        {(task || focus) && <Panel pad>{inspector}</Panel>}
        {!task && (
          <section className={css.stepsBox} aria-labelledby="h-steps">
            <h2 id="h-steps" className={css.sectionTitle}>{w('byDepth')}</h2>
            <StepsView j={j} focus={focus} onFocus={pick} />
          </section>
        )}
        {!task && !focus && <Missing j={j} />}
        <ModalOverlay isOpen={explore} onOpenChange={setExplore} isDismissable className={css.exploreOverlay}>
          <Modal className={css.exploreModal}>
            <Dialog className={css.exploreDialog} aria-label={w('journeys')}>
              {({ close }) => (
                <>
                  <JourneyCanvas journeys={j} mode={mode} focus={focus} task={task} flag={flag} showHidden={showHidden} unseen={unseen}
                    onFocus={setFocus} legend={false} className={css.exploreCanvas}
                    head={<><IconButton icon="x" label={w('closeMap')} onPress={close} /><Heading slot="title" className={css.exploreTitle}>{w('journeys')}</Heading></>} />
                  {focus && (
                    <div className={css.exploreBar} role="status">
                      <Id value={j.screens.find((s) => s.id === focus)?.route ?? w('menu')} />
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

  const title = <h1 className={css.title} id="h-journeys">{w('journeys')}<span className={css.level}>{counts}</span></h1>
  const head = (
    <>
      <ModeSwitch mode={mode} onChange={setMode} />
      <Segmented label={w('showAs')} value={steps ? 'steps' : 'map'} onChange={(v) => go({ show: v === 'steps' ? 'steps' : undefined })}
        options={[{ id: 'map', label: w('asMap') }, { id: 'steps', label: w('asSteps') }]} />
      <TaskSelect j={j} value={task?.id} onChange={setTask} />
      <HiddenSwitch on={showHidden} onChange={setHidden} />
    </>
  )
  return (
    <div className={css.page}>
      <section className={css.canvasCol} aria-labelledby="h-journeys">
        <MissingBanner data={data} />
        <div className={css.viewsRow}><SystemViews current="journeys" /></div>
        <JourneyCanvas key={steps ? 'steps' : 'map'} journeys={j} mode={mode} focus={focus} task={task} flag={flag} showHidden={showHidden} unseen={unseen}
          onFocus={setFocus} title={title} head={head} className={css.canvasBox}
          replace={steps ? <div className={css.stepsView}><StepsView j={j} task={task} focus={focus} onFocus={pick} /></div> : undefined} />
      </section>
      <aside className={css.inspector} aria-label={t('inspector')}>{inspector}</aside>
    </div>
  )
}

export function JourneysPage() {
  const w = useJourneyWords()
  return (
    <WithData>{(data) => data.journeys && data.journeys.screens.length > 0
      ? <JourneysBody data={data} j={data.journeys} />
      : (
        <div className={css.emptyPage}>
          <SystemViews current="journeys" />
          <Panel><StateMessage title={w('noJourneys')} sub={w('noJourneysSub')} /></Panel>
          {data.journeys && <Panel pad><Missing j={data.journeys} /></Panel>}
        </div>
      )}</WithData>
  )
}
