// A link to a Studio view: a hash route and its search params, so every entity has a link that restores its view.
import { Link } from '@tanstack/react-router'
import type { ReactNode } from 'react'
import { Id } from '../i18n/text'

export type Search = Record<string, string | undefined>

export function Go({ to, search, className, children, label, current, replace }:
  { to: string; search?: Search; className?: string; children: ReactNode; label?: string; current?: boolean; replace?: boolean }) {
  return (
    <Link to={to} search={search ?? {}} className={className} aria-label={label} replace={replace}
      aria-current={current ? 'page' : undefined} activeOptions={{ exact: true, includeSearch: true }}>
      {children}
    </Link>
  )
}

/** Ids as list items, each a link to the view `to` with the id as its `param` search param. */
export function IdLinks({ ids, to, param, className }: { ids: readonly string[]; to: string; param: string; className?: string }) {
  return <>{ids.map((id) => <li key={id}><Go to={to} search={{ [param]: id }} className={className}><Id value={id} /></Go></li>)}</>
}
