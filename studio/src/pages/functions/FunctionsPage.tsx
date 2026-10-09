// System -> Functions (#/system/functions) and one function (#/system/f/<functionId>), C-experience 3.3. Desktop: the
// list pane (search, order, which functions, kind, the file filter) beside the selected function, or beside the
// overview (what EAOS measured per language, the most complex, the most called, those with problems). Phone: the
// list, and the function pushed on top of it with a back button naming the list. Every state is in the URL:
// ?q=&sort=&show=&kind=&module=. A language with no function facts is named in the coverage, never an empty list.
import { useNavigate, useParams, useSearch } from '@tanstack/react-router'
import { useMemo, useState } from 'react'
import { Button } from '../../components/Button'
import { Chip, type Tone } from '../../components/Chip'
import { Segmented, SearchField } from '../../components/Controls'
import { Panel, Section, Skeleton, StateMessage } from '../../components/Panel'
import type { StudioData } from '../../data/types'
import { usePrefs } from '../../i18n/prefs'
import { Id, N, Txt } from '../../i18n/text'
import { usePageChrome } from '../../shell/chrome'
import { layout, MissingBanner, WithData } from '../../shell/Layout'
import { usePhone } from '../SystemMap'
import { SystemViews } from '../system/SystemViews'
import { FunctionDetail } from './FunctionDetail'
import { FnLink, Level, type ListSearch as Search } from './parts'
import { filterFunctions, KINDS, searchText, SHOWS, SORTS, useCoverage, useSection, type CoverageRow, type Filter, type Fn,
  type FnKind, type FunctionsData, type LanguageRow, type Show, type Sort } from './model'
import { useFunctionWords } from './words'
import css from './Functions.module.css'

const PAGE = 40

function useFilter(): [Filter, (patch: Partial<Search>) => void] {
  const search = useSearch({ strict: false }) as Search
  const navigate = useNavigate()
  const filter: Filter = {
    q: search.q, module: search.module,
    sort: (SORTS as readonly string[]).includes(search.sort ?? '') ? search.sort as Sort : 'risk',
    show: (SHOWS as readonly string[]).includes(search.show ?? '') ? search.show as Show : 'all',
    kind: (KINDS as readonly string[]).includes(search.kind ?? '') ? search.kind as FnKind : undefined,
  }
  const set = (patch: Partial<Search>) => navigate({
    to: '.', replace: true,
    search: (prev: Search) => Object.fromEntries(Object.entries({ ...prev, ...patch }).filter(([, v]) => v !== undefined && v !== '' && v !== 'risk' && v !== 'all')) as Search,
  })
  return [filter, set]
}

function Row({ fn, current }: { fn: Fn; current: boolean }) {
  const w = useFunctionWords()
  const file = fn.module.split('/').slice(-2).join('/')
  return (
    <li>
      <FnLink id={fn.id} className={css.row} current={current}>
        <span className={css.rowMain}>
          <span className={css.rowName}><Id value={fn.name} /></span>
          <span className={css.rowSub}>{w(`kind_${fn.kind}`)} · <Id value={file + (fn.line ? `:${fn.line}` : '')} /></span>
        </span>
        <span className={css.rowEnd}>
          <Level fn={fn} />
          {fn.cards?.length ? <span className={css.cardsBadge}>{fn.cards.length === 1 ? w('problemShort') : w('problemsShort', { n: fn.cards.length })}</span> : null}
        </span>
      </FnLink>
    </li>
  )
}

const LANG_TONE: Record<LanguageRow['state'], Tone> = { measured: 'good', empty: 'neutral', partial: 'warning', not_measured: 'neutral', failed: 'critical' }

/** What EAOS measured per language, and the step that brings the rest: the designed "not measured yet" state. */
export function LanguagesPanel({ fx, row }: { fx: FunctionsData; row?: CoverageRow }) {
  const w = useFunctionWords()
  const { lang } = usePrefs()
  const languages = fx.languages ?? []
  if (!languages.length) return null
  return (
    <Section title={w('coverageTitle')}>
      <Panel pad>
        <ul className={css.langs}>
          {languages.map((l) => (
            <li key={l.id} className={css.lang}>
              <Chip tone={LANG_TONE[l.state]}><Id value={l.id} /></Chip>
              <span className={css.langN}>{l.functions.value !== null ? <N value={l.functions.value} /> : '—'}</span>
              <span className={css.langState}>{w(`lang_${l.state}`)}</span>
            </li>
          ))}
        </ul>
        {(fx.missing ?? []).map((gap) => (
          <p key={gap.id} className={css.gap}><Txt>{gap.detail[lang]}</Txt> · {w('byStep')} <Id value={gap.step} /></p>
        ))}
        {row && row.state !== 'measured' && !(fx.missing ?? []).length && <p className={css.gap}><Txt>{row.detail}</Txt></p>}
      </Panel>
    </Section>
  )
}

function Lead({ fx }: { fx: FunctionsData }) {
  const w = useFunctionWords()
  const c = fx.counts ?? {}
  const touching = fx.functions.filter((f) => f.reads?.length || f.writes?.length).length
  if (!fx.functions.length) return <p className={layout.lead}>{w('leadNone')}</p>
  return <p className={layout.lead}>{w('lead', { f: fx.functions.length, m: fx.modules.length, c: c.calls?.value ?? 0, d: touching })}</p>
}

function Controls({ filter, set, shown, total }: { filter: Filter; set: (patch: Partial<Search>) => void; shown: number; total: number }) {
  const w = useFunctionWords()
  return (
    <div className={css.controls}>
      <SearchField label={w('search')} placeholder={w('searchHint')} value={filter.q ?? ''} onChange={(q) => set({ q })} />
      <div className={css.controlRow}>
        <Segmented<Sort> label={w('sortBy')} value={filter.sort ?? 'risk'} onChange={(sort) => set({ sort })}
          options={SORTS.map((id) => ({ id, label: w(`sort_${id}`) }))} />
      </div>
      <div className={css.chips} role="group" aria-label={w('showWhich')}>
        {SHOWS.map((id) => (
          <button key={id} type="button" className={css.chipBtn} aria-pressed={(filter.show ?? 'all') === id} onClick={() => set({ show: id })}>{w(`show_${id}`)}</button>
        ))}
      </div>
      <div className={css.chips} role="group" aria-label={w('kindFilter')}>
        <button type="button" className={css.chipBtn} aria-pressed={!filter.kind} onClick={() => set({ kind: undefined })}>{w('anyKind')}</button>
        {KINDS.map((id) => (
          <button key={id} type="button" className={css.chipBtn} aria-pressed={filter.kind === id} onClick={() => set({ kind: filter.kind === id ? undefined : id })}>{w(`kinds_${id}`)}</button>
        ))}
      </div>
      {filter.module && (
        <div className={css.fileFilter}>
          <span>{w('inFile')} <Id value={filter.module} keep={3} /></span>
          <button type="button" className={css.clearFile} onClick={() => set({ module: undefined })} aria-label={w('clearFile')}>×</button>
        </div>
      )}
      <p className={css.count} aria-live="polite">{w('shown', { n: shown, t: total })}</p>
    </div>
  )
}

function List({ fx, filter, set, selected }: { fx: FunctionsData; filter: Filter; set: (patch: Partial<Search>) => void; selected?: string }) {
  const w = useFunctionWords()
  const texts = useMemo(() => new Map(fx.functions.map((f) => [f.id, searchText(f)])), [fx])
  const kept = useMemo(() => filterFunctions(fx.functions, filter, texts), [fx, texts, filter.q, filter.sort, filter.show, filter.kind, filter.module])
  const [limit, setLimit] = useState(PAGE)
  const key = JSON.stringify(filter)
  const [seen, setSeen] = useState(key)
  if (seen !== key) { setSeen(key); setLimit(PAGE) }
  const shown = kept.slice(0, limit)
  return (
    <>
      <Controls filter={filter} set={set} shown={kept.length} total={fx.functions.length} />
      {kept.length ? (
        <>
          <ul className={css.list} aria-label={w('functions')}>{shown.map((fn) => <Row key={fn.id} fn={fn} current={fn.id === selected} />)}</ul>
          {kept.length > shown.length && (
            <div className={css.more}><Button variant="ghost" onPress={() => setLimit(limit + PAGE)}>{w('showMore', { n: Math.min(PAGE, kept.length - shown.length) })}</Button></div>
          )}
        </>
      ) : (
        <StateMessage title={w('noMatch')} sub={w('noMatchSub')}
          action={<div><Button variant="secondary" onPress={() => set({ q: undefined, show: undefined, kind: undefined, module: undefined })}>{w('clearAll')}</Button></div>} />
      )}
    </>
  )
}

function Top({ title, fns }: { title: string; fns: Fn[] }) {
  if (!fns.length) return null
  return (
    <Section title={title}>
      <Panel><ul className={css.list}>{fns.map((fn) => <Row key={fn.id} fn={fn} current={false} />)}</ul></Panel>
    </Section>
  )
}

function Overview({ fx, row }: { fx: FunctionsData; row?: CoverageRow }) {
  const w = useFunctionWords()
  const byRisk = filterFunctions(fx.functions, { sort: 'risk' }).slice(0, 5)
  const byCallers = filterFunctions(fx.functions, { sort: 'callers' }).filter((f) => f.callers.length).slice(0, 5)
  const withProblems = filterFunctions(fx.functions, { sort: 'risk', show: 'problems' }).slice(0, 5)
  return (
    <>
      <LanguagesPanel fx={fx} row={row} />
      {fx.functions.length > 0 && <p className={css.hint}>{w('overviewSub')}</p>}
      <Top title={w('riskiest')} fns={byRisk} />
      <Top title={w('withProblems')} fns={withProblems} />
      <Top title={w('mostCalled')} fns={byCallers} />
    </>
  )
}

function Heading({ data, fx }: { data: StudioData; fx?: FunctionsData }) {
  const w = useFunctionWords()
  return (
    <>
      <MissingBanner data={data} />
      <SystemViews current="functions" />
      <div className={layout.titleBlock}>
        <h1 className={layout.largeTitle}>{w('functions')}</h1>
        {fx && <Lead fx={fx} />}
      </div>
    </>
  )
}

function Explorer({ data, selected }: { data: StudioData; selected?: string }) {
  const w = useFunctionWords()
  const { t } = usePrefs()
  const phone = usePhone()
  const slot = useSection<FunctionsData>(data, 'functions')
  const row = useCoverage(data, 'functions')
  const [filter, set] = useFilter()
  const search = useSearch({ strict: false }) as Search
  const fx = slot.kind === 'ready' ? slot.value : undefined
  const fn = fx && selected ? fx.functions.find((f) => f.id === selected) : undefined
  const title = fn ? fn.name : w('functions')
  usePageChrome(title, selected ? { to: '/system/functions', search, label: w('backToList') } : undefined, data.manifest.project.name)

  if (slot.kind === 'loading') return <div className={layout.page}><Heading data={data} /><Panel><Skeleton label={t('loading')} /></Panel></div>
  if (!fx) {
    return (
      <div className={layout.page}>
        <Heading data={data} />
        <Panel><StateMessage title={w('lang_not_measured')} sub={<>{row?.detail ? <Txt>{row.detail}</Txt> : null}{row?.step && <> · {w('byStep')} <Id value={row.step} /></>}</>} /></Panel>
      </div>
    )
  }
  const detail = selected ? <FunctionDetail data={data} fx={fx} id={selected} /> : null
  if (phone) {
    if (detail) return <div className={layout.page}>{detail}</div>
    return (
      <div className={layout.page}>
        <Heading data={data} fx={fx} />
        <LanguagesPanel fx={fx} row={row} />
        <List fx={fx} filter={filter} set={set} />
      </div>
    )
  }
  return (
    <div className={layout.split}>
      <aside className={layout.listPane} aria-label={w('functions')}>
        <div className={css.paneHead}><List fx={fx} filter={filter} set={set} selected={selected} /></div>
      </aside>
      <div className={layout.detailPane}>
        <div className={layout.page}>
          {detail ?? <><Heading data={data} fx={fx} /><Overview fx={fx} row={row} /></>}
        </div>
      </div>
    </div>
  )
}

export function FunctionsPage() {
  return <WithData>{(data) => <Explorer data={data} />}</WithData>
}

export function FunctionPage() {
  const { functionId } = useParams({ strict: false }) as { functionId?: string }
  return <WithData>{(data) => <Explorer data={data} selected={functionId} />}</WithData>
}
