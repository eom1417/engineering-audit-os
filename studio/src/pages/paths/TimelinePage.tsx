// #/change/timeline: the fix plan in the order it runs (studio/paths.json timeline, from plan.json's waves). Waves are
// the columns, the plan's steps the rows; a cell counts the tasks of that step in that wave, and choosing it lists
// them with what each waits for (a prerequisite, or an earlier task on the same file). Phone: the waves as a list.
// ?step=<id>, ?wave=<n>.
import { useNavigate, useSearch } from '@tanstack/react-router'
import { useMemo, useState } from 'react'
import { Button as AriaButton } from 'react-aria-components'
import { Button } from '../../components/Button'
import { Go } from '../../components/Go'
import { Icon } from '../../components/Icon'
import { Panel, Section, Skeleton, StateMessage } from '../../components/Panel'
import { Sheet } from '../../components/Sheet'
import type { StudioData } from '../../data/types'
import { usePrefs } from '../../i18n/prefs'
import { Id, N, Txt } from '../../i18n/text'
import { usePageChrome } from '../../shell/chrome'
import { layout, MissingBanner, PageTitle, WithData } from '../../shell/Layout'
import { usePhone } from '../SystemMap'
import { usePaths, type Timeline, type TimelineTask } from './model'
import { usePathWords } from './words'
import css from './paths.module.css'

interface TimelineSearch { step?: string; wave?: string }

/** Four bins of a cell's task count, for its dot's shade (the number is always written). */
function bin(n: number): 1 | 2 | 3 | 4 {
  return n <= 2 ? 1 : n <= 9 ? 2 : n <= 29 ? 3 : 4
}

export function TaskRows({ tasks }: { tasks: TimelineTask[] }) {
  const w = usePathWords()
  const { t } = usePrefs()
  const [all, setAll] = useState(false)
  const shown = all ? tasks : tasks.slice(0, 20)
  return (
    <>
      <ul className={css.taskList}>
        {shown.map((task) => (
          <li key={task.id} className={css.task}>
            <span className={css.taskHead}>
              <Go to="/problems" search={{ card: task.id }} className={css.waitLink}><Id value={task.id} /></Go>
              <span><Txt>{task.title}</Txt></span>
            </span>
            <span className={css.waits}>
              {task.waits.length === 0 ? w('noWaits') : <>
                <span>{w('waitsFor')}:</span>
                {task.waits.map((wait) => (
                  <span key={wait.task}>
                    <Go to="/problems" search={{ card: wait.task }} className={css.waitLink}><Id value={wait.task} /></Go>
                    {' '}({w(wait.why === 'prerequisite' ? 'why_prerequisite' : 'why_same_file')}{wait.detail && wait.why === 'same_file' ? <>: <Id value={wait.detail} keep={2} /></> : null})
                  </span>
                ))}
                {task.more > 0 && <span>{w('moreWaits', { n: task.more })}</span>}
              </>}
            </span>
          </li>
        ))}
      </ul>
      {tasks.length > shown.length && <Button variant="ghost" onPress={() => setAll(true)}>{t('showAllN', { n: tasks.length })}</Button>}
    </>
  )
}

export function Grid({ timeline, step, wave, onPick }: { timeline: Timeline; step?: string; wave?: number; onPick: (step: string | undefined, wave: number | undefined) => void }) {
  const w = usePathWords()
  const cell = useMemo(() => {
    const out = new Map<string, number>()
    for (const wv of timeline.waves) for (const s of wv.steps) out.set(`${s.step ?? ''}|${wv.wave}`, s.tasks)
    return out
  }, [timeline])
  const rows = [...timeline.steps, ...(timeline.tasks.some((task) => !task.step) ? [{ id: '', title: w('noStep'), tasks: 0, first: null, last: null }] : [])]
  return (
    <div className={css.tlScroll} data-scroll-x="">
      <table className={css.tlGrid}>
        <thead>
          <tr>
            <th scope="col" className={css.tlCorner}>{w('step')}</th>
            {timeline.waves.map((wv) => (
              <th key={wv.wave} scope="col" className={css.tlWave} data-on={wave === wv.wave && !step ? '' : undefined}>
                <AriaButton className={css.tlBtn} aria-label={w('wave', { n: wv.wave })} aria-pressed={wave === wv.wave && !step} onPress={() => onPick(undefined, wv.wave)}>
                  <span aria-hidden="true">{wv.wave}</span>
                </AriaButton>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((s) => (
            <tr key={s.id || 'none'}>
              <th scope="row" className={css.tlStep}>
                <AriaButton className={css.stepBtn} aria-pressed={step === s.id && wave === undefined} onPress={() => onPick(s.id, undefined)}>
                  <span className={css.tlStepId}><Id value={s.id || '—'} /></span>
                  <span className={css.tlStepName}><Txt>{s.title}</Txt></span>
                </AriaButton>
              </th>
              {timeline.waves.map((wv) => {
                const n = cell.get(`${s.id}|${wv.wave}`) ?? 0
                return (
                  <td key={wv.wave} className={css.tlCell}>
                    {n > 0 && (
                      <AriaButton className={css.tlBtn} aria-pressed={step === s.id && wave === wv.wave} onPress={() => onPick(s.id, wv.wave)}
                        aria-label={w('cellAria', { s: s.id || w('noStep'), w: wv.wave, n })}>
                        <span className={[css.tlDot, css[`tl${bin(n)}`]].join(' ')} aria-hidden="true">{n}</span>
                      </AriaButton>
                    )}
                  </td>
                )
              })}
            </tr>
          ))}
          <tr className={css.tlTotal}>
            <th scope="row" className={css.tlStep}>{w('tasksN', { n: timeline.tasks.length })}</th>
            {timeline.waves.map((wv) => <td key={wv.wave}><N value={wv.tasks} /></td>)}
          </tr>
        </tbody>
      </table>
    </div>
  )
}

function TimelineView({ data, timeline }: { data: StudioData; timeline: Timeline }) {
  const w = usePathWords()
  const { t } = usePrefs()
  const phone = usePhone()
  const navigate = useNavigate()
  const search = useSearch({ strict: false }) as TimelineSearch
  const step = timeline.steps.some((s) => s.id === search.step) || search.step === '' ? search.step : undefined
  const wave = timeline.waves.some((wv) => String(wv.wave) === search.wave) ? Number(search.wave) : undefined
  const [sheet, setSheet] = useState(false)
  const pick = (s: string | undefined, wv: number | undefined) => {
    navigate({ to: '/change/timeline', replace: true, search: { step: s || undefined, wave: wv === undefined ? undefined : String(wv) } })
    if (phone) setSheet(true)
  }
  const chosen = timeline.tasks.filter((task) => (step === undefined || (task.step ?? '') === step) && (wave === undefined || task.wave === wave))
  const stepTitle = step !== undefined ? timeline.steps.find((s) => s.id === step)?.id ?? w('noStep') : undefined
  const heading = stepTitle && wave ? w('cellTasks', { s: stepTitle, w: wave }) : wave ? w('waveTasks', { w: wave }) : stepTitle ?? ''
  const count = (key: string) => timeline.counts[key]?.value ?? 0
  const details = (step !== undefined || wave !== undefined) ? (
    <Section title={heading} count={chosen.length}><Panel pad><TaskRows tasks={chosen} /></Panel></Section>
  ) : <p className={css.lead}>{w('chooseCell')}</p>
  return (
    <div className={layout.page}>
      <MissingBanner data={data} />
      <Go to="/change" className={css.back}><Icon name="back" />{t('journeyAndPlan')}</Go>
      <PageTitle title={w('planTimeline')} lead={w('timelineLead')} />
      <p className={css.lead}>{w('timelineCount', { n: count('waves'), t: count('tasks'), w: count('waits') })}</p>
      {phone ? (
        <>
          <Panel>
            <ul className={css.waveList} aria-label={w('planTimeline')}>
              {timeline.waves.map((wv) => (
                <li key={wv.wave}>
                  <AriaButton className={[css.waveRow, css.stepBtn].join(' ')} onPress={() => pick(undefined, wv.wave)}>
                    <span className={css.waveHead}><span>{w('wave', { n: wv.wave })}</span><span>{w('tasksN', { n: wv.tasks })}</span></span>
                    <span className={css.waveSteps}>{wv.steps.map((s) => <span key={s.step ?? 'none'}><Id value={s.step ?? '—'} /> <N value={s.tasks} /></span>)}</span>
                  </AriaButton>
                </li>
              ))}
            </ul>
          </Panel>
          <Sheet isOpen={sheet && (step !== undefined || wave !== undefined)} onOpenChange={setSheet} title={heading}>
            <TaskRows tasks={chosen} />
          </Sheet>
        </>
      ) : (
        <>
          <Grid timeline={timeline} step={step} wave={wave} onPick={pick} />
          {details}
        </>
      )}
    </div>
  )
}

function TimelineBody({ data }: { data: StudioData }) {
  const w = usePathWords()
  const { t } = usePrefs()
  const state = usePaths(data)
  usePageChrome(w('planTimeline'), { to: '/change', label: t('journeyAndPlan') }, data.manifest.project.name)
  if (state.kind === 'loading') return <div className={layout.page}><Panel><Skeleton label={t('loading')} /></Panel></div>
  const timeline = state.kind === 'ready' ? state.paths.timeline : null
  if (!timeline) {
    return <div className={layout.page}><PageTitle title={w('planTimeline')} /><Panel><StateMessage title={w('noTimeline')} sub={w('noTimelineSub')} /></Panel></div>
  }
  return <TimelineView data={data} timeline={timeline} />
}

export function TimelinePage() {
  return <WithData>{(data) => <TimelineBody data={data} />}</WithData>
}

/** The entry on the Change page: the plan's order in one line, and the way to the timeline. */
export function TimelineEntry({ data }: { data: StudioData }) {
  const w = usePathWords()
  const state = usePaths(data)
  const timeline = state.kind === 'ready' ? state.paths.timeline : null
  if (!timeline) return null
  return (
    <Panel className={css.entryCard}>
      <span className={css.entryText}>
        <span>{w('planTimeline')}</span>
        <span>{w('timelineCard', { n: timeline.waves.length, t: timeline.tasks.length })}</span>
      </span>
      <Go to="/change/timeline" className={css.back}>{w('openTimeline')}<Icon name="chevron" /></Go>
    </Panel>
  )
}
