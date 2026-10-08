// Panels, section titles, link rows, folded lists, property lists, and the designed loading, empty and error states.
import { useState, type ReactNode } from 'react'
import { Button as AriaButton } from 'react-aria-components'
import { usePrefs } from '../i18n/prefs'
import { N } from '../i18n/text'
import { Button } from './Button'
import { Go, type Search } from './Go'
import { Icon, type IconName } from './Icon'
import css from './Panel.module.css'

export function Panel({ children, pad, emphasis, className, as: Tag = 'div', label }:
  { children: ReactNode; pad?: boolean; emphasis?: boolean; className?: string; as?: 'div' | 'section' | 'article' | 'aside'; label?: string }) {
  return <Tag aria-label={label} className={[css.panel, pad && css.pad, emphasis && css.emphasis, className].filter(Boolean).join(' ')}>{children}</Tag>
}

export function Section({ title, count, unit, children, className, id }:
  { title: string; count?: number; unit?: string; children: ReactNode; className?: string; id?: string }) {
  const heading = id ?? `s-${title.replace(/\s+/g, '-')}`
  return (
    <section className={[css.section, className].filter(Boolean).join(' ')} aria-labelledby={heading}>
      <h2 className={css.sectionTitle} id={heading}>
        <span>{title}</span>
        {count !== undefined && <N value={count} className={css.count} />}
        {unit && <span className={css.unit}>{unit}</span>}
      </h2>
      {children}
    </section>
  )
}

interface RowBody { icon?: IconName; title: ReactNode; sub?: ReactNode; end?: ReactNode; chevron?: boolean }

function RowInside({ icon, title, sub, end, chevron = true }: RowBody) {
  return (
    <>
      {icon && <span className={css.rowIcon}><Icon name={icon} /></span>}
      <span className={css.rowMain}>
        <span className={css.rowTitle}>{title}</span>
        {sub && <span className={css.rowSub}>{sub}</span>}
      </span>
      {end !== undefined && <span className={css.rowEnd}>{end}</span>}
      {chevron && <Icon name="chevron" className={css.chev} />}
    </>
  )
}

/** A row that opens a view: icon, title, subtitle, end value, chevron. */
export function RowLink({ to, search, current, label, ...body }: RowBody & { to: string; search?: Search; current?: boolean; label?: string }) {
  return <Go to={to} search={search} className={css.row} current={current} label={label}><RowInside {...body} /></Go>
}

/** A row that selects or opens something in place (a sheet, the inspector). */
export function RowButton({ onPress, pressed, ...body }: RowBody & { onPress: () => void; pressed?: boolean }) {
  return <AriaButton className={css.row} onPress={onPress} aria-pressed={pressed}><RowInside {...body} /></AriaButton>
}

/** The first `first` items, then "Show all N" (DESIGN.md: never a phone list longer than a screen by default). */
export function FoldList<T>({ items, first = 6, render, label }: { items: T[]; first?: number; render: (item: T, index: number) => ReactNode; label?: string }) {
  const { t } = usePrefs()
  const [open, setOpen] = useState(false)
  const shown = open ? items : items.slice(0, first)
  return (
    <>
      <ul aria-label={label}>{shown.map((item, i) => <li key={i}>{render(item, i)}</li>)}</ul>
      {items.length > first && (
        <div className={css.foldMore}>
          <Button variant="ghost" onPress={() => setOpen(!open)} aria-expanded={open}>
            {open ? t('showLess') : t('showAllN', { n: items.length })}
          </Button>
        </div>
      )}
    </>
  )
}

export function Props({ rows }: { rows: [ReactNode, ReactNode, boolean?][] }) {
  return (
    <dl className={css.props}>
      {rows.map(([term, value, muted], i) => <div key={i}><dt>{term}</dt><dd className={muted ? css.muted : undefined}>{value}</dd></div>)}
    </dl>
  )
}

/** Loading: a skeleton in the final geometry, announced politely. */
export function Skeleton({ label }: { label: string }) {
  return (
    <div className={css.skeleton} role="status" aria-live="polite">
      <span className="sr">{label}</span>
      <span className={css.bone} /><span className={css.bone} /><span className={css.bone} />
    </div>
  )
}

export function StateMessage({ kind = 'empty', icon, title, sub, action }:
  { kind?: 'empty' | 'error'; icon?: IconName; title: string; sub?: ReactNode; action?: ReactNode }) {
  return (
    <div className={[css.state, kind === 'error' && css.stateError].filter(Boolean).join(' ')} role={kind === 'error' ? 'alert' : undefined}>
      <span className={css.stateIcon}><Icon name={icon ?? (kind === 'error' ? 'problems' : 'clock')} /></span>
      <div className={css.stateBody}>
        <div className={css.stateTitle}>{title}</div>
        {sub && <div className={css.stateSub}>{sub}</div>}
        {action}
      </div>
    </div>
  )
}
