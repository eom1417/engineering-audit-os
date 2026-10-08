// The filter and grouping sheet: each facet's values as toggles with the number each would show, and the grouping.
// A bottom sheet on the phone, a centred dialog on desktop (components/Sheet). Values keep a fixed order for the
// report, so nothing moves under the person's finger while they choose.
import { useState } from 'react'
import { ToggleButton } from 'react-aria-components'
import { Button } from '../../components/Button'
import { Sheet, SheetLead, SheetSub } from '../../components/Sheet'
import { usePrefs } from '../../i18n/prefs'
import { FACETS, GROUPS, type Facet, type FacetCount, type GroupBy } from './model'
import { useValueLabel } from './labels'
import { useProblemWords } from './words'
import css from './problems.module.css'

const FIRST = 12   // a facet with many values (components) shows this many, then "show all"

export function Toggle({ selected, onChange, children, label, zero }:
  { selected: boolean; onChange: (on: boolean) => void; children: React.ReactNode; label?: string; zero?: boolean }) {
  return <ToggleButton isSelected={selected} onChange={onChange} className={[css.toggle, zero && css.zero].filter(Boolean).join(' ')} aria-label={label}>{children}</ToggleButton>
}

function FacetBlock({ facet, values, chosen, onChange }:
  { facet: Facet; values: FacetCount[]; chosen: string[]; onChange: (values: string[]) => void }) {
  const w = useProblemWords()
  const { num, t } = usePrefs()
  const label = useValueLabel()
  const [all, setAll] = useState(false)
  if (!values.length) return null
  const shown = all ? values : values.slice(0, FIRST).concat(values.slice(FIRST).filter((v) => chosen.includes(v.value)))
  return (
    <section className={css.facet} aria-labelledby={`facet-${facet}`}>
      <SheetSub><span id={`facet-${facet}`}>{w(`facet_${facet}`)}</span></SheetSub>
      <div className={css.toggles} role="group" aria-labelledby={`facet-${facet}`}>
        {shown.map(({ value, count }) => {
          const on = chosen.includes(value)
          return (
            <Toggle key={value} selected={on} zero={!count} onChange={(next) => onChange(next ? [...chosen, value] : chosen.filter((v) => v !== value))}>
              <span className={css.toggleText}>{label(facet, value)}</span>
              <span className={['num', css.toggleCount].join(' ')}>{num(count)}</span>
            </Toggle>
          )
        })}
      </div>
      {values.length > shown.length || all ? (
        <div><Button variant="ghost" onPress={() => setAll(!all)} aria-expanded={all}>{all ? t('showLess') : w('showFacetAll', { n: values.length })}</Button></div>
      ) : null}
    </section>
  )
}

export function FilterSheet({ open, onOpenChange, facets, chosen, group, onFacet, onGroup, onClear }:
  { open: boolean; onOpenChange: (open: boolean) => void; facets: Record<Facet, FacetCount[]>; chosen: Record<Facet, string[]>;
    group: GroupBy | null; onFacet: (facet: Facet, values: string[]) => void; onGroup: (group: GroupBy | null) => void; onClear: () => void }) {
  const w = useProblemWords()
  const any = FACETS.some((facet) => chosen[facet].length)
  return (
    <Sheet isOpen={open} onOpenChange={onOpenChange} title={w('filtersTitle')}>
      <section className={css.facet} aria-labelledby="facet-group">
        <SheetSub><span id="facet-group">{w('groupBy')}</span></SheetSub>
        <div className={css.toggles} role="group" aria-labelledby="facet-group">
          <Toggle selected={group === null} onChange={() => onGroup(null)}>{w('groupNone')}</Toggle>
          {GROUPS.map((g) => <Toggle key={g} selected={group === g} onChange={() => onGroup(g)}>{w(`group_${g}`)}</Toggle>)}
        </div>
      </section>
      {FACETS.map((facet) => <FacetBlock key={facet} facet={facet} values={facets[facet]} chosen={chosen[facet]} onChange={(values) => onFacet(facet, values)} />)}
      <SheetLead>{w('countsNote')}</SheetLead>
      {any && <div><Button variant="secondary" icon="x" onPress={onClear}>{w('clearAll')}</Button></div>}
    </Sheet>
  )
}
