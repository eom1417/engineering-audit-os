// What a check looks at and how fast it runs, chosen before it starts (eaos/check_choices.py offered): the complete
// check or some paths, each with what it looks at; with the AI or the rules alone; the normal mode or the speed mode, whose warning says it uses more
// tokens; and, for an app with a sign-in, how its pages are opened (kept) and the published address read for this check.
// The paths and their words come from the preview, never written twice here.
import { Input, Label, TextField } from 'react-aria-components'
import { Segmented } from '../components/Controls'
import type { CheckOffer, SignInWay } from '../data/actions/types'
import { usePrefs } from '../i18n/prefs'
import { Txt } from '../i18n/text'
import { SelectBox } from './SelectBox'
import { useCmdWords } from './words'
import css from './command.module.css'

/** `ai` false: this one check with the rules alone (audit's without_ai); the assistant kept for the next ones.
 * `signIn`: how the pages behind the app's sign-in are opened (kept); `published`: its published address, this check only. */
export interface CheckChoice { paths: string[]; mode: 'normal' | 'speed'; ai?: boolean; signIn?: SignInWay; published?: string }

const COMPLETE = 'complete'

/** The paths after one is turned on or off: complete stands alone, and nothing chosen is the complete check. */
export function toggled(paths: string[], id: string): string[] {
  if (id === COMPLETE) return [COMPLETE]
  const next = paths.includes(id) ? paths.filter((p) => p !== id) : [...paths.filter((p) => p !== COMPLETE), id]
  return next.length ? next : [COMPLETE]
}

/** The check's inputs for the choice: no paths for the complete check, the AI left out only when turned off, the way to
 * sign in when one is chosen, and a published address only when the person named one (and signs in by hand). */
export const checkInputs = (choice: CheckChoice) => ({ mode: choice.mode, ...(choice.paths.includes(COMPLETE) ? {} : { paths: choice.paths }),
  ...(choice.ai === false ? { without_ai: true } : {}), ...(choice.signIn ? { sign_in: choice.signIn } : {}),
  ...(choice.signIn === 'hand' && choice.published?.trim() ? { published: choice.published.trim() } : {}) })

const SIGN_IN_LEAD = { hand: 'signInHandLead', test_user: 'signInTestUserLead', none: 'signInNoneLead' } as const

/** A check pressed anywhere is a new check: without `fresh` EAOS answers "already checked" and nothing runs (the dead
 * end of Home's next step, the palette and the chat). Only a check that goes on from a stage keeps the one on record. */
export const freshOf = (request: { action?: string; inputs?: Record<string, unknown> } | null | undefined, values: Record<string, unknown>) =>
  (request?.action === 'audit' && !values.again_from && !request.inputs?.again_from ? { fresh: true } : {})

export function CheckOptions({ offer, choice, onChange }: { offer: CheckOffer; choice: CheckChoice; onChange: (next: CheckChoice) => void }) {
  const w = useCmdWords()
  const { lang } = usePrefs()
  return (
    <div className={css.form} data-check-options>
      <p className={css.fieldLabel}>{w('checkPaths')}</p>
      {offer.paths.map((path) => {
        const pick = () => onChange({ ...choice, paths: toggled(choice.paths, path.id) })
        // the whole row chooses the path, its words as well as its box (the box stops its own click from counting twice)
        return (
          <div key={path.id} className={css.check} data-path={path.id} onClick={pick}>
            <SelectBox checked={choice.paths.includes(path.id)} label={path.name[lang]} onToggle={pick} />
            <span>{path.name[lang]}<span className={css.hint}><Txt>{path.looks_at[lang]}</Txt></span></span>
          </div>
        )
      })}
      <Segmented label={w('checkAi')} value={choice.ai === false ? 'off' : 'on'} onChange={(ai) => onChange({ ...choice, ai: ai === 'on' })}
        options={[{ id: 'on', label: w('aiOn') }, { id: 'off', label: w('aiOff') }]} />
      {choice.ai === false && <p className={css.hint} role="note" data-ai-off>{w('aiOffLead')}</p>}
      <Segmented label={w('checkMode')} value={choice.mode} onChange={(mode) => onChange({ ...choice, mode })}
        options={[{ id: 'normal', label: w('modeNormal') }, { id: 'speed', label: w('modeSpeed') }]} />
      {choice.mode === 'speed' && <p className={css.pvWarn} role="note" data-speed-warning>{w('speedWarning')}</p>}
      {(offer.sign_in_seen.length > 0 || offer.sign_in) && (
        <>
          {offer.sign_in_seen.length > 0 && <p className={css.hint} data-sign-in-seen>{w('signInSeen', { where: offer.sign_in_seen[0].split(':')[0] })}</p>}
          <Segmented label={w('signInWay')} value={choice.signIn ?? 'hand'} onChange={(signIn) => onChange({ ...choice, signIn })}
            options={[{ id: 'hand', label: w('signInHand') }, { id: 'test_user', label: w('signInTestUser') }, { id: 'none', label: w('signInNoSignIn') }]} />
          <p className={css.hint} role="note">{w(SIGN_IN_LEAD[choice.signIn ?? 'hand'])}</p>
          {(choice.signIn ?? 'hand') === 'hand' && (
            <TextField className={css.field} value={choice.published ?? ''} onChange={(published) => onChange({ ...choice, signIn: 'hand', published })}>
              <Label className={css.fieldLabel}>{w('publishedLabel')}</Label>
              <Input className={css.input} dir="ltr" type="url" inputMode="url" placeholder="https://" data-published />
              <span className={css.hint}>{w('publishedHint')}</span>
            </TextField>
          )}
        </>
      )}
    </div>
  )
}
