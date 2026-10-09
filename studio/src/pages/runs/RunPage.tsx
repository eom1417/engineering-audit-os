// The live run (#/runs/<id>): what the assistant does, step by step, in plain words; the progress of each batch; the
// question when it needs the person; the before/after screens; and at the end the result with Accept and Undo, each
// behind an explicit confirm. The stream reconnects with Last-Event-ID, so closing the tab loses nothing: reopening
// replays the run from its first event. New events only append below, so nothing on the page jumps.
import { useParams } from '@tanstack/react-router'
import { useEffect, useState } from 'react'
import { Button } from '../../components/Button'
import { Panel, Section, StateMessage } from '../../components/Panel'
import { Sheet, SheetLead } from '../../components/Sheet'
import { useToast } from '../../components/Toast'
import { QuestionCard } from '../../command/Questions'
import { useCmdWords } from '../../command/words'
import { verbOf } from '../../data/actions/contract'
import { duration, labelOf } from '../../data/actions/derive'
import { useActions, useRun } from '../../data/actions/store'
import { ActionError, TERMINAL, type Control, type Run } from '../../data/actions/types'
import { useStudio } from '../../data/context'
import { usePrefs } from '../../i18n/prefs'
import { Id, Txt } from '../../i18n/text'
import { usePageChrome } from '../../shell/chrome'
import { layout } from '../../shell/Layout'
import { Batches, ResultFacts, ScreenPairs, StateChip, Timeline } from './parts'
import { DemoBanner, SnapshotPanel } from './RunsPage'
import css from './runs.module.css'

function useNow(on: boolean): number {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    if (!on) return
    const timer = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(timer)
  }, [on])
  return now
}

function DecideSheet({ run, op, onClose, onDone }: { run: Run; op: 'accept' | 'undo' | null; onClose: () => void; onDone: (next: Run) => void }) {
  const { client } = useActions()
  const w = useCmdWords()
  const toast = useToast()
  const { lang } = usePrefs()
  const [token, setToken] = useState<string | null>(null)
  const [problem, setProblem] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const branch = run.result?.branch ?? ''
  useEffect(() => {
    setToken(null); setProblem(null); setBusy(false)
    if (!op || !client) return
    let on = true
    client.preview(op, { inputs: {} }).then((p) => { if (on) setToken(p.confirm?.token ?? null) }, (e) => { if (on) setProblem(e instanceof ActionError ? e.message : String(e)) })
    return () => { on = false }
  }, [op, client])
  if (!op) return null
  const decide = async () => {
    if (!client || !token) return
    setBusy(true)
    try {
      const next = await client.decide(run.id, op, token)
      toast(w('decided', { what: op === 'accept' ? w('outcomeAccepted') : w('outcomeUndone') }))
      onDone(next)
      onClose()
    } catch (error) {
      setProblem(error instanceof ActionError ? error.message : String(error))
      setBusy(false)
    }
  }
  return (
    <Sheet isOpen onOpenChange={(open) => { if (!open) onClose() }} title={w(op === 'accept' ? 'acceptTitle' : 'undoTitle', { branch })}>
      <SheetLead>{w(op === 'accept' ? 'acceptLead' : 'undoLead')}</SheetLead>
      <p className={css.decideBranch}><Id value={branch} /> · <Txt>{labelOf(run.label, lang)}</Txt></p>
      {problem && <StateMessage kind="error" title={w('decideFailed')} sub={<Txt>{problem}</Txt>} />}
      <div className={css.decideFoot}>
        <Button variant="secondary" onPress={onClose}>{w('cancel')}</Button>
        <Button variant="primary" busy={busy || (!token && !problem)} isDisabled={!token} onPress={decide} data-confirm="decide">
          {w(op === 'accept' ? 'acceptYes' : 'undoYes')}
        </Button>
      </div>
    </Sheet>
  )
}

function Controls({ run, onRun }: { run: Run; onRun: (next: Run) => void }) {
  const actions = useActions()
  const w = useCmdWords()
  const toast = useToast()
  const [busy, setBusy] = useState<Control | null>(null)
  const optimistic: Partial<Record<Control, Run['state']>> = { pause: 'paused', resume: 'running', stop: 'stopped' }
  const press = async (op: Control) => {
    if (!actions.client) return
    setBusy(op)
    const shown = optimistic[op]
    if (shown) { actions.patch(run.id, { state: shown }); onRun({ ...run, state: shown }) }
    try {
      const next = await actions.client.control(run.id, op)
      onRun(next)
    } catch (error) {
      toast(error instanceof ActionError ? error.message : String(error))
      onRun(run)
    } finally {
      setBusy(null)
      void actions.refresh()
    }
  }
  const can = {
    pause: run.state === 'running', resume: run.state === 'paused',
    stop: !TERMINAL.includes(run.state), retry: run.state === 'failed' || run.state === 'stopped',
  }
  if (!Object.values(can).some(Boolean)) return null
  return (
    <div className={css.controls}>
      {can.pause && <Button variant="secondary" icon="pause" data-control="pause" busy={busy === 'pause'} onPress={() => press('pause')}>{w('pause')}</Button>}
      {can.resume && <Button variant="primary" icon="play" data-control="resume" busy={busy === 'resume'} onPress={() => press('resume')}>{w('resume')}</Button>}
      {can.retry && <Button variant="primary" icon="retry" data-control="retry" busy={busy === 'retry'} onPress={() => press('retry')}>{w('retry')}</Button>}
      {can.stop && <Button variant="ghost" icon="stop" data-control="stop" busy={busy === 'stop'} onPress={() => press('stop')}>{w('stop')}</Button>}
    </div>
  )
}

function RunBody({ id }: { id: string }) {
  const actions = useActions()
  const { lang } = usePrefs()
  const w = useCmdWords()
  const followed = useRun(id)
  const { run, view, status } = followed
  const [deciding, setDeciding] = useState<'accept' | 'undo' | null>(null)
  const state = run?.state ?? view.state
  const now = useNow(state === 'running' || state === 'waiting_for_person' || state === 'paused')
  const data = useStudio()
  usePageChrome(run ? labelOf(run.label, lang) : w('run'), { to: '/runs', label: w('runs') }, data?.manifest.project.name)

  if (followed.missing && !run) {
    return <div className={layout.page}><Panel><StateMessage kind="error" title={w('runNotFound')} sub={w('runNotFoundSub')} /></Panel></div>
  }
  if (!run || !state) return <div className={layout.page}><Panel><StateMessage icon="clock" title={w('connecting')} /></Panel></div>
  const elapsed = duration(run.started, run.ended, lang, now)
  const result = view.result ?? run.result ?? null
  const question = state === 'waiting_for_person' ? (view.question ?? run.question ?? null) : null
  const branchWaiting = state === 'done' && result?.branch && !run.outcome
  // Batches belong to Fix runs; a read-only run shows its progress as the timeline alone
  const progress = run.verb === 'fix' || view.batches.length > 0 || state === 'queued'
  const side = progress || view.screens.length > 0

  return (
    <div className={[layout.page, css.runPage].join(' ')}>
      {actions.mode === 'demo' && <DemoBanner />}
      <header className={css.head}>
        <div className={css.headTop} data-run-state={state}>
          <span className={css.kicker}>{run.verb ? verbOf(run.verb).label[lang] : <Id value={run.action} />}</span>
          <StateChip state={state} />
          {run.position && state === 'queued' ? <span className={css.meta}>{w('positionN', { n: run.position })}</span> : null}
        </div>
        <h1 className={css.title}><Txt>{labelOf(run.label, lang)}</Txt></h1>
        <p className={css.meta}>
          {[run.assistant === 'claude' ? 'Claude Code' : run.assistant === 'codex' ? 'Codex' : run.mode === 'handoff' ? null : 'EAOS',
            elapsed ? w(run.ended ? 'took' : 'elapsed', { d: elapsed }) : null, run.attempt > 1 ? w('attempt', { n: run.attempt }) : null].filter(Boolean).join(' · ')}
          {status === 'reconnecting' && <span className={css.reconnect} role="status"> · {w('reconnecting')}</span>}
        </p>
        <Controls run={run} onRun={(next) => followed.reload(next)} />
      </header>

      <div className={css.now} aria-live="polite">
        <span className={css.nowLabel}>{w('latestStep')}</span>
        <span className={css.nowText}>{view.now ? <Txt>{view.now[lang]}</Txt> : state === 'queued' ? w('waitingTurn', { n: run.position ?? 1 }) : '…'}</span>
      </div>

      {question && <QuestionCard question={question} compact />}
      <div className={side ? css.grid : css.single}>
        <div className={css.mainCol}>
          {view.error && TERMINAL.includes(state) && (
            <Panel className={css.error} label={w('errorTitle')}>
              <h2 className={css.panelTitle}>{w('errorTitle')}</h2>
              <p><Txt>{view.error.text[lang]}</Txt></p>
              {view.error.what_now && <p className={css.whatNow}><Txt>{view.error.what_now[lang]}</Txt></p>}
            </Panel>
          )}
          {result && state === 'done' && (
            <Panel className={css.resultPanel} label={w('result')}>
              <h2 className={css.panelTitle}>{w('result')}</h2>
              <ResultFacts result={result} />
              {branchWaiting && (
                <div className={css.decide}>
                  <Button variant="primary" large icon="check" data-decide="accept" onPress={() => setDeciding('accept')}>{w('acceptBranch')}</Button>
                  <Button variant="secondary" large icon="x" data-decide="undo" onPress={() => setDeciding('undo')}>{w('undoBranch')}</Button>
                </div>
              )}
              {run.outcome && <p className={css.outcome}>{w('decided', { what: run.outcome === 'accepted' ? w('outcomeAccepted') : w('outcomeUndone') })}</p>}
            </Panel>
          )}
          <Section title={w('whatHappened')} count={view.items.length}>
            <Panel><Timeline items={view.items} /></Panel>
          </Section>
        </div>
        {side && <aside className={css.sideCol}>
          {progress && <Section title={w('progress')}>
            <Panel pad>
              {view.batches.length ? <Batches batches={view.batches} />
                : <p className={css.placeholder}>{state === 'queued' ? w('waitingTurn', { n: run.position ?? 1 }) : w('noProgressYet')}</p>}
            </Panel>
          </Section>}
          {view.screens.length > 0 && (
            <Section title={w('screens')}><Panel pad><ScreenPairs screens={view.screens} /></Panel></Section>
          )}
        </aside>}
      </div>
      <DecideSheet run={run} op={deciding} onClose={() => setDeciding(null)} onDone={(next) => { actions.patch(run.id, next); followed.reload(next); void actions.refresh() }} />
    </div>
  )
}

export function RunPage() {
  const { runId } = useParams({ strict: false }) as { runId: string }
  const actions = useActions()
  const w = useCmdWords()
  const data = useStudio()
  if (actions.mode === 'snapshot') return <SnapshotRun title={w('run')} project={data?.manifest.project.name} />
  return <RunBody key={runId} id={runId} />
}

function SnapshotRun({ title, project }: { title: string; project?: string }) {
  const w = useCmdWords()
  usePageChrome(title, { to: '/runs', label: w('runs') }, project)
  return <div className={layout.page}><SnapshotPanel /></div>
}
