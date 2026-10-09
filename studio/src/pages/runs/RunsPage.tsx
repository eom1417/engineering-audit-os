// Runs (#/runs): what runs now, the queue in the order the person chooses (one runs at a time), and every run before,
// searchable by its words, cards and outcome. In a snapshot it says how to start the live Studio, and offers an
// example run replayed from a recording.
import { useNavigate, useSearch } from '@tanstack/react-router'
import { useMemo } from 'react'
import { Button, IconButton, copyText } from '../../components/Button'
import { SearchField, Segmented } from '../../components/Controls'
import { FoldList, Panel, Section, StateMessage } from '../../components/Panel'
import { useToast } from '../../components/Toast'
import { useCmdWords } from '../../command/words'
import { SNAPSHOT } from '../../data/actions/contract'
import { useActions } from '../../data/actions/store'
import { ACTIVE, ActionError, TERMINAL, type Run } from '../../data/actions/types'
import { useStudio } from '../../data/context'
import { normalize } from '../../search/normalize'
import { usePrefs } from '../../i18n/prefs'
import { usePageChrome } from '../../shell/chrome'
import { layout, PageTitle } from '../../shell/Layout'
import { RunRow } from './parts'
import { labelOf } from '../../data/actions/derive'
import css from './runs.module.css'

type Show = 'all' | 'done' | 'unfinished'
interface RunsSearch { q?: string; show?: Show }

export function DemoBanner() {
  const w = useCmdWords()
  const actions = useActions()
  const navigate = useNavigate()
  return (
    <div className={css.demo} role="note">
      <span>{w('demoBanner')}</span>
      <Button variant="ghost" onPress={() => { actions.stopDemo(); navigate({ to: '/runs' }) }}>{w('leaveDemo')}</Button>
    </div>
  )
}

/** What a snapshot says instead of running: the command that starts the live Studio, and an example to watch. */
export function SnapshotPanel() {
  const w = useCmdWords()
  const { lang } = usePrefs()
  const toast = useToast()
  const actions = useActions()
  return (
    <Panel className={css.snapshot} label={w('snapshotTitle')}>
      <h2 className={css.panelTitle}>{w('snapshotTitle')}</h2>
      <p className={css.snapLead}>{SNAPSHOT.text[lang]}</p>
      <div className={css.command}>
        <code><bdi dir="ltr">{SNAPSHOT.command}</bdi></code>
        <Button variant="secondary" icon="copy" onPress={async () => toast((await copyText(SNAPSHOT.command)) ? `${w('copyCommand')} ✓` : '')}>{w('copyCommand')}</Button>
      </div>
      <Button variant="primary" icon="play" onPress={() => actions.startDemo()}>{w('watchExample')}</Button>
    </Panel>
  )
}

function Queue({ queued }: { queued: Run[] }) {
  const actions = useActions()
  const w = useCmdWords()
  const toast = useToast()
  const { lang } = usePrefs()
  const move = async (from: number, to: number) => {
    if (!actions.client) return
    const order = queued.map((r) => r.id)
    const [id] = order.splice(from, 1)
    order.splice(to, 0, id)
    const before = actions.queue
    actions.setQueue(order)
    try { actions.setQueue(await actions.client.reorder(order)) } catch (error) {
      actions.setQueue(before)
      toast(error instanceof ActionError ? error.message : String(error))
    }
  }
  const remove = async (run: Run) => {
    if (!actions.client) return
    actions.setQueue(actions.queue.filter((id) => id !== run.id))
    actions.patch(run.id, { state: 'stopped' })
    try { await actions.client.control(run.id, 'stop') } catch (error) { toast(error instanceof ActionError ? error.message : String(error)) }
    void actions.refresh()
  }
  if (!queued.length) return <Panel><StateMessage icon="clock" title={w('queueEmpty')} /></Panel>
  return (
    <Panel>
      <ol className={css.queue} aria-label={w('queue')}>
        {queued.map((run, i) => (
          <li key={run.id} className={css.queueRow}>
            <span className={css.queueN} aria-hidden="true">{i + 1}</span>
            <div className={css.queueMain}><RunRow run={run} end={null} /></div>
            <div className={css.queueTools}>
              {i > 0 && <IconButton icon="up" label={w('moveUp', { label: labelOf(run.label, lang) })} onPress={() => move(i, i - 1)} data-hook={`queue-up:${run.id}`} />}
              {i < queued.length - 1 && <IconButton icon="down" label={w('moveDown', { label: labelOf(run.label, lang) })} onPress={() => move(i, i + 1)} />}
              <IconButton icon="x" label={w('removeFromQueue', { label: labelOf(run.label, lang) })} onPress={() => remove(run)} />
            </div>
          </li>
        ))}
      </ol>
    </Panel>
  )
}

function RunsBody() {
  const actions = useActions()
  const w = useCmdWords()
  const { lang } = usePrefs()
  const search = useSearch({ strict: false }) as RunsSearch
  const navigate = useNavigate()
  const set = (patch: Partial<RunsSearch>) => navigate({ to: '/runs', search: { ...search, ...patch }, replace: true })
  const show: Show = search.show ?? 'all'
  const byId = useMemo(() => new Map(actions.runs.map((run) => [run.id, run])), [actions.runs])
  const active = actions.runs.filter((run) => ACTIVE.includes(run.state))
  const queued = [...actions.queue.map((id) => byId.get(id)).filter((run): run is Run => Boolean(run && run.state === 'queued')),
    ...actions.runs.filter((run) => run.state === 'queued' && !actions.queue.includes(run.id))]
  const past = useMemo(() => {
    const needle = normalize(search.q ?? '')
    return actions.runs.filter((run) => TERMINAL.includes(run.state))
      .filter((run) => show === 'all' || (show === 'done' ? run.state === 'done' : run.state !== 'done'))
      .filter((run) => !needle || normalize([run.label.en, run.label.ar, run.action, run.verb ?? '', run.state, run.outcome ?? '', ...run.cards,
        run.result?.branch ?? ''].join(' ')).includes(needle))
  }, [actions.runs, search.q, show])
  const all = actions.runs.filter((run) => TERMINAL.includes(run.state)).length

  return (
    <>
      <Section title={w('now')}>
        {active.length ? <Panel><ul>{active.map((run) => <li key={run.id}><RunRow run={run} /></li>)}</ul></Panel>
          : <Panel><StateMessage icon="pulse" title={w('nothingRunning')} sub={w('nothingRunningSub')} /></Panel>}
      </Section>
      <Section title={w('queue')} count={queued.length} unit={w('queueLead')}>
        <Queue queued={queued} />
      </Section>
      <Section title={w('history')} count={all}>
        <div className={css.historyTools}>
          <SearchField label={w('searchRuns')} placeholder={w('searchRuns')} value={search.q ?? ''} onChange={(q) => set({ q: q || undefined })} />
          <Segmented label={w('history')} value={show} onChange={(next) => set({ show: next === 'all' ? undefined : next })}
            options={[{ id: 'all', label: w('all') }, { id: 'done', label: w('finished') }, { id: 'unfinished', label: w('notFinished') }]} />
        </div>
        {past.length ? <Panel><FoldList items={past} first={8} label={w('history')} render={(run) => <RunRow run={run} />} /></Panel>
          : <Panel><StateMessage title={all ? w('noRunsMatch') : w('noRuns')} /></Panel>}
      </Section>
      <span className="sr" aria-live="polite">{active[0] ? labelOf(active[0].label, lang) : ''}</span>
    </>
  )
}

export function RunsPage() {
  const actions = useActions()
  const w = useCmdWords()
  const data = useStudio()
  usePageChrome(w('runs'), undefined, data?.manifest.project.name)
  return (
    <div className={layout.page}>
      {actions.mode === 'demo' && <DemoBanner />}
      <PageTitle title={w('runs')} lead={w('runsLead')} />
      {actions.mode === 'snapshot' ? <SnapshotPanel /> : <RunsBody />}
    </div>
  )
}
