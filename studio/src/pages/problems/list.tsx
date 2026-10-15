// The Problems list's pieces: who acts and the chosen filters as chips, what the assistant will fix, and the rows
// drawn so far under their group headings with "show more".
import { memo, useMemo } from 'react'
import { Button } from '../../components/Button'
import { ChipButton } from '../../components/Chip'
import { Segmented } from '../../components/Controls'
import { FindingRow } from '../../components/Finding'
import type { Card } from '../../data/types'
import { usePrefs } from '../../i18n/prefs'
import { SelectableRow } from '../../command/Selectable'
import { useCommandMaybe } from '../../command/command'
import { useValueLabel } from './labels'
import { assistantFixes, FACETS, readFilters, type Facet, type GroupBy, type Item, type ProblemsSearch, type Who } from './model'
import { MORE } from './useProblemList'
import { useProblemWords } from './words'
import css from './problems.module.css'

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

/** What your assistant will fix: the cards it decided to fix itself among those the filters show, offered as one
 * selection and one button that opens the Fix preview over them (where the person may also let the batch be accepted
 * when its checks pass). */
export function AssistantFixes({ cards }: { cards: Card[] }) {
  const w = useProblemWords()
  const command = useCommandMaybe()
  const ids = useMemo(() => assistantFixes(cards), [cards])
  if (!ids.length || !command) return null
  return (
    <div className={css.assistantFixes} role="region" aria-label={w('assistantFixesRegion')} data-assistant-fixes={ids.length}>
      <span>{w('assistantFixes', { n: ids.length })}</span>
      <div className={css.assistantFixesActions}>
        <Button variant="primary" icon="fix" onPress={() => command.open({ verb: 'fix', selection: { kind: 'cards', cards: ids } })} data-direct="fix-assistant">
          {w('fixWithAssistant')}
        </Button>
        <Button variant="secondary" onPress={() => command.pick(ids, null)}>{w('selectThem')}</Button>
      </div>
    </div>
  )
}

/** Who acts, the filter button and the chosen filters as removable chips; drawn again only when one of them changes. */
export const Controls = memo(function Controls({ who, group, chosen, active, onSet, onFacet, onFilters }:
  { who: Who; group: GroupBy | null; chosen: Record<Facet, string[]>; active: number; onSet: (patch: Partial<ProblemsSearch>) => void; onFacet: (facet: Facet, values: string[]) => void; onFilters: () => void }) {
  const { t } = usePrefs()
  const w = useProblemWords()
  const label = useValueLabel()
  return (
    <>
      <Segmented<Who> label={t('problems')} value={who} onChange={(next) => onSet({ who: next === 'all' ? undefined : next })}
        options={[{ id: 'all', label: t('allProblems') }, { id: 'you', label: t('needsYou') }, { id: 'eaos', label: t('eaosFixes') }]} />
      <div className={css.filterBar}>
        <Button variant="secondary" icon="layers" onPress={onFilters} data-open="filters">
          {active ? w('filtersN', { n: active }) : w('filters')}
        </Button>
        {group && (
          <ChipButton tone="accent" onPress={() => onSet({ group: undefined })} aria-label={w('removeFilter', { name: `${w('groupBy')}: ${w(`group_${group}`)}` })}>
            {w('groupBy')}: {w(`group_${group}`)}<span aria-hidden="true" className={css.chipX}>×</span>
          </ChipButton>
        )}
        {FACETS.flatMap((facet) => chosen[facet].map((value) => (
          <ChipButton key={`${facet}:${value}`} tone="accent" onPress={() => onFacet(facet, chosen[facet].filter((v) => v !== value))}
            aria-label={w('removeFilter', { name: `${w(`facet_${facet}`)}: ${value || '—'}` })}>
            {label(facet, value)}<span aria-hidden="true" className={css.chipX}>×</span>
          </ChipButton>
        )))}
      </div>
    </>
  )
})

type Segments = { head?: Item & { kind: 'group' }; items: (Item & { kind: 'row' })[] }[]

/** The first `limit` rows, as segments under their group headings, and how many rows were drawn. */
export function segmentsOf(items: Item[], limit: number): { segments: Segments; drawn: number } {
  const segments: Segments = []
  let drawn = 0
  for (const item of items) {
    if (item.kind === 'group') { segments.push({ head: item, items: [] }); continue }
    if (drawn >= limit) break
    if (!segments.length) segments.push({ items: [] })
    segments[segments.length - 1].items.push(item)
    drawn += 1
  }
  return { segments, drawn }
}

/** The drawn rows under their headings, and "show more" while rows are left. */
export function ProblemList({ name, segments, search, ids, left, onMore }:
  { name: string; segments: Segments; search: ProblemsSearch; ids: string[]; left: number; onMore: () => void }) {
  const w = useProblemWords()
  return (
    <div className={css.list} aria-label={name} role="region">
      {segments.map((segment, i) => <Segment key={segment.head ? `g:${segment.head.key}` : `r:${i}`} head={segment.head} items={segment.items} search={search} order={ids} />)}
      {left > 0 && (
        <div className={css.more}>
          <Button variant="secondary" onPress={onMore}>{w('showMore', { n: Math.min(MORE, left) })}</Button>
          <span className={css.muted}>{w('remaining', { n: left })}</span>
        </div>
      )}
    </div>
  )
}
