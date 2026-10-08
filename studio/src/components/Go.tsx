// A link to a Studio view: a hash route and its search params, so every entity has a link that restores its view.
import { Link } from '@tanstack/react-router'
import type { ReactNode } from 'react'

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
