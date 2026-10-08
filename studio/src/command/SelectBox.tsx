// A check box that selects a card or a group for the command centre. A native input, so Shift-click (a range over the
// list's visible order), Space and screen readers all behave as people expect; 44px to the thumb on the phone.
import { Icon } from '../components/Icon'
import css from './command.module.css'

export function SelectBox({ checked, mixed, label, onToggle }:
  { checked: boolean; mixed?: boolean; label: string; onToggle: (shift: boolean) => void }) {
  return (
    <label className={css.box} data-checked={checked || mixed ? '' : undefined}>
      <input type="checkbox" className={css.boxInput} checked={checked} aria-label={label}
        ref={(input) => { if (input) input.indeterminate = Boolean(mixed && !checked) }}
        onClick={(event) => { event.stopPropagation(); onToggle(event.shiftKey) }} onChange={() => undefined} />
      <span className={css.boxMark} aria-hidden="true">{checked ? <Icon name="check" size={14} /> : mixed ? <span className={css.boxDash} /> : null}</span>
    </label>
  )
}
