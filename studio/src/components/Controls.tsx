// The segmented control (React Aria ToggleButtonGroup: one choice always selected) and the search field.
import type { ReactNode } from 'react'
import { Button as AriaButton, Input, SearchField as AriaSearchField, ToggleButton, ToggleButtonGroup } from 'react-aria-components'
import { usePrefs } from '../i18n/prefs'
import { Icon } from './Icon'
import css from './Controls.module.css'

export function Segmented<K extends string>({ label, value, onChange, options, comfortable }:
  { label: string; value: K; onChange: (value: K) => void; options: { id: K; label: ReactNode; lang?: string; aria?: string }[]; comfortable?: boolean }) {
  return (
    <ToggleButtonGroup aria-label={label} selectionMode="single" disallowEmptySelection selectedKeys={[value]}
      onSelectionChange={(keys) => { const next = [...keys][0]; if (next) onChange(next as K) }}
      className={[css.seg, comfortable && css.comfortable].filter(Boolean).join(' ')}>
      {options.map((option) => (
        <ToggleButton key={option.id} id={option.id} className={css.segBtn} lang={option.lang} aria-label={option.aria}>{option.label}</ToggleButton>
      ))}
    </ToggleButtonGroup>
  )
}

export function SearchField({ label, placeholder, value, onChange, autoFocus }:
  { label: string; placeholder?: string; value: string; onChange: (value: string) => void; autoFocus?: boolean }) {
  const { t } = usePrefs()
  return (
    <AriaSearchField aria-label={label} value={value} onChange={onChange} autoFocus={autoFocus} className={css.field}>
      <Icon name="search" />
      <Input placeholder={placeholder} />
      <AriaButton className={css.clear} aria-label={t('close')}><Icon name="x" /></AriaButton>
    </AriaSearchField>
  )
}
