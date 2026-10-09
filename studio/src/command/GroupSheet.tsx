// Select a whole group in two taps: the kind (area, severity, component, gap, operation, plan step), then the group.
// Each row says how many cards it holds; picking one replaces the selection and the action bar names it.
import { useMemo, useState } from 'react'
import { OperationChip, SeverityGlyph } from '../components/Chip'
import { RowButton, StateMessage } from '../components/Panel'
import { Sheet, SheetLead } from '../components/Sheet'
import { Button } from '../components/Button'
import { useStudio } from '../data/context'
import type { Relation, Severity } from '../data/types'
import { usePrefs } from '../i18n/prefs'
import { Id, N, Txt } from '../i18n/text'
import { useCommand } from './command'
import { groupsOf, type Group } from './groups'
import type { GroupKind } from './selectionModel'
import { useCmdWords, type CmdWord } from './words'
import css from './command.module.css'

const KINDS: { by: GroupKind; word: CmdWord }[] = [
  { by: 'area', word: 'byArea' }, { by: 'severity', word: 'bySeverity' }, { by: 'component', word: 'byComponent' },
  { by: 'gap', word: 'byGap' }, { by: 'operation', word: 'byOperation' }, { by: 'step', word: 'byStep' },
]

function GroupTitle({ group }: { group: Group }) {
  if (group.by === 'severity') return <SeverityGlyph severity={group.value as Severity} />
  if (group.by === 'operation') return <OperationChip relation={group.value as Relation} />
  if (group.by === 'component' || group.by === 'gap') return <Id value={group.label} keep={3} />
  if (group.by === 'step') return <span className={css.stepLabel}><Id value={group.value} /><Txt>{group.label === group.value ? '' : group.label}</Txt></span>
  return <Txt>{group.label}</Txt>
}

export function GroupSheet() {
  const command = useCommand()
  const data = useStudio()
  const w = useCmdWords()
  const { t } = usePrefs()
  const [kind, setKind] = useState<GroupKind | null>(null)
  const groups = useMemo(() => (data ? groupsOf(data) : null), [data])
  const close = (open: boolean) => { if (!open) { command.openGroups(false); setKind(null) } }
  const chosen = kind && groups ? groups[kind] : []
  const title = kind ? w(KINDS.find((k) => k.by === kind)!.word) : w('selectGroup')
  return (
    <Sheet isOpen={command.groupsOpen} onOpenChange={close} title={title}>
      {!kind && <SheetLead>{w('selectGroupLead')}</SheetLead>}
      {!kind && groups && (
        <ul className={css.groupList}>
          {KINDS.map((k) => (
            <li key={k.by}>
              <RowButton icon="layers" title={w(k.word)} end={<N value={groups[k.by].length} />} onPress={() => setKind(k.by)} hook={`group-kind:${k.by}`} />
            </li>
          ))}
        </ul>
      )}
      {kind && (
        <>
          <div><Button variant="ghost" icon="back" onPress={() => setKind(null)}>{w('selectGroup')}</Button></div>
          {chosen.length === 0 ? <StateMessage title={w('groupNone')} /> : (
            <ul className={css.groupList} aria-label={title}>
              {chosen.slice(0, 60).map((group) => (
                <li key={`${group.by}:${group.value}`}>
                  <RowButton hook={`group:${group.by}:${group.value}`} title={<GroupTitle group={group} />} end={<span className={css.groupCount}>{w('cardsCount', { n: group.ids.length })}</span>}
                    onPress={() => { command.pick(group.ids, { by: group.by, value: group.value, label: group.by === 'severity' ? t(`sev${group.value[0].toUpperCase()}${group.value.slice(1)}` as 'sevHigh') : group.label }); close(false) }} />
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </Sheet>
  )
}
