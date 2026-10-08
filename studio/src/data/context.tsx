// The loaded report, shared by every page; and the few numbers several places show, computed once here.
import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { load, type Loaded } from './load'
import type { Card, StudioData } from './types'

const DataContext = createContext<Loaded>({ kind: 'loading' })

export function DataProvider({ children, preset }: { children: ReactNode; preset?: Loaded }) {
  const [state, setState] = useState<Loaded>(preset ?? { kind: 'loading' })
  useEffect(() => {
    if (preset) return
    let live = true
    load().then((next) => { if (live) setState(next) }, () => { if (live) setState({ kind: 'empty' }) })
    return () => { live = false }
  }, [preset])
  return <DataContext.Provider value={state}>{children}</DataContext.Provider>
}

export function useLoaded(): Loaded {
  return useContext(DataContext)
}

/** The report when it is loaded, else null (pages render their loading, empty or error state). */
export function useStudio(): StudioData | null {
  const state = useContext(DataContext)
  return state.kind === 'ready' ? state.data : null
}

export interface Counts {
  cards: number
  fixable: number
  needDecision: number
  bySeverity: Record<Card['severity'], number>
  decisionsWaiting: number
  components: number
  docs: number
}

export function counts(data: StudioData): Counts {
  const cards = data.cards?.cards ?? []
  const bySeverity = { critical: 0, high: 0, medium: 0, low: 0 }
  for (const card of cards) bySeverity[card.severity] += 1
  return {
    cards: cards.length,
    fixable: cards.filter((c) => c.fixable).length,
    needDecision: cards.filter((c) => c.needs_decision).length,
    bySeverity,
    decisionsWaiting: (data.decisions?.decisions ?? []).filter((d) => d.state === 'waiting').length,
    components: data.story?.current.components.length ?? 0,
    docs: data.docs?.docs.length ?? 0,
  }
}
