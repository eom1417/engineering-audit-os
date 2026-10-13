// A view's search params are part of its link (#/route?a=b): a page changes them one patch at a time, and the params
// left empty are dropped so the link stays short.
import { useNavigate } from '@tanstack/react-router'

/** Changes the search params of the view at `to` (with its route `params`), replacing the history entry when `replace`. */
export function useSearchPatch<T extends object>(to: string, { replace, params }: { replace?: boolean; params?: Record<string, string> } = {}) {
  const navigate = useNavigate()
  return (patch: Partial<T>) => navigate({
    to, params, replace,
    search: (prev: T) => Object.fromEntries(Object.entries({ ...prev, ...patch }).filter(([, v]) => v !== undefined && v !== '')) as T,
  })
}
