// The loaded report, shared by every page; and the few numbers several places show, computed once here.
// The report comes through one DataSource (source.ts): a snapshot, or the live server, whose events reload the
// sections that changed and are announced to screen readers in the person's language.
import { createContext, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { usePrefs } from '../i18n/prefs'
import type { Loaded } from './load'
import { loadReportLocale, localizeReport, type ReportLocale } from './localization'
import type { LiveEvent, LiveStatus } from './live'
import { pickSource, type DataSource, type Mode } from './source'
import type { Card, StudioData } from './types'

const ReportLocaleContext = createContext<ReportLocale | undefined>(undefined)
export function useReportLocale(): ReportLocale | undefined { return useContext(ReportLocaleContext) }

const DataContext = createContext<Loaded>({ kind: 'loading' })

export interface Live {
  mode: Mode
  status: LiveStatus | null
  /** The last event the pages now show */
  last: LiveEvent | null
}

const LiveContext = createContext<Live>({ mode: 'snapshot', status: null, last: null })

export function DataProvider({ children, preset, source }: { children: ReactNode; preset?: Loaded; source?: DataSource }) {
  const [state, setState] = useState<Loaded>(preset ?? { kind: 'loading' })
  const [chosen] = useState<DataSource>(() => source ?? pickSource())
  const [live, setLive] = useState<Live>({ mode: preset ? 'snapshot' : chosen.mode, status: null, last: null })
  const current = useRef<StudioData | null>(null)
  const { lang } = usePrefs()
  const [locale, setLocale] = useState<ReportLocale | undefined>(() => window.EAOS_LOCALE)
  const localeFingerprint = state.kind === 'ready' ? state.data.manifest.locales?.en?.sha256 : undefined
  const hasEnglish = !!localeFingerprint
  useEffect(() => {
    if (!hasEnglish) return
    let on = true
    loadReportLocale().then((loaded) => { if (on && loaded) setLocale(loaded) })
    return () => { on = false }
  }, [hasEnglish, localeFingerprint])
  const displayed = useMemo<Loaded>(() => lang === 'en' && hasEnglish && !locale ? { kind: 'loading' } : localizeReport(state, lang, locale), [state, lang, locale, hasEnglish])

  useEffect(() => {
    if (preset) return
    let on = true
    let queue = Promise.resolve()
    const apply = (next: Loaded) => {
      if (!on) return
      current.current = next.kind === 'ready' ? next.data : null
      setState(next)
    }
    // Events are applied one after another, each on the report the one before it left.
    const reload = (event: LiveEvent | null) => {
      queue = queue.then(() => chosen.load(event ? current.current : null)).then((next) => {
        apply(next)
        if (on && event) setLive((was) => ({ ...was, last: event }))
      }, () => undefined)
    }
    queue = chosen.load().then(apply, () => apply({ kind: 'empty' }))
    const stop = chosen.follow?.(reload, (status) => { if (on) setLive((was) => ({ ...was, status })) })
    return () => { on = false; stop?.() }
  }, [preset, chosen])

  useEffect(() => {
    const root = document.documentElement
    root.dataset.studioMode = live.mode
    if (live.status) root.dataset.studioLive = live.status
    if (live.last) root.dataset.studioEvent = live.last.id
  }, [live])

  return (
    <ReportLocaleContext.Provider value={locale}>
    <DataContext.Provider value={displayed}>
      <LiveContext.Provider value={live}>
        {children}
        <div className="sr" role="status" aria-live="polite">{live.last ? live.last.text[lang] : ''}</div>
      </LiveContext.Provider>
    </DataContext.Provider>
    </ReportLocaleContext.Provider>
  )
}

export function useLoaded(): Loaded {
  return useContext(DataContext)
}

/** Whether the Studio is live or a snapshot, and the last change it shows. */
export function useLive(): Live {
  return useContext(LiveContext)
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
