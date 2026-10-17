// What a check looks at and how fast it runs, chosen before it starts (eaos/check_choices.py offered): the complete
// check or some paths, each with what it looks at; the normal mode or the speed mode, whose warning says it uses more
// tokens. The paths and their words come from the preview, never written twice here.
import { Segmented } from '../components/Controls'
import type { CheckOffer } from '../data/actions/types'
import { usePrefs } from '../i18n/prefs'
import { Txt } from '../i18n/text'
import { SelectBox } from './SelectBox'
import { useCmdWords } from './words'
import css from './command.module.css'

export interface CheckChoice { paths: string[]; mode: 'normal' | 'speed' }

const COMPLETE = 'complete'

/** The paths after one is turned on or off: complete stands alone, and nothing chosen is the complete check. */
export function toggled(paths: string[], id: string): string[] {
  if (id === COMPLETE) return [COMPLETE]
  const next = paths.includes(id) ? paths.filter((p) => p !== id) : [...paths.filter((p) => p !== COMPLETE), id]
  return next.length ? next : [COMPLETE]
}

/** The check's inputs for the choice: no paths for the complete check. */
export const checkInputs = (choice: CheckChoice) => ({ mode: choice.mode, ...(choice.paths.includes(COMPLETE) ? {} : { paths: choice.paths }) })

export function CheckOptions({ offer, choice, onChange }: { offer: CheckOffer; choice: CheckChoice; onChange: (next: CheckChoice) => void }) {
  const w = useCmdWords()
  const { lang } = usePrefs()
  return (
    <div className={css.form} data-check-options>
      <p className={css.fieldLabel}>{w('checkPaths')}</p>
      {offer.paths.map((path) => (
        <div key={path.id} className={css.check} data-path={path.id}>
          <SelectBox checked={choice.paths.includes(path.id)} label={path.name[lang]} onToggle={() => onChange({ ...choice, paths: toggled(choice.paths, path.id) })} />
          <span>{path.name[lang]}<span className={css.hint}><Txt>{path.looks_at[lang]}</Txt></span></span>
        </div>
      ))}
      <Segmented label={w('checkMode')} value={choice.mode} onChange={(mode) => onChange({ ...choice, mode })}
        options={[{ id: 'normal', label: w('modeNormal') }, { id: 'speed', label: w('modeSpeed') }]} />
      {choice.mode === 'speed' && <p className={css.pvWarn} role="note" data-speed-warning>{w('speedWarning')}</p>}
    </div>
  )
}
