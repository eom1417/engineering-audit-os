// The running check for every page: the live map reads it, and the frame shows a banner while a check runs. Live only
// (the snapshot has no server to follow); the state is read whole from /api/scan-progress, then follows the feed's
// `progress` events of the check (data/scan.ts). A gap in the numbers, a new run or a reset reads it whole again, and so does a
// slow look while a run is open, which is how a run whose process stopped turns `interrupted` instead of glowing on.
import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from 'react'
import { liveToken } from './live'
import { apply, emptyProgress, onScan, verdict, type ProgressRow, type ScanProgress } from './scan'

export interface Scan {
  /** null in the snapshot, and until the first answer */
  progress: ScanProgress | null
  /** Server clock minus browser clock, in ms */
  skew: number
  /** The last stage that ended ok and when the page heard it: where the light starts travelling from */
  lastEnded: { stage: string; at: number } | null
}

const ScanContext = createContext<Scan>({ progress: null, skew: 0, lastEnded: null })
const LOOK_AGAIN_MS = 15000

export function ScanProvider({ children, preset }: { children: ReactNode; preset?: Scan }) {
  const [scan, setScan] = useState<Scan>(preset ?? { progress: null, skew: 0, lastEnded: null })
  const current = useRef<ScanProgress | null>(null)
  current.current = scan.progress

  useEffect(() => {
    if (preset) return
    const token = liveToken()
    if (!token) return
    let on = true
    let reading: Promise<void> | null = null
    let held: ProgressRow[] = []
    const read = () => {
      if (reading) return reading
      const sent = Date.now()
      reading = fetch('/api/scan-progress', { headers: { 'X-EAOS-Token': token }, cache: 'no-store', credentials: 'same-origin' })
        .then((answer) => (answer.ok ? answer.json() as Promise<ScanProgress> : Promise.reject(new Error(String(answer.status)))))
        .then((body) => {
          if (!on) return
          const back = Date.now()
          const skew = body.now ? Date.parse(body.now) - (sent + back) / 2 : 0
          let progress: ScanProgress = { ...emptyProgress(), ...body }
          // what arrived while it was being read, after the state it read
          for (const row of held) if (verdict(progress, row) === 'apply') progress = apply(progress, row)
          held = []
          current.current = progress
          setScan((was) => ({ ...was, progress, skew: Number.isFinite(skew) ? skew : 0 }))
        })
        .catch(() => undefined)
        .finally(() => { reading = null })
      return reading
    }
    void read()
    const stop = onScan((row) => {
      if (!row) { void read(); return }
      if (reading) { held.push(row); return }
      const state = current.current ?? emptyProgress()
      const what = verdict(state, row)
      if (what === 'reload') { held.push(row); void read(); return }
      if (what === 'ignore') return
      const next = apply(state, row)
      current.current = next
      const endedOk = row.event === 'stage.ended' && row.status === 'ok' && !row.resumed && typeof row.stage === 'string'
      setScan((was) => ({ ...was, progress: next, lastEnded: endedOk ? { stage: row.stage as string, at: Date.now() } : was.lastEnded }))
    })
    const timer = window.setInterval(() => { if (current.current?.state === 'running') void read() }, LOOK_AGAIN_MS)
    return () => { on = false; stop(); window.clearInterval(timer) }
  }, [preset])

  return <ScanContext.Provider value={scan}>{children}</ScanContext.Provider>
}

export function useScan(): Scan {
  return useContext(ScanContext)
}
