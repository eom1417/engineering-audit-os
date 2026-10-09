// The selection where the pages show cards and steps: a row with its check box, the tools above a list (select what
// is shown, select a group), a plan step's box, and the map inspector's "select its cards".
import { useMemo, type ReactNode } from 'react'
import { Button } from '../components/Button'
import { useStudio } from '../data/context'
import { useCommand, useCommandMaybe } from './command'
import { componentOwner } from './groups'
import { SelectBox } from './SelectBox'
import type { GroupRef } from './selectionModel'
import { useCmdWords } from './words'
import css from './command.module.css'

/** A list row (a card) with its check box; Shift-click selects the range over `order`, the list as shown. */
export function SelectableRow({ id, order, children }: { id: string; order: string[]; children: ReactNode }) {
  const command = useCommand()
  const w = useCmdWords()
  const checked = command.sel.ids.includes(id)
  return (
    <div className={css.selRow} data-selected={checked ? '' : undefined}>
      <SelectBox checked={checked} label={w('selectCard', { id })} onToggle={(shift) => command.toggle(id, shift, order)} />
      {children}
    </div>
  )
}

/** Above a list: tick everything shown, or pick a whole group. */
export function ListTools({ shown }: { shown: string[] }) {
  const command = useCommand()
  const w = useCmdWords()
  const all = shown.length > 0 && shown.every((id) => command.sel.ids.includes(id))
  return (
    <div className={css.listTools}>
      {shown.length > 0 && (
        <Button variant="ghost" icon="check" onPress={() => command.setMany(shown, !all)} aria-pressed={all}>
          {all ? w('clearSelection') : w('selectShown', { n: shown.length })}
        </Button>
      )}
      <Button variant="ghost" icon="layers" onPress={() => command.openGroups(true)} data-hook="select-group">{w('selectGroup')}</Button>
    </div>
  )
}

/** A box that selects a whole group's cards (a plan step): ticked when all are in, mixed when some are. */
export function GroupBox({ ids, group, label }: { ids: string[]; group: GroupRef; label: string }) {
  const command = useCommand()
  const inside = ids.filter((id) => command.sel.ids.includes(id)).length
  const all = ids.length > 0 && inside === ids.length
  if (!ids.length) return <span className={css.boxSpacer} aria-hidden="true" />
  return (
    <SelectBox checked={all} mixed={inside > 0} label={label}
      onToggle={() => (all ? command.setMany(ids, false) : command.sel.ids.length ? command.setMany(ids, true) : command.pick(ids, group))} />
  )
}

/** "Select its cards": the map inspector's way into the command centre for one component (its cards are the ones the
 * map counts for it). */
export function SelectComponentCards({ component }: { component: string }) {
  const command = useCommandMaybe()
  const data = useStudio()
  const w = useCmdWords()
  const ids = useMemo(() => {
    if (!data) return []
    const owner = componentOwner(data)
    return (data.cards?.cards ?? []).filter((c) => c.paths[0] && owner(c.paths[0]) === component).map((c) => c.id)
  }, [data, component])
  const group: GroupRef = { by: 'component', value: component, label: component }
  if (!command || !ids.length) return null
  return <Button variant="secondary" block icon="check" onPress={() => command.pick(ids, group)}>{w('selectItsCards', { n: ids.length })}</Button>
}
