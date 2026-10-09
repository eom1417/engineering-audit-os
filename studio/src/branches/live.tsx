// The live answer to "is the check current?" and "which branch is this?", shared by the header, the scan sheet, the
// branch switcher and the Branches page (NS46.T18, NS46.T19). In the live Studio it asks the server again when the tab
// comes back into focus, on a modest interval, after any run finishes and when the report reloads; in a snapshot it
// reads what the report recorded at export time and says so.
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { useActions } from '../data/actions/store'
import { TERMINAL, type BranchApi, type BranchContext, type LiveFreshness } from '../data/actions/types'
import { useStudio } from '../data/context'
import type { Freshness } from '../data/types'

/** How often the live Studio asks again while the tab is visible */
export const FRESH_INTERVAL_MS = 60_000

export interface BranchLive {
  /** The live branch API, or null in a snapshot, a demo or a read-only server */
  api: BranchApi | null
  freshness: LiveFreshness | null
  context: BranchContext | null
  /** The last refresh failed (offline server): what is shown is the last known answer */
  offline: boolean
  checking: boolean
  refresh(): Promise<void>
}

const BranchLiveContext = createContext<BranchLive | null>(null)

export function BranchLiveProvider({ children }: { children: ReactNode }) {
  const { client, runs } = useActions()
  const data = useStudio()
  const api = client?.mode === 'live' && client.branches ? client.branches : null
  const [freshness, setFreshness] = useState<LiveFreshness | null>(null)
  const [context, setContext] = useState<BranchContext | null>(null)
  const [offline, setOffline] = useState(false)
  const [checking, setChecking] = useState(false)
  const ticket = useRef(0)

  const refresh = useCallback(async () => {
    if (!api) return
    const mine = ++ticket.current
    setChecking(true)
    try {
      const [fresh, ctx] = await Promise.all([api.freshness(), api.context()])
      if (mine !== ticket.current) return
      setFreshness(fresh)
      setContext(ctx)
      setOffline(false)
    } catch {
      if (mine === ticket.current) setOffline(true)
    } finally {
      if (mine === ticket.current) setChecking(false)
    }
  }, [api])

  // focus, visibility and a modest interval
  useEffect(() => {
    if (!api) { setFreshness(null); setContext(null); return }
    void refresh()
    const back = () => { if (document.visibilityState === 'visible') void refresh() }
    const timer = setInterval(back, FRESH_INTERVAL_MS)
    window.addEventListener('focus', back)
    document.addEventListener('visibilitychange', back)
    return () => { clearInterval(timer); window.removeEventListener('focus', back); document.removeEventListener('visibilitychange', back) }
  }, [api, refresh])

  // any run that finishes, and a report that reloads
  const finished = runs.filter((run) => TERMINAL.includes(run.state)).map((run) => run.id).sort().join(',')
  const built = data?.manifest.built.built ?? ''
  const first = useRef(true)
  useEffect(() => {
    if (first.current) { first.current = false; return }
    void refresh()
  }, [finished, built, refresh])

  const value = useMemo(() => ({ api, freshness, context, offline, checking, refresh }), [api, freshness, context, offline, checking, refresh])
  return <BranchLiveContext.Provider value={value}>{children}</BranchLiveContext.Provider>
}

export function useBranchLive(): BranchLive {
  const value = useContext(BranchLiveContext)
  if (!value) throw new Error('useBranchLive outside BranchLiveProvider')
  return value
}

export interface FreshView {
  state: Freshness | 'legacy'
  /** Commits behind, when the state is behind */
  count: number | null
  live: boolean
}

/** The one freshness every place shows: the server's live answer when there is one, else the report's own. */
export function useFreshView(): FreshView | null {
  const { api, freshness } = useBranchLive()
  const data = useStudio()
  if (!data) return null
  if (api && freshness) {
    const legacy = freshness.state === 'unknown' && freshness.reason === 'legacy_report'
    const state: FreshView['state'] = legacy ? 'legacy' : freshness.state === 'fresh' && freshness.eaos_updated ? 'eaos_updated' : freshness.state
    return { state, count: freshness.behind?.commits ?? null, live: true }
  }
  const head = data.head
  const scanned = head?.scanned ?? data.manifest.scanned
  const recorded = scanned.recorded === true
  let state: FreshView['state'] = head?.freshness ?? 'unknown'
  // legacy: the scan wrote down no commit (the exporter says so), or a report from before freshness_detail existed
  if (head?.freshness_detail?.reason === 'legacy_report' || (!head?.freshness_detail && !recorded && scanned.at && state === 'unknown')) state = 'legacy'
  return { state, count: head?.freshness_detail?.behind?.commits ?? null, live: false }
}
