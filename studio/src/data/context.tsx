// The loaded report, shared by every page; and the few numbers several places show, computed once here.
// The report comes through one DataSource (source.ts): a snapshot, or the live server, whose events reload the
// sections that changed and are announced to screen readers in the person's language.
import { createContext, startTransition, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { usePrefs } from '../i18n/prefs'
import { whenIdle } from '../shell/later'
import { readSections, withSections, type Loaded } from './load'
import { loadReportLocale, localizeReport, type ReportLocale } from './localization'
import type { LiveEvent, LiveStatus } from './live'
import { emitScan, type ProgressRow } from './scan'
import { pickSource, type DataSource, type Mode } from './source'
import type { Card, SectionName, StudioData } from './types'

const ReportLocaleContext = createContext<ReportLocale | undefined>(undefined)
export function useReportLocale(): ReportLocale | undefined { return useContext(ReportLocaleContext) }

const DataContext = createContext<Loaded>({ kind: 'loading' })
/** Asks for sections still pending (data/stages.ts): each is read once and the report updates when it arrives. */
const SectionsContext = createContext<(names: readonly SectionName[]) => void>(() => undefined)

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
  useEffect(() => { current.current = state.kind === 'ready' ? state.data : null }, [state])
  const asked = useRef(new Set<SectionName>())
  const request = useCallback((names: readonly SectionName[]) => {
    const data = current.current
    const fresh = names.filter((name) => data?.pending?.includes(name) && !asked.current.has(name))
    if (!data || !fresh.length) return
    for (const name of fresh) asked.current.add(name)
    // Sections arrive into the report as it is then (a live reload may have replaced it meanwhile)
    void readSections(fresh).then(() => startTransition(() => setState((was) => was.kind === 'ready' ? { kind: 'ready', data: withSections(was.data, fresh, window.EAOS_STUDIO ?? {}) } : was)))
  }, [])
  const displayed = useMemo<Loaded>(() => lang === 'en' && hasEnglish && !locale ? { kind: 'loading' } : localizeReport(state, lang, locale), [state, lang, locale, hasEnglish])

  useEffect(() => {
    if (preset) return
    let on = true
    let queue = Promise.resolve()
    const apply = (next: Loaded) => {
      if (!on) return
      current.current = next.kind === 'ready' ? next.data : null
      // A report is a large tree to draw: as a transition React draws it in slices and the page keeps answering
      startTransition(() => setState(next))
    }
    // Events are applied one after another, each on the report the one before it left. Progress (`progress`, many a
    // minute while work runs) changes no section: the check's goes to the live map (data/scan.ts), and the report
    // reloads when the check publishes its new data, as before.
    const reload = (event: LiveEvent | null) => {
      if (event?.kind === 'progress') {
        if (event.data.flow === 'check') emitScan(event.data as unknown as ProgressRow)
        return
      }
      if (!event) emitScan(null)
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
      <SectionsContext.Provider value={request}>
      <LiveContext.Provider value={live}>
        {children}
        <div className="sr" role="status" aria-live="polite">{live.last ? live.last.text[lang] : ''}</div>
      </LiveContext.Provider>
      </SectionsContext.Provider>
    </DataContext.Provider>
    </ReportLocaleContext.Provider>
  )
}

export function useLoaded(): Loaded {
  return useContext(DataContext)
}

/** The sections of `needs` (every section when 'all') still being read, after asking for them: [] once they are all
 * there. A page shows its loading state until then, so it never draws a part of the report as empty. `when: 'idle'`
 * asks once the page is drawn and the browser is idle, so what is drawn first does not share the network with them. */
export function useSections(needs: readonly SectionName[] | 'all', when: 'now' | 'idle' = 'now'): SectionName[] {
  const loaded = useContext(DataContext)
  const request = useContext(SectionsContext)
  const pending = loaded.kind === 'ready' ? loaded.data.pending ?? [] : []
  const waiting = needs === 'all' ? pending : pending.filter((name) => needs.includes(name))
  const key = waiting.join(',')
  useEffect(() => {
    if (!key) return
    const ask = () => request(key.split(',') as SectionName[])
    if (when === 'now') return ask()
    return whenIdle(ask)
  }, [key, request, when])
  return waiting
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
  const bySeverity = { critical: 0, high: 0, medium: 0, low: 0, info: 0 }
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
