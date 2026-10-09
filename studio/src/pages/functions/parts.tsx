// The pieces both function views share: the link to one function (keeping the list's filters) and its complexity
// badge, measured against Lizard's warning line.
import { Link, useSearch } from '@tanstack/react-router'
import type { ReactNode } from 'react'
import { level, type Fn } from './model'
import { useFunctionWords } from './words'
import css from './Functions.module.css'

export type ListSearch = { q?: string; sort?: string; show?: string; kind?: string; module?: string }

/** A link to one function's view, keeping the list's filters. */
export function FnLink({ id, className, children, label, current }: { id: string; className?: string; children: ReactNode; label?: string; current?: boolean }) {
  const search = useSearch({ strict: false }) as ListSearch
  const keep = Object.fromEntries(Object.entries(search).filter(([k]) => ['q', 'sort', 'show', 'kind', 'module'].includes(k)))
  return (
    <Link to="/system/f/$functionId" params={{ functionId: id }} search={keep} className={className} aria-label={label}
      aria-current={current ? 'page' : undefined}>{children}</Link>
  )
}

export function Level({ fn }: { fn: Fn }) {
  const w = useFunctionWords()
  const at = level(fn)
  if (at === 'none') return <span className={css.levelNone}>{w('notMeasured')}</span>
  return <span className={[css.level, css[at]].join(' ')} title={fn.complexity.src}><span className={css.levelDot} aria-hidden="true" />{w('complexityShort', { n: fn.complexity.value ?? 0 })}</span>
}
