// What every SVG map of the Studio shares: text cut to the room of its box, the size of the box it is drawn in, and a
// drawn node pressed from the keyboard.
import { useCallback, useRef, useState, type KeyboardEvent } from 'react'

/** The key handler of a drawn node that is a button: Enter and Space press it, as a click does. */
export function pressKey(press: () => void) {
  return (e: KeyboardEvent) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); press() } }
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
