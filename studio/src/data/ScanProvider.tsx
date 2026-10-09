// The work EAOS is doing, for every page: the live map reads it, and the frame shows a banner and the tab's title while
// something runs. Live only (the snapshot has no server to follow); the state is read whole from /api/progress, then
// follows the feed's `progress` events flow by flow (data/scan.ts). A gap in the numbers, a new run or a reset reads it
// whole again, and so does a slow look while a run is open, which is how a run whose process stopped turns
// `interrupted` instead of glowing on. When the stream says nothing for 8 s, not even its keep-alive ping (a proxy that
// holds server-sent events back), the page reads /api/progress every 2 s until the stream delivers again.
import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from 'react'
import { liveToken, streamHeardAt } from './live'
import { apply, emptyProgress, onScan, verdict, type AllProgress, type ProgressRow } from './scan'

export type Transport = 'stream' | 'polling'

export interface Scan {
  /** null in the snapshot, and until the first answer */
  all: AllProgress | null
  /** Server clock minus browser clock, in ms */
  skew: number
  /** Which path carries the changes now */
  transport: Transport
}

const ScanContext = createContext<Scan>({ all: null, skew: 0, transport: 'stream' })
const QUIET_MS = 8000
const POLL_MS = 2000
const LOOK_AGAIN_MS = 15000

/** The rows held while the state was being read, applied after it to the flows they belong to. */
function withRows(all: AllProgress, rows: ProgressRow[]): AllProgress {
  const flows = { ...all.flows }
  for (const row of rows) {
    const flow = row.flow ?? 'check'
    const state = flows[flow] ?? emptyProgress()
    if (verdict(state, row) === 'apply') flows[flow] = apply(state, row)
  }
  return { ...all, flows }
}

/** What the page does with a row of any flow (data/scan.ts verdict); before the first read, read. */
function verdictIn(all: AllProgress | null, row: ProgressRow): 'apply' | 'ignore' | 'reload' {
  return all ? verdict(all.flows[row.flow ?? 'check'] ?? emptyProgress(), row) : 'reload'
}

/** How long after the last read the state is read again: every 2 s while the stream is silent, every 15 s while
 * something runs (a run whose process died never writes again), else only on news. */
function lookAgainAfter(transport: Transport, all: AllProgress | null): number {
  if (transport === 'polling') return POLL_MS
  return Object.values(all?.flows ?? {}).some((f) => f.state === 'running') ? LOOK_AGAIN_MS : Infinity
}

export function ScanProvider({ children, preset }: { children: ReactNode; preset?: Scan }) {
  const [scan, setScan] = useState<Scan>(preset ?? { all: null, skew: 0, transport: 'stream' })
  const current = useRef<AllProgress | null>(null)
  current.current = scan.all

  useEffect(() => {
    if (preset) return
    const token = liveToken()
    if (!token) return
    let on = true
    let reading: Promise<void> | null = null
    let held: ProgressRow[] = []
    let readAt = 0
    const read = () => {
      if (reading) return reading
      const sent = readAt = Date.now()
      reading = fetch('/api/progress', { headers: { 'X-EAOS-Token': token }, cache: 'no-store', credentials: 'same-origin' })
        .then((answer) => (answer.ok ? answer.json() as Promise<AllProgress> : Promise.reject(new Error(String(answer.status)))))
        .then((body) => {
          if (!on) return
          const skew = body.now ? Date.parse(body.now) - (sent + Date.now()) / 2 : 0
          const all = withRows({ journey: body.journey ?? [], flows: body.flows ?? {} }, held)
          held = []
          current.current = all
          setScan((was) => ({ ...was, all, skew: Number.isFinite(skew) ? skew : 0 }))
        })
        .catch(() => undefined)
        .finally(() => { reading = null })
      return reading
    }
    void read()
    const stop = onScan((row) => {
      const what = row && !reading ? verdictIn(current.current, row) : 'reload'
      if (what === 'reload') {
        if (row) held.push(row)
        void read()
      } else if (what === 'apply') {
        const all = withRows(current.current as AllProgress, [row as ProgressRow])
        current.current = all
        setScan((was) => ({ ...was, all }))
      }
    })
    const opened = Date.now()
    const timer = window.setInterval(() => {
      const transport = Date.now() - Math.max(streamHeardAt(), opened) > QUIET_MS ? 'polling' : 'stream'
      setScan((was) => (was.transport === transport ? was : { ...was, transport }))
      if (Date.now() - readAt >= lookAgainAfter(transport, current.current)) void read()
    }, 1000)
    return () => { on = false; stop(); window.clearInterval(timer) }
  }, [preset])

  return <ScanContext.Provider value={scan}>{children}</ScanContext.Provider>
}

export function useScan(): Scan {
  return useContext(ScanContext)
}

/** The flow running now, else null. */
export function runningFlow(all: AllProgress | null): string | null {
  return Object.entries(all?.flows ?? {}).find(([, f]) => f.state === 'running')?.[0] ?? null
}
