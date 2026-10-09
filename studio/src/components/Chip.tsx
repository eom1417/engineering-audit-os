// Chips with a dot and a word, the severity glyph (four ordinal bars rising toward inline-end) and the operation
// chip (reserved hues, icon and word). Colour never carries meaning alone.
import type { ReactNode } from 'react'
import { Button as AriaButton, type ButtonProps } from 'react-aria-components'
import type { Freshness, Relation, Severity } from '../data/types'
import { usePrefs } from '../i18n/prefs'
import { Id } from '../i18n/text'
import { Icon, type IconName } from './Icon'
import css from './Chip.module.css'

export type Tone = 'neutral' | 'good' | 'warning' | 'serious' | 'critical' | 'accent'

export function Chip({ tone = 'neutral', dot = true, children }: { tone?: Tone; dot?: boolean; children: ReactNode }) {
  return <span className={[css.chip, css[tone]].join(' ')}>{dot && <span className={css.dot} aria-hidden="true" />}{children}</span>
}

export function ChipButton({ tone = 'neutral', children, ...rest }: Omit<ButtonProps, 'children' | 'className'> & { tone?: Tone; children: ReactNode }) {
  return (
    <AriaButton {...rest} className={[css.chip, css[tone]].join(' ')}>
      <span className={css.dot} aria-hidden="true" />{children}
    </AriaButton>
  )
}

const FRESH: Record<Freshness, { tone: Tone; word: 'freshFresh' | 'freshBranchMoved' | 'freshEaosUpdated' | 'freshUnknown' }> = {
  fresh: { tone: 'good', word: 'freshFresh' },
  branch_moved: { tone: 'warning', word: 'freshBranchMoved' },
  eaos_updated: { tone: 'warning', word: 'freshEaosUpdated' },
  unknown: { tone: 'neutral', word: 'freshUnknown' },
}

/** The scan's freshness; pressing it opens the sheet that explains it. */
export function FreshnessChip({ freshness, onPress }: { freshness: Freshness; onPress?: () => void }) {
  const { t } = usePrefs()
  const { tone, word } = FRESH[freshness]
  return <ChipButton tone={tone} onPress={onPress}>{t(word)}</ChipButton>
}

const SEV_BARS: Record<Severity, number> = { info: 0, low: 1, medium: 2, high: 3, critical: 4 }
const SEV_CLASS: Record<Severity, string> = { info: css.sevInfo, low: css.sevLow, medium: css.sevMedium, high: css.sevHigh, critical: css.sevCritical }
const SEV_WORD = { info: 'sevInfo', low: 'sevLow', medium: 'sevMedium', high: 'sevHigh', critical: 'sevCritical' } as const

/** The four bars and the word; a card of severity "info" (the contract allows it) shows no bar lit and its word. */
export function SeverityGlyph({ severity, word = true }: { severity: Severity; word?: boolean }) {
  const { t } = usePrefs()
  const name = t(SEV_WORD[severity] ?? 'sevInfo')
  return (
    <span className={[css.sev, SEV_CLASS[severity] ?? css.sevLow].join(' ')} aria-label={word ? undefined : name} role={word ? undefined : 'img'}>
      <span className={css.bars} aria-hidden="true">
        {[0, 1, 2, 3].map((i) => <i key={i} data-on={i < (SEV_BARS[severity] ?? 0) ? '' : undefined} />)}
      </span>
      {word && <span>{name}</span>}
    </span>
  )
}

const OP: Record<Relation, { key: string; icon: IconName; word: 'opKeep' | 'opModify' | 'opRebuild' | 'opDelete' | 'opMerge' | 'opIntroduce' }> = {
  retain: { key: 'keep', icon: 'opKeep', word: 'opKeep' },
  modify: { key: 'modify', icon: 'opModify', word: 'opModify' },
  rebuild: { key: 'rebuild', icon: 'opRebuild', word: 'opRebuild' },
  delete: { key: 'delete', icon: 'opDelete', word: 'opDelete' },
  merge: { key: 'merge', icon: 'opMerge', word: 'opMerge' },
  missing: { key: 'introduce', icon: 'opIntroduce', word: 'opIntroduce' },
  introduce: { key: 'introduce', icon: 'opIntroduce', word: 'opIntroduce' },
}

export function OperationChip({ relation, to }: { relation: Relation; to?: string | null }) {
  const { t } = usePrefs()
  const op = OP[relation]
  return (
    <span className={[css.op, css[op.key]].join(' ')}>
      <span className={css.opIcon}><Icon name={op.icon} size={14} /></span>
      {t(op.word)}
      {to ? <span className={css.opTo}><Icon name="arrow" size={12} /><Id value={to} /></span> : null}
    </span>
  )
}

export function Badge({ count, label }: { count: number; label?: string }) {
  return <span className={[css.badge, 'num'].join(' ')} aria-label={label}>{count}</span>
}
