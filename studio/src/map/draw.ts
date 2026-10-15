// What every SVG map of the Studio shares: text cut to the room of its box, the size of the box it is drawn in, and a
// drawn node pressed from the keyboard.
import { useCallback, useMemo, useRef, useState, type KeyboardEvent } from 'react'

/** The links touching the chosen node, by their `key` field; none when nothing is chosen. */
export function useLinked<E extends { from: string; to: string }, K extends keyof E>(edges: E[], selected: string | undefined, key: K) {
  return useMemo(() => {
    const on = new Set<E[K]>()
    if (selected) for (const e of edges) if (e.from === selected || e.to === selected) on.add(e[key])
    return on
  }, [edges, selected, key])
}

/** The key handler of a drawn node that is a button: Enter and Space press it, as a click does. */
export function pressKey(press: () => void) {
  return (e: KeyboardEvent) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); press() } }
}

/** What a drawn node carries when the map is interactive: a button in the focus order, its label, Enter and Space press it. */
export function pressable(interactive: boolean, id: string, label: string, pressed: boolean | undefined, onFocus?: (id: string) => void) {
  if (!interactive) return {}
  const press = () => onFocus?.(id)
  return { role: 'button', tabIndex: 0, 'aria-label': label, ...(pressed === undefined ? {} : { 'aria-pressed': pressed }), onClick: press, onKeyDown: pressKey(press) }
}

/** The pixel size of the drawing's box, followed as it changes. */
export function useBox(): [(el: HTMLDivElement | null) => void, { w: number; h: number }] {
  const [size, setSize] = useState({ w: 0, h: 0 })
  const watcher = useRef<ResizeObserver | null>(null)
  const attach = useCallback((el: HTMLDivElement | null) => {
    watcher.current?.disconnect()
    if (!el) return
    watcher.current = new ResizeObserver(([entry]) => setSize({ w: entry.contentRect.width, h: entry.contentRect.height }))
    watcher.current.observe(el)
  }, [])
  return [attach, size]
}

/** A sentence too long for its box: cut at its end. */
export function clip(text: string, room: number): string {
  return text.length <= room ? text : text.slice(0, room - 1) + '…'
}

/** "…/tail" of a long identifier for a fixed-width box: it keeps its end (the full value goes in the title). */
export function fit(text: string, room: number): string {
  return text.length <= room ? text : '…' + text.slice(-(room - 1))
}
