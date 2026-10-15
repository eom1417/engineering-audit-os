// Problems: the list (search with Arabic normalisation, who acts, facets with their counts, grouping by area,
// component or plan step; every choice in the address) and a card's detail with its evidence and place in the plan.
// Desktop: split panes, the list stays while the detail scrolls. Phone: the list, and the card pushed as its own view
// with a back button naming the list. The list never reorders under the person's finger: a new check arriving while
// it is open waits behind "Show changes"; "Show more" only adds to the end.
import { useCallback, useState } from 'react'
import { Button } from '../../components/Button'
import { SearchField } from '../../components/Controls'
import { Panel, StateMessage } from '../../components/Panel'
import type { Card, StudioData } from '../../data/types'
import { usePrefs } from '../../i18n/prefs'
import { usePageChrome } from '../../shell/chrome'
import { layout, MissingBanner, SectionsLoading, WithData } from '../../shell/Layout'
import { useSections } from '../../data/context'
import { CARD_NEEDS, PROBLEMS_NEEDS } from '../../data/stages'
import { ListTools } from '../../command/Selectable'
import { Detail } from './Detail'
import { FilterSheet } from './FilterSheet'
import { AssistantFixes, Controls, ProblemList, segmentsOf } from './list'
import { activeCount, FACETS, type GroupBy, type ProblemsSearch } from './model'
import { useProblemList, type ProblemList as ListState } from './useProblemList'
import { useProblemWords } from './words'
import css from './problems.module.css'

function ProblemsBody({ data }: { data: StudioData }) {
  const { t } = usePrefs()
  const p = useProblemList(data)
  const { search, filters, result } = p
  const [sheet, setSheet] = useState(false)
  const listName = t('problems')
  const { selected, waiting } = useChosenCard(data, search, p.pinned, listName)
  const openSheet = useCallback(() => setSheet(true), [])
  const clear = () => p.set(Object.fromEntries(FACETS.map((f) => [f, undefined])))
  const { segments, drawn } = segmentsOf(p.items, p.limit)

  return (
    <div className={layout.split}>
      <div className={[layout.listPane, selected && layout.phoneHidden].filter(Boolean).join(' ')}>
        <ListHead data={data} p={p} name={listName} onFilters={openSheet} />
        {result.rows.length === 0 ? <div className={css.empty}><StateMessage title={t('noResults')} /></div>
          : <ProblemList name={listName} segments={segments} search={search} ids={p.ids} left={result.rows.length - drawn} onMore={p.showMore} />}
        <FilterSheet open={sheet} onOpenChange={setSheet} facets={result.facets} chosen={filters.chosen} group={filters.group}
          onFacet={p.onFacet} onGroup={(group: GroupBy | null) => p.set({ group: group ?? undefined })} onClear={clear} />
      </div>
      <div className={[layout.detailPane, !selected && layout.phoneHidden].filter(Boolean).join(' ')}>
        <div className={layout.page}>
          <DetailSide selected={selected} asked={search.card} waiting={waiting} data={data} />
        </div>
      </div>
    </div>
  )
}

/** The card the address names (in this check, or the one the list is pinned to), the sections its detail still
 * waits for, and the page's title and way back that follow it. */
function useChosenCard(data: StudioData, search: ProblemsSearch, pinned: ListState['pinned'], listName: string) {
  const all = data.cards?.cards ?? []
  const selected = all.find((c) => c.id === search.card) ?? pinned?.cards.find((c) => c.id === search.card)
  const waiting = useSections(search.card ? CARD_NEEDS : [])
  usePageChrome(selected ? selected.id : listName, selected ? { to: '/problems', search: { ...search, card: undefined }, label: listName } : undefined, data.manifest.project.name)
  return { selected, waiting }
}

/** The list's head: its title and count, a newer check waiting, what the assistant will fix, the search and filters. */
function ListHead({ data, p, name, onFilters }: { data: StudioData; p: ListState; name: string; onFilters: () => void }) {
  const { t, num } = usePrefs()
  const w = useProblemWords()
  const { filters } = p
  const total = p.list.rows.length
  const shownN = p.result.rows.length
  const active = activeCount(filters) - Number(filters.who !== 'all')
  return (
    <div className={layout.listHead}>
      <MissingBanner data={data} />
      <h1 className={css.listTitle}>
        {name}{' '}
        <span className={css.count} aria-live="polite">{shownN === total ? num(total) : w('shownOf', { n: shownN, total })}</span>
      </h1>
      {p.changed && (
        <div className={css.newScan} role="status">
          <span>{w('newScan')}</span>
          <Button variant="secondary" icon="retry" onPress={p.showChanges}>{w('showChanges')}</Button>
        </div>
      )}
      <AssistantFixes cards={p.shown} />
      <SearchField label={t('search')} placeholder={t('search')} value={p.typed} onChange={p.setTyped} />
      <Controls who={filters.who} group={filters.group} chosen={p.chosen} active={active} onSet={p.onSet} onFacet={p.onFacet} onFilters={onFilters} />
      <ListTools shown={p.ids} />
    </div>
  )
}

/** The detail side: the chosen card (once its sections arrived), a card the address names that is not there, or a hint. */
function DetailSide({ selected, asked, waiting, data }: { selected?: Card; asked?: string; waiting: ReturnType<typeof useSections>; data: StudioData }) {
  const { t } = usePrefs()
  if (selected) return waiting.length ? <SectionsLoading waiting={waiting} /> : <Detail card={selected} data={data} />
  return asked ? <Panel><StateMessage kind="error" title={t('notFoundCard')} /></Panel>
    : <Panel><StateMessage icon="problems" title={t('chooseProblem')} /></Panel>
}

export function ProblemsPage() {
  return <WithData needs={PROBLEMS_NEEDS}>{(data) => <ProblemsBody data={data} />}</WithData>
}
