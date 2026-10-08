// The sticky action bar: it rises when something is selected and says what (the count, or the group's name), with the
// four verbs. On the phone it sits above the tab bar in two rows, the verbs in reach of the thumb.
import { Button } from '../components/Button'
import { IconButton } from '../components/Button'
import { VERBS } from '../data/actions/contract'
import { usePrefs } from '../i18n/prefs'
import { Txt } from '../i18n/text'
import { useCommand } from './command'
import { MAX_CARDS } from './selectionModel'
import { useCmdWords } from './words'
import css from './command.module.css'

export function ActionBar() {
  const command = useCommand()
  const { lang } = usePrefs()
  const w = useCmdWords()
  const { sel } = command
  if (!sel.ids.length) return null
  const count = w('selectedN', { n: sel.ids.length })
  return (
    <div className={css.bar} role="region" aria-label={w('actionsFor')}>
      <div className={css.barInner}>
        <div className={css.barHead}>
          <span className={css.barCount} aria-live="polite">
            {sel.group ? <><span className={css.barGroup} data-truncate title={sel.group.label}><Txt>{sel.group.label}</Txt></span><span className={css.barN}>{count}</span></> : count}
          </span>
          {sel.ids.length >= MAX_CARDS && <span className={css.barNote}>{w('selectionCapped', { n: MAX_CARDS })}</span>}
          <Button variant="ghost" icon="layers" className={css.barGroupBtn} onPress={() => command.openGroups(true)}>{w('selectGroup')}</Button>
          <IconButton icon="x" label={w('clearSelection')} onPress={command.clear} />
        </div>
        <div className={css.verbs}>
          {VERBS.map((verb) => (
            <Button key={verb.id} data-verb={verb.id} variant={verb.id === 'fix' ? 'primary' : 'secondary'} icon={verb.id} className={css.verb}
              onPress={() => command.open({ verb: verb.id, selection: command.selection })}>
              {verb.label[lang]}
            </Button>
          ))}
        </div>
      </div>
    </div>
  )
}
