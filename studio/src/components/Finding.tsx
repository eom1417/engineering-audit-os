// A finding in a list (severity glyph, title, path · id, who acts on it) and the evidence card that backs it.
import type { ReactNode } from 'react'
import type { Card, Fact } from '../data/types'
import { usePrefs } from '../i18n/prefs'
import { Id, Txt } from '../i18n/text'
import { SeverityGlyph } from './Chip'
import { Go, type Search } from './Go'
import { Panel } from './Panel'
import css from './Finding.module.css'

export function FindingRow({ card, to, search, current }: { card: Card; to: string; search?: Search; current?: boolean }) {
  const { t } = usePrefs()
  const path = card.paths[0]
  return (
    <Go to={to} search={search} className={css.row} current={current}>
      <SeverityGlyph severity={card.severity} word={false} />
      <span className={css.main}>
        <span className={css.title}><Txt block>{card.title}</Txt></span>
        <span className={css.meta}>{path && <Id value={path} keep={2} />}{path && <span aria-hidden="true">·</span>}<Id value={card.id} /></span>
      </span>
      <span className={[css.marker, card.needs_decision ? css.you : css.eaos].join(' ')}>{card.needs_decision ? t('needsYou') : t('eaosFixes')}</span>
    </Go>
  )
}

/** One fact a card cites: its kind, engine and id, the sentence, and the code (always LTR, its own scroll); `children`
 * follow the place (a page's code excerpt with its line numbers, its links). */
export function EvidenceCard({ fact, code, children }: { fact: Fact; code?: string; children?: ReactNode }) {
  const { t } = usePrefs()
  const where = fact.path ? `${fact.path}${fact.line ? `:${fact.line}` : ''}` : null
  return (
    <Panel as="article" className={css.evidence} label={`${t('evidence')} ${fact.id}`}>
      <div className={css.evHead}>
        <span className={css.evKind}><Id value={fact.kind} /></span>
        {fact.engine && <Id value={fact.engine} />}
        <Id value={fact.id} />
      </div>
      <p className={css.evText}><Txt block>{fact.summary}</Txt></p>
      {where && <div className={css.evHead}><span>{t('where')}</span><Id value={where} /></div>}
      {code && <pre className={css.code} data-scroll-x="" tabIndex={0} aria-label={where ?? fact.id}><code>{code}</code></pre>}
      {children}
    </Panel>
  )
}
