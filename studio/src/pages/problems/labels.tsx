// How a facet value reads: severity and state in words, an area in words when the Studio knows it, a plan step by
// its id, a component as an identifier; an empty value says what is missing.
import type { ReactNode } from 'react'
import type { CardState, Severity } from '../../data/types'
import type { WordKey } from '../../i18n/catalog'
import { usePrefs } from '../../i18n/prefs'
import { Id } from '../../i18n/text'
import type { Facet } from './model'
import { PROBLEM_WORDS, useProblemWords, type ProblemWord } from './words'

export const SEVERITY_WORD: Record<Severity, WordKey> = { critical: 'sevCritical', high: 'sevHigh', medium: 'sevMedium', low: 'sevLow', info: 'sevInfo' }
export const STATE_WORD: Record<CardState, WordKey> = {
  open: 'stateOpen', in_batch: 'stateInBatch', on_branch: 'stateOnBranch', done: 'stateDone', resolved: 'stateResolved', skipped: 'stateSkipped',
}

export function useValueLabel(): (facet: Facet, value: string) => ReactNode {
  const { t } = usePrefs()
  const w = useProblemWords()
  return (facet, value) => {
    if (facet === 'severity') return t(SEVERITY_WORD[value as Severity] ?? 'sevInfo')
    if (facet === 'state') return STATE_WORD[value as CardState] ? t(STATE_WORD[value as CardState]) : value
    if (facet === 'area') {
      if (!value) return w('noArea')
      const key = `area_${value}` as ProblemWord
      return key in PROBLEM_WORDS ? w(key) : <Id value={value} />
    }
    if (facet === 'step') return value ? <Id value={value} /> : w('noStep')
    return value ? <Id value={value} keep={2} /> : w('noComponent')
  }
}
