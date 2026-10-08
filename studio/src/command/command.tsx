// The command centre inside the shell: the selection the Problems, Change and System pages share (cleared when the
// person moves to another section, or with Esc), and the one preview sheet every verb, palette action and button
// opens. The pieces that float over every page (action bar, question toast, run pill) live in CommandHost.
import { useRouterState } from '@tanstack/react-router'
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import type { Selection, VerbId } from '../data/actions/types'
import { EMPTY, pickGroup, setMany, toSelection, toggle, type GroupRef, type SelState } from './selectionModel'

export interface CommandRequest {
  verb?: VerbId
  action?: string
  selection?: Selection | null
  inputs?: Record<string, unknown>
}

export interface Command {
  sel: SelState
  selection: Selection | null
  toggle(id: string, shift: boolean, order: string[]): void
  setMany(ids: string[], on: boolean): void
  pick(ids: string[], group: GroupRef | null): void
  clear(): void
  /** The open preview's request, if any */
  request: CommandRequest | null
  open(request: CommandRequest): void
  close(): void
  groupsOpen: boolean
  openGroups(open: boolean): void
}

const CommandContext = createContext<Command | null>(null)

export function CommandProvider({ children }: { children: ReactNode }) {
  const [sel, setSel] = useState<SelState>(EMPTY)
  const [request, setRequest] = useState<CommandRequest | null>(null)
  const [groupsOpen, openGroups] = useState(false)
  const section = useRouterState({ select: (s) => s.location.pathname.split('/')[1] ?? '' })

  // A selection belongs to the section it was made in
  useEffect(() => { setSel(EMPTY) }, [section])

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== 'Escape' || event.defaultPrevented || document.querySelector('[role="dialog"]')) return
      setSel((was) => (was.ids.length ? EMPTY : was))
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  const open = useCallback((next: CommandRequest) => setRequest(next), [])
  const value = useMemo<Command>(() => ({
    sel,
    selection: toSelection(sel),
    toggle: (id, shift, order) => setSel((was) => toggle(was, id, shift, order)),
    setMany: (ids, on) => setSel((was) => setMany(was, ids, on)),
    pick: (ids, group) => setSel((was) => pickGroup(was, ids, group)),
    clear: () => setSel(EMPTY),
    request, open, close: () => setRequest(null),
    groupsOpen, openGroups,
  }), [sel, request, open, groupsOpen])
  return <CommandContext.Provider value={value}>{children}</CommandContext.Provider>
}

export function useCommand(): Command {
  const value = useContext(CommandContext)
  if (!value) throw new Error('useCommand outside CommandProvider')
  return value
}

/** The command centre where the page may be rendered without it (the gallery, a test): null instead of an error. */
export function useCommandMaybe(): Command | null {
  return useContext(CommandContext)
}
