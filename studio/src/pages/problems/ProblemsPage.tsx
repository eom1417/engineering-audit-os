// Problems: the list (search with Arabic normalisation, who acts, facets with their counts, grouping by area,
// component or plan step; every choice in the address) and a card's detail with its evidence and place in the plan.
// Desktop: split panes, the list stays while the detail scrolls. Phone: the list, and the card pushed as its own view
// with a back button naming the list. The list never reorders under the person's finger: a new check arriving while
// it is open waits behind "Show changes"; "Show more" only adds to the end.
import { useNavigate, useSearch } from '@tanstack/react-router'
import { useEffect, useMemo, useState } from 'react'
import { Button } from '../../components/Button'
import { ChipButton } from '../../components/Chip'
import { SearchField, Segmented } from '../../components/Controls'
import { FindingRow } from '../../components/Finding'
import { Panel, StateMessage } from '../../components/Panel'
import type { StudioData } from '../../data/types'
import { usePrefs } from '../../i18n/prefs'
import { usePageChrome } from '../../shell/chrome'
import { layout, MissingBanner, WithData } from '../../shell/Layout'
import { ListTools, SelectableRow } from '../../command/Selectable'
import { Detail } from './Detail'
import { FilterSheet } from './FilterSheet'
import { useValueLabel } from './labels'
import { activeCount, facetParam, FACETS, filterRows, itemsOf, prepare, readFilters, type Facet, type GroupBy, type Item, type ProblemsSearch, type Who } from './model'
import { useProblemWords } from './words'
import css from './problems.module.css'

const FIRST = 30      // rows drawn at first; "show more" adds MORE at a time
const MORE = 200

/** The rows of one group (or of the whole list) as a list; a group's heading names its value and count. */
function Segment({ head, items, search, order }: { head?: Item & { kind: 'group' }; items: (Item & { kind: 'row' })[]; search: ProblemsSearch; order: string[] }) {
  const { num } = usePrefs()
  const label = useValueLabel()
  const filters = readFilters(search)
  const list = (
    <ul className={css.rows}>
      {items.map(({ row }) => (
        <li key={row.card.id}>
          <SelectableRow id={row.card.id} order={order}>
            <FindingRow card={row.card} to="/problems" search={{ ...search, card: row.card.id }} current={row.card.id === search.card} />
          </SelectableRow>
        </li>
      ))}
    </ul>
  )
  if (!head) return list
  return (
    <section className={css.group} aria-label={`${head.key || '—'} (${head.count})`}>
      <h2 className={css.groupHead}>
        <span className={css.groupName}>{label(filters.group as Facet, head.key)}</span>
        <span className={['num', css.groupCount].join(' ')}>{num(head.count)}</span>
      </h2>
      {list}
    </section>
  )
}

function ProblemsBody({ data }: { data: StudioData }) {
  const { t, lang, num } = usePrefs()
  const w = useProblemWords()
  const label = useValueLabel()
  const search = useSearch({ strict: false }) as ProblemsSearch
  const navigate = useNavigate()
  // The cards the list shows stay those it opened with until the person asks for a newer check's
  const [pinned, setPinned] = useState(() => data.cards)
  const shownData = useMemo(() => (pinned === data.cards ? data : { ...data, cards: pinned }), [data, pinned])
  const changed = pinned !== data.cards
  const list = useMemo(() => prepare(shownData, lang), [shownData, lang])
  const filters = readFilters(search)
  const key = JSON.stringify([filters.q, filters.who, filters.chosen, filters.group])
  const result = useMemo(() => filterRows(list, filters), [list, key])   // eslint-disable-line react-hooks/exhaustive-deps
  const items = useMemo(() => itemsOf(result.rows, filters.group, list.order), [result, filters.group, list])
  const ids = useMemo(() => result.rows.map((row) => row.card.id), [result])
  const [limit, setLimit] = useState(FIRST)
  useEffect(() => setLimit(FIRST), [key])
  const [sheet, setSheet] = useState(false)

  const all = data.cards?.cards ?? []
  const selected = all.find((c) => c.id === search.card) ?? pinned?.cards.find((c) => c.id === search.card)
  const listName = t('problems')
  usePageChrome(selected ? selected.id : listName, selected ? { to: '/problems', search: { ...search, card: undefined }, label: listName } : undefined, data.manifest.project.name)
  const set = (patch: Partial<ProblemsSearch>) => navigate({ to: '/problems', search: { ...search, ...patch }, replace: true })
  const setFacet = (facet: Facet, values: string[]) => set({ [facet]: facetParam(values) })
  const clear = () => set(Object.fromEntries(FACETS.map((f) => [f, undefined])))
  const total = list.rows.length
  const active = activeCount(filters) - (filters.who !== 'all' ? 1 : 0)

  // Draw the first `limit` items, as segments under their group headings
  const segments: { head?: Item & { kind: 'group' }; items: (Item & { kind: 'row' })[] }[] = []
  let drawn = 0
  for (const item of items) {
    if (item.kind === 'group') { segments.push({ head: item, items: [] }); continue }
    if (drawn >= limit) break
    if (!segments.length) segments.push({ items: [] })
    segments[segments.length - 1].items.push(item)
    drawn += 1
  }
  const left = result.rows.length - drawn

  return (
    <div className={layout.split}>
      <div className={[layout.listPane, selected && layout.phoneHidden].filter(Boolean).join(' ')}>
        <div className={layout.listHead}>
          <MissingBanner data={data} />
          <h1 className={css.listTitle}>
            {listName}{' '}
            <span className={css.count} aria-live="polite">
              {result.rows.length === total ? num(total) : w('shownOf', { n: result.rows.length, total })}
            </span>
          </h1>
          {changed && (
            <div className={css.newScan} role="status">
              <span>{w('newScan')}</span>
              <Button variant="secondary" icon="retry" onPress={() => setPinned(data.cards)}>{w('showChanges')}</Button>
            </div>
          )}
          <SearchField label={t('search')} placeholder={t('search')} value={search.q ?? ''} onChange={(q) => set({ q: q || undefined })} />
          <Segmented<Who> label={t('problems')} value={filters.who} onChange={(next) => set({ who: next === 'all' ? undefined : next })}
            options={[{ id: 'all', label: t('allProblems') }, { id: 'you', label: t('needsYou') }, { id: 'eaos', label: t('eaosFixes') }]} />
          <div className={css.filterBar}>
            <Button variant="secondary" icon="layers" onPress={() => setSheet(true)} data-open="filters">
              {active ? w('filtersN', { n: active }) : w('filters')}
            </Button>
            {filters.group && (
              <ChipButton tone="accent" onPress={() => set({ group: undefined })} aria-label={w('removeFilter', { name: `${w('groupBy')}: ${w(`group_${filters.group}`)}` })}>
                {w('groupBy')}: {w(`group_${filters.group}`)}<span aria-hidden="true" className={css.chipX}>×</span>
              </ChipButton>
            )}
            {FACETS.flatMap((facet) => filters.chosen[facet].map((value) => (
              <ChipButton key={`${facet}:${value}`} tone="accent" onPress={() => setFacet(facet, filters.chosen[facet].filter((v) => v !== value))}
                aria-label={w('removeFilter', { name: `${w(`facet_${facet}`)}: ${value || '—'}` })}>
                {label(facet, value)}<span aria-hidden="true" className={css.chipX}>×</span>
              </ChipButton>
            )))}
          </div>
          <ListTools shown={ids} />
        </div>
        {result.rows.length === 0 ? <div className={css.empty}><StateMessage title={t('noResults')} /></div> : (
          <div className={css.list} aria-label={listName} role="region">
            {segments.map((segment, i) => <Segment key={segment.head ? `g:${segment.head.key}` : `r:${i}`} head={segment.head} items={segment.items} search={search} order={ids} />)}
            {left > 0 && (
              <div className={css.more}>
                <Button variant="secondary" onPress={() => setLimit(limit + MORE)}>{w('showMore', { n: Math.min(MORE, left) })}</Button>
                <span className={css.muted}>{w('remaining', { n: left })}</span>
              </div>
            )}
          </div>
        )}
        <FilterSheet open={sheet} onOpenChange={setSheet} facets={result.facets} chosen={filters.chosen} group={filters.group}
          onFacet={setFacet} onGroup={(group: GroupBy | null) => set({ group: group ?? undefined })} onClear={clear} />
      </div>
      <div className={[layout.detailPane, !selected && layout.phoneHidden].filter(Boolean).join(' ')}>
        <div className={layout.page}>
          {selected ? <Detail card={selected} data={data} />
            : search.card ? <Panel><StateMessage kind="error" title={t('notFoundCard')} /></Panel>
              : <Panel><StateMessage icon="problems" title={t('chooseProblem')} /></Panel>}
        </div>
      </div>
    </div>
  )
}

export function ProblemsPage() {
  return <WithData>{(data) => <ProblemsBody data={data} />}</WithData>
}
