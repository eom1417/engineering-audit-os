// The command centre's state, shared by every page: which client runs actions (live, demo or none in a snapshot),
// the runs with the queue's order, and the open questions. Live runs are polled (often while one is active, rarely
// otherwise, and again when the tab comes back); the demo tells when it changes. Changes the person makes are shown
// at once (optimistic) where a refusal can simply be undone: pause, resume, stop, reorder and answers.
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { useLoaded, useStudio } from '../context'
import { demoClient, type DemoCard } from './demo'
import { deriveRun, type RunView } from './derive'
import { liveClient, takeToken } from './live'
import { ACTIVE, type ActionsClient, type Mode, type Question, type Run, type RunEvent, type StreamStatus, type ReportDecision } from './types'

const DEMO_KEY = 'eaos.demo'

export interface Actions {
  mode: Mode
  client: ActionsClient | null
  runs: Run[]
  queue: string[]
  questions: Question[]
  decisions: ReportDecision[]
  loaded: boolean
  /** The run holding the project's slot (running, paused or waiting for an answer), if any */
  active: Run | null
  refresh(): Promise<void>
  rememberDecision(row: ReportDecision): void
  /** Shows a change at once; the next refresh replaces it with the server's truth */
  patch(id: string, change: Partial<Run>): void
  setQueue(order: string[]): void
  dropQuestion(id: string): void
  startDemo(): void
  stopDemo(): void
}

const ActionsContext = createContext<Actions | null>(null)

function demoWanted(): boolean {
  if (/[?&]demo=1(&|$)/.test(location.hash)) {
    try { sessionStorage.setItem(DEMO_KEY, '1') } catch { /* this visit only */ }
    return true
  }
  try { return sessionStorage.getItem(DEMO_KEY) === '1' } catch { return false }
}

export function ActionsProvider({ children, client: given }: { children: ReactNode; client?: ActionsClient }) {
  const data = useStudio()
  const settled = useLoaded().kind !== 'loading'
  const cards = useRef<DemoCard[]>([])
  cards.current = (data?.cards?.cards ?? []) as DemoCard[]
  const [token] = useState(() => (given ? null : takeToken()))
  const [demo, setDemo] = useState(() => !given && !token && demoWanted())
  const demoRef = useRef<ReturnType<typeof demoClient> | null>(null)
  const client = useMemo<ActionsClient | null>(() => {
    if (given) return given
    if (token) return liveClient(token)
    if (!demo) return null
    demoRef.current ??= demoClient(() => cards.current)
    return demoRef.current
  }, [given, token, demo])
  const [runs, setRuns] = useState<Run[]>([])
  const [queue, setQueueState] = useState<string[]>([])
  const [questions, setQuestions] = useState<Question[]>([])
  const [decisions, setDecisions] = useState<ReportDecision[]>([])
  const [loaded, setLoaded] = useState(false)
  const pending = useRef(0)

  const refresh = useCallback(async () => {
    if (!client) return
    const ticket = ++pending.current
    try {
      const [listed, asked, answered] = await Promise.all([client.runs(), client.questions(), client.decisions?.() ?? Promise.resolve([])])
      if (ticket !== pending.current) return // a newer refresh has the newer truth
      setRuns(listed.runs)
      setQueueState(listed.queue)
      setQuestions(asked)
      setDecisions(answered)
      setLoaded(true)
    } catch { setLoaded(true) }
  }, [client])

  // The demo seeds its runs once the report has loaded, so they name the report's own cards (examples without one)
  useEffect(() => {
    if (client?.mode === 'demo' && settled && demoRef.current) { demoRef.current.seed(); void refresh() }
  }, [client, settled, refresh])

  useEffect(() => {
    if (!client) { setRuns([]); setQueueState([]); setQuestions([]); setLoaded(false); return }
    let timer: ReturnType<typeof setTimeout> | undefined
    let unwatch: (() => void) | undefined
    let stopped = false
    const back = () => { if (document.visibilityState === 'visible') void refresh() }
    void (client.available ? client.available() : Promise.resolve(true)).then((available) => {
      if (stopped) return
      if (!available) { setLoaded(true); return }
      void refresh()
      if (client.watch) { unwatch = client.watch(() => { void refresh() }); return }
      const loop = () => {
        const busy = document.visibilityState === 'visible'
        timer = setTimeout(async () => { if (busy) await refresh(); if (!stopped) loop() }, busy ? 3000 : 15000)
      }
      loop()
      document.addEventListener('visibilitychange', back)
    })
    return () => { stopped = true; clearTimeout(timer); unwatch?.(); document.removeEventListener('visibilitychange', back) }
  }, [client, refresh])

  const value = useMemo<Actions>(() => ({
    mode: client?.mode ?? 'snapshot',
    client, runs, queue, questions, decisions, loaded,
    active: runs.find((run) => ACTIVE.includes(run.state)) ?? null,
    refresh,
    rememberDecision: (row) => { pending.current++; setDecisions((all) => all.map((current) => current.scope === row.scope ? row : current)) },
    patch: (id, change) => setRuns((all) => all.map((run) => (run.id === id ? { ...run, ...change } : run))),
    setQueue: (order) => setQueueState(order),
    dropQuestion: (id) => setQuestions((all) => all.filter((q) => q.id !== id)),
    startDemo: () => { try { sessionStorage.setItem(DEMO_KEY, '1') } catch { /* this visit only */ } setDemo(true) },
    stopDemo: () => { try { sessionStorage.removeItem(DEMO_KEY) } catch { /* nothing kept */ } demoRef.current = null; setDemo(false) },
  }), [client, runs, queue, questions, decisions, loaded, refresh])

  return <ActionsContext.Provider value={value}>{children}</ActionsContext.Provider>
}

export function useActions(): Actions {
  const value = useContext(ActionsContext)
  if (!value) throw new Error('useActions outside ActionsProvider')
  return value
}

export interface FollowedRun {
  run: Run | null
  events: RunEvent[]
  view: RunView
  status: StreamStatus
  missing: boolean
  /** Reloads the run (after a control or a decision) and follows its stream again if it was over */
  reload(next?: Run): void
}

/** One run and its events, followed live; reopening the page replays every event from the first. */
export function useRun(id: string): FollowedRun {
  const { client, runs } = useActions()
  const [run, setRun] = useState<Run | null>(() => runs.find((r) => r.id === id) ?? null)
  const [events, setEvents] = useState<RunEvent[]>([])
  const [status, setStatus] = useState<StreamStatus>('connecting')
  const [missing, setMissing] = useState(false)
  const [round, setRound] = useState(0)
  const last = useRef(0)

  useEffect(() => { last.current = 0; setEvents([]); setMissing(false) }, [id, client])

  useEffect(() => {
    if (!client) return
    let on = true
    client.run(id).then((next) => { if (on) setRun(next) }, () => { if (on) setMissing(true) })
    const stop = client.follow(id, last.current, (event) => {
      if (!on || event.seq <= last.current) return
      last.current = event.seq
      setEvents((all) => [...all, event])
      if (event.kind === 'state' || event.kind === 'question' || event.kind === 'result') {
        client.run(id).then((next) => { if (on) setRun(next) }, () => undefined)
      }
    }, (next) => { if (on) setStatus(next) })
    return () => { on = false; stop() }
  }, [client, id, round])

  // The list's copy is fresher after an optimistic change made elsewhere (the queue, the inbox)
  const listed = runs.find((r) => r.id === id)
  useEffect(() => { if (listed) setRun((was) => (was && was.state === listed.state && was.outcome === listed.outcome ? was : { ...was, ...listed })) }, [listed])

  const view = useMemo(() => deriveRun(events, run), [events, run])
  const reload = useCallback((next?: Run) => {
    if (next) setRun(next)
    if (!next || status === 'closed') setRound((n) => n + 1)
  }, [status])
  return { run, events, view, status, missing, reload }
}
