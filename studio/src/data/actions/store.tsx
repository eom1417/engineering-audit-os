// The command centre's state, shared by every page: which client runs actions (live, or none in a snapshot), the
// runs with the queue's order, and the open questions. Live runs are polled (often while one is active, rarely
// otherwise, and again when the tab comes back). Changes the person makes are shown
// at once (optimistic) where a refusal can simply be undone: pause, resume, stop, reorder and answers.
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { deriveRun, type RunView } from './derive'
import { liveClient, takeToken } from './live'
import { ACTIVE, type ActionsClient, type Mode, type Question, type Run, type RunEvent, type StreamStatus, type ReportDecision } from './types'

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
}

const ActionsContext = createContext<Actions | null>(null)

export function ActionsProvider({ children, client: given }: { children: ReactNode; client?: ActionsClient }) {
  const [token] = useState(() => (given ? null : takeToken()))
  const client = useMemo<ActionsClient | null>(() => given ?? (token ? liveClient(token) : null), [given, token])
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

  useEffect(() => {
    if (!client) { setRuns([]); setQueueState([]); setQuestions([]); setLoaded(false); return }
    let timer: ReturnType<typeof setTimeout> | undefined
    let stopped = false
    const back = () => { if (document.visibilityState === 'visible') void refresh() }
    void (client.available ? client.available() : Promise.resolve(true)).then((available) => {
      if (stopped) return
      if (!available) { setLoaded(true); return }
      void refresh()
      const loop = () => {
        const busy = document.visibilityState === 'visible'
        timer = setTimeout(async () => { if (busy) await refresh(); if (!stopped) loop() }, busy ? 3000 : 15000)
      }
      loop()
      document.addEventListener('visibilitychange', back)
    })
    return () => { stopped = true; clearTimeout(timer); document.removeEventListener('visibilitychange', back) }
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
  }), [client, runs, queue, questions, decisions, loaded, refresh])

  return <ActionsContext.Provider value={value}>{children}</ActionsContext.Provider>
}

export function useActions(): Actions {
  const value = useContext(ActionsContext)
  if (!value) throw new Error('useActions outside ActionsProvider')
  return value
}

/** The command centre where a page may be rendered without it (a test): null instead of an error. */
export function useActionsMaybe(): Actions | null {
  return useContext(ActionsContext)
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

const FLUSH = 120 // ms between two drawings of a run's new events

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
    let pending: RunEvent[] = []
    let timer = 0
    // Events are drawn together, at most every FLUSH ms: one by one, a page opened on a long run replayed its 500 events
    // into 500 drawings, and each refresh showed it mid-way, at another count and step (owner, 2026-10-15).
    const flush = () => {
      const got = pending
      pending = []
      timer = 0
      if (!on || !got.length) return
      setEvents((all) => [...all, ...got])
      if (got.some((e) => e.kind === 'state' || e.kind === 'question' || e.kind === 'result')) {
        client.run(id).then((next) => { if (on) setRun(next) }, () => undefined)
      }
    }
    client.run(id).then((next) => { if (on) setRun(next) }, () => { if (on) setMissing(true) })
    const stop = client.follow(id, last.current, (event) => {
      if (!on || event.seq <= last.current) return
      last.current = event.seq
      pending.push(event)
      if (!timer) timer = window.setTimeout(flush, FLUSH)
    }, (next) => { if (on) setStatus(next) })
    return () => { on = false; window.clearTimeout(timer); stop() }
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
