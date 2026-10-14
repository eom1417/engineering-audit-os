// Pieces every Change page shares: the section's own navigation (Overview, Bridge, Gaps, Plans), the "not measured yet"
// state from the report's coverage row, the closure meter, the task-state bar and the links to a step, task or
// operation.
import type { ReactNode } from 'react'
import { useRouterState } from '@tanstack/react-router'
import { Go } from '../../components/Go'
import { NotHere, Panel, StateMessage } from '../../components/Panel'
import type { Gap, OpState } from '../../data/change'
import type { StudioData } from '../../data/types'
import { Id, N } from '../../i18n/text'
import { layout, PageTitle } from '../../shell/Layout'
import { useCoverageRow } from '../library/model'
import { TASK_STATES } from './model'
import { STATE_WORD, useChangeWords, type ChangeWord } from './words'
import css from './change.module.css'

const NAV = [
  { to: '/change', word: 'navOverview', match: (p: string) => p === '/change' || p === '/change/timeline' },
  { to: '/change/bridge', word: 'navBridge', match: (p: string) => p === '/change/bridge' },
  { to: '/change/gaps', word: 'navGaps', match: (p: string) => p.startsWith('/change/gaps') },
  { to: '/plans', word: 'navPlans', match: (p: string) => /^\/(plans|tasks)(\/|$)/.test(p) },
] as const

/** Change's places as one row of links, the current one marked (C-experience 2.3: Bridge / Gaps / Plans). */
export function ChangeNav() {
  const w = useChangeWords()
  const path = useRouterState({ select: (s) => s.location.pathname })
  return (
    <nav aria-label={w('changeNav')} className={css.nav}>
      {NAV.map((item) => (
        <Go key={item.to} to={item.to} className={css.navLink} current={item.match(path)}>{w(item.word)}</Go>
      ))}
    </nav>
  )
}

/** A plan, step, task, operation or gap the link names and this check does not have, with the way back. */
export function Missing({ title, back = '/plans', label = 'backToPlans' }: { title: string; back?: string; label?: ChangeWord }) {
  const w = useChangeWords()
  return <div className={layout.page}><ChangeNav /><PageTitle title={title} /><NotHere title={w('oldLink')} sub={null} back={back} label={w(label)} /></div>
}

/** A section the report does not hold: what is missing, and why. */
export function NotMeasured({ data, section, title }: { data: StudioData; section: string; title: string }) {
  const w = useChangeWords()
  const row = useCoverageRow(data, section)
  return (
    <Panel>
      <StateMessage title={title} sub={<>{w('notMeasured')}{row?.detail ? <> — {row.detail}</> : null}</>} />
    </Panel>
  )
}

/** A share as a short bar with its words beside it. */
export function Meter({ value, children }: { value: number; children: ReactNode }) {
  return (
    <span className={css.closure}>
      <span className={css.meter} aria-hidden="true"><i style={{ inlineSize: `${Math.round(value * 100)}%` }} /></span>
      <span>{children}</span>
    </span>
  )
}

/** How far a gap is closed by its cards; a gap no card closes says so (null is never drawn as 0). */
export function Closure({ gap }: { gap: Gap }) {
  const w = useChangeWords()
  if (gap.operation === 'retain' && !gap.cards.length) return <span className={css.muted}>{w('stays')}</span>
  if (!gap.cards.length || gap.closed.value === null) return <span className={css.muted}>{w('noCard')}</span>
  return <Meter value={gap.closed.value}>{w('closedOf', { c: gap.cards_closed, n: gap.cards.length })}</Meter>
}

/** A step's tasks by state, as one bar with the counts written beside it. */
export function StateBar({ counts }: { counts: Record<OpState, number> }) {
  const w = useChangeWords()
  const total = TASK_STATES.reduce((s, k) => s + counts[k], 0)
  return (
    <span className={css.stateBar}>
      <span className={css.bar} aria-hidden="true">
        {total > 0 && TASK_STATES.map((k) => counts[k] > 0 && <i key={k} className={css[`st_${k}`]} style={{ flexGrow: counts[k] }} />)}
      </span>
      <span className={css.stateWords}>
        {TASK_STATES.filter((k) => counts[k] > 0).map((k) => <span key={k}><i className={[css.dot, css[`st_${k}`]].join(' ')} aria-hidden="true" />{w(STATE_WORD[k])} <N value={counts[k]} /></span>)}
      </span>
    </span>
  )
}

export function StepLink({ plan, step, children }: { plan: string; step: string; children?: ReactNode }) {
  return <Go to={`/plans/${encodeURIComponent(plan)}/${encodeURIComponent(step)}`} className={css.inlineLink}>{children ?? <Id value={step} />}</Go>
}

export function OpLink({ id, children }: { id: string; children?: ReactNode }) {
  return <Go to={`/ops/${encodeURIComponent(id)}`} className={css.inlineLink}>{children ?? <Id value={id} keep={3} />}</Go>
}

export function GapLink({ id, children }: { id: string; children?: ReactNode }) {
  return <Go to={`/change/gaps/${encodeURIComponent(id)}`} className={css.inlineLink}>{children ?? <Id value={id} keep={3} />}</Go>
}

/** Links in a row, wrapping; nothing when there are none. */
export function LinkList({ children, label }: { children: ReactNode[]; label?: string }) {
  if (!children.length) return null
  return <ul className={css.links} aria-label={label}>{children.map((child, i) => <li key={i}>{child}</li>)}</ul>
}
