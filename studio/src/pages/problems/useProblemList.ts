// The Problems list's state: the search words as typed and in the address, the check the list opened with (pinned
// until the person asks for a newer one), the filters, the rows and groups they leave, how many are drawn, and
// stable setters so typing a search word does not draw the controls again.
import { useNavigate, useSearch } from '@tanstack/react-router'
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import type { StudioData } from '../../data/types'
import { usePrefs } from '../../i18n/prefs'
import { facetParam, filterRows, itemsOf, prepare, readFilters, type Facet, type ProblemsSearch } from './model'

const FIRST = 30      // rows drawn at first; "show more" adds MORE at a time
export const MORE = 200
const TYPING_MS = 300 // the pause after typing before the words are written into the address

export function useProblemList(data: StudioData) {
  const { lang } = usePrefs()
  const address = useSearch({ strict: false }) as ProblemsSearch
  const navigate = useNavigate()
  const [typed, setTyped] = useTypedSearch(address, navigate)
  const search = useMemo(() => ({ ...address, q: typed || undefined }), [address, typed])
  // The cards the list shows stay those it opened with until the person asks for a newer check's
  const [pinned, setPinned] = useState(() => data.cards)
  const shownData = useMemo(() => (pinned === data.cards ? data : { ...data, cards: pinned }), [data, pinned])
  // Only the sections the list reads: another section arriving (a card's evidence) does not prepare it again
  const list = useMemo(() => prepare(shownData, lang), [pinned, shownData.system, shownData.story, shownData.plans, lang])   // eslint-disable-line react-hooks/exhaustive-deps
  const filters = readFilters(search)
  const key = JSON.stringify([filters.q, filters.who, filters.chosen, filters.group])
  const result = useMemo(() => filterRows(list, filters), [list, key])   // eslint-disable-line react-hooks/exhaustive-deps
  const items = useMemo(() => itemsOf(result.rows, filters.group, list.order), [result, filters.group, list])
  const ids = useMemo(() => result.rows.map((row) => row.card.id), [result])
  const shown = useMemo(() => result.rows.map((row) => row.card), [result])
  const [limit, setLimit] = useState(FIRST)
  useEffect(() => setLimit(FIRST), [key])
  const set = (patch: Partial<ProblemsSearch>) => navigate({ to: '/problems', search: { ...search, ...patch }, replace: true })
  // Stable handles for the controls, so typing a search word does not draw them again
  const latest = useRef(set)
  useLayoutEffect(() => { latest.current = set })
  const onSet = useCallback((patch: Partial<ProblemsSearch>) => latest.current(patch), [])
  const onFacet = useCallback((facet: Facet, values: string[]) => latest.current({ [facet]: facetParam(values) }), [])
  const chosenKey = JSON.stringify(filters.chosen)
  const chosen = useMemo(() => filters.chosen, [chosenKey])   // eslint-disable-line react-hooks/exhaustive-deps
  return {
    search, typed, setTyped, pinned, list, filters, result, items, ids, shown, limit, set, onSet, onFacet, chosen,
    changed: pinned !== data.cards,
    showChanges: () => setPinned(data.cards),
    showMore: () => setLimit(limit + MORE),
  }
}

export type ProblemList = ReturnType<typeof useProblemList>

/** The search words filter as they are typed and reach the address a moment later: writing the address on every
 * keystroke draws the router's subscribers again before the list can answer. A change of the address from
 * elsewhere (back, a link, the address bar) replaces the words. */
function useTypedSearch(address: ProblemsSearch, navigate: ReturnType<typeof useNavigate>) {
  const [typed, setTyped] = useState(address.q ?? '')
  const seen = useRef(address.q)
  if (seen.current !== address.q) { seen.current = address.q; if ((address.q ?? '') !== typed) setTyped(address.q ?? '') }
  useEffect(() => {
    if ((address.q ?? '') === typed) return
    const timer = setTimeout(() => {
      seen.current = typed || undefined
      navigate({ to: '/problems', search: (was: ProblemsSearch) => ({ ...was, q: typed || undefined }), replace: true })
    }, TYPING_MS)
    return () => clearTimeout(timer)
  }, [typed, address.q, navigate])
  return [typed, setTyped] as const
}
