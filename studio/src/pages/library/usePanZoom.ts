// Pan and zoom for a drawing in a scrolling box (a document's diagram, and its full screen view): the drawing is
// sized to its natural size times the scale, so the box's own scroll pans it (scroll bars, keyboard arrows, a
// trackpad, a finger); a mouse drags it; Ctrl/Cmd + wheel, a pinch (full screen) or + and − zoom around the pointer.
// The box is left to right whatever the page's direction, so the drawing never mirrors.
import { useCallback, useEffect, useLayoutEffect, useRef, useState, type RefObject } from 'react'
import { busiest, clampZoom, fitScale, zoomScroll, ZOOM, type Size } from './diagram'

export interface PanZoom {
  /** The scale, or null before the box is measured */
  k: number | null
  zoomBy: (factor: number, at?: { x: number; y: number }) => void
  fit: () => void
  /** True when the drawing is larger than its box, so it can be dragged */
  pans: boolean
}

export function usePanZoom(box: RefObject<HTMLDivElement | null>, natural: Size | null,
  { floor = 0, fill = 1, fitHeight = false, pinch = false, wheel = false }: { floor?: number; fill?: number; fitHeight?: boolean; pinch?: boolean; wheel?: boolean } = {}): PanZoom {
  const [k, setK] = useState<number | null>(null)
  const [pans, setPans] = useState(false)
  const chosen = useRef(false) // the reader zoomed: a resize no longer refits
  const focus = useRef<{ at: { x: number; y: number }; from: number } | null>(null)
  const first = useRef(true) // the first fit of a drawing wider than its box opens on its middle, not its empty corner
  const kRef = useRef(k)
  kRef.current = k

  const fitted = useCallback(() => {
    const el = box.current
    if (!el || !natural) return null
    return fitScale(natural, { width: el.clientWidth, height: fitHeight ? el.clientHeight : 0 }, { floor, fill })
  }, [box, natural, floor, fill, fitHeight])

  const fit = useCallback(() => {
    chosen.current = false
    focus.current = null
    setK(fitted())
  }, [fitted])

  const zoomBy = useCallback((factor: number, at?: { x: number; y: number }) => {
    const el = box.current
    const from = kRef.current
    if (!el || from === null) return
    const to = clampZoom(from * factor)
    if (to === from) return
    chosen.current = true
    focus.current = { at: at ?? { x: el.clientWidth / 2, y: el.clientHeight / 2 }, from }
    setK(to)
  }, [box])

  // The first fit, and a refit when the box changes size while the reader has not zoomed
  useEffect(() => {
    const el = box.current
    if (!el || !natural) return
    first.current = true
    setK(fitted())
    const watch = new ResizeObserver(() => { if (!chosen.current) setK(fitted()) })
    watch.observe(el)
    return () => watch.disconnect()
  }, [box, natural, fitted])

  // After a zoom: the point that was under the pointer (or the centre) stays where it was
  useLayoutEffect(() => {
    const el = box.current
    if (!el || k === null || !natural) return
    const zoom = focus.current
    focus.current = null
    if (zoom) {
      const next = zoomScroll({ left: el.scrollLeft, top: el.scrollTop }, zoom.at, zoom.from, k)
      el.scrollLeft = next.left
      el.scrollTop = next.top
    }
    const wide = natural.width * k > el.clientWidth + 1
    if (first.current && wide) {
      const origin = el.firstElementChild?.getBoundingClientRect()
      const nodes = [...el.querySelectorAll('svg g.node, svg g.cluster-label, svg .actor, svg .er.entityBox, svg g.classGroup')].map((node) => {
        const r = node.getBoundingClientRect()
        return { x: r.left + r.width / 2 - (origin?.left ?? 0), y: r.top + r.height / 2 - (origin?.top ?? 0) }
      })
      const start = busiest(nodes, { width: el.clientWidth, height: el.clientHeight }, { width: natural.width * k, height: natural.height * k })
      el.scrollLeft = start.left
      el.scrollTop = start.top
    }
    first.current = false
    setPans(wide || natural.height * k > el.clientHeight + 1)
  }, [box, k, natural])

  // A mouse drags the drawing; two fingers pinch it (full screen); Ctrl/Cmd + wheel (or any wheel, full screen) zooms
  useEffect(() => {
    const el = box.current
    if (!el) return
    const pointers = new Map<number, { x: number; y: number }>()
    let last: { x: number; y: number } | null = null
    let spread = 0
    const local = (e: { clientX: number; clientY: number }) => {
      const r = el.getBoundingClientRect()
      return { x: e.clientX - r.left, y: e.clientY - r.top }
    }
    const down = (e: PointerEvent) => {
      if (e.pointerType === 'mouse' && e.button !== 0) return
      if (e.pointerType === 'touch' && !pinch) return
      pointers.set(e.pointerId, { x: e.clientX, y: e.clientY })
      last = { x: e.clientX, y: e.clientY }
      if (pointers.size === 2) {
        const [a, b] = [...pointers.values()]
        spread = Math.hypot(a.x - b.x, a.y - b.y)
      }
      el.setPointerCapture?.(e.pointerId)
    }
    const move = (e: PointerEvent) => {
      if (!pointers.has(e.pointerId)) return
      pointers.set(e.pointerId, { x: e.clientX, y: e.clientY })
      if (pointers.size === 2) {
        const [a, b] = [...pointers.values()]
        const now = Math.hypot(a.x - b.x, a.y - b.y)
        if (spread > 0 && Math.abs(now - spread) > 2) {
          zoomBy(now / spread, local({ clientX: (a.x + b.x) / 2, clientY: (a.y + b.y) / 2 }))
          spread = now
        }
        return
      }
      if (!last) return
      el.scrollLeft -= e.clientX - last.x
      el.scrollTop -= e.clientY - last.y
      last = { x: e.clientX, y: e.clientY }
      el.dataset.dragging = ''
    }
    const up = (e: PointerEvent) => {
      pointers.delete(e.pointerId)
      if (pointers.size < 2) spread = 0
      if (pointers.size === 0) { last = null; delete el.dataset.dragging }
      else last = [...pointers.values()][0]
    }
    const onWheel = (e: WheelEvent) => {
      if (!wheel && !e.ctrlKey && !e.metaKey) return
      e.preventDefault()
      zoomBy(Math.exp(-e.deltaY * (e.deltaMode === 1 ? 0.05 : 0.0025)), local(e))
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.ctrlKey || e.metaKey || e.altKey) return
      if (e.key === '+' || e.key === '=') { e.preventDefault(); zoomBy(ZOOM.step) }
      else if (e.key === '-' || e.key === '_') { e.preventDefault(); zoomBy(1 / ZOOM.step) }
      else if (e.key === '0') { e.preventDefault(); fit() }
    }
    el.addEventListener('pointerdown', down)
    el.addEventListener('pointermove', move)
    el.addEventListener('pointerup', up)
    el.addEventListener('pointercancel', up)
    el.addEventListener('wheel', onWheel, { passive: false })
    el.addEventListener('keydown', onKey)
    return () => {
      el.removeEventListener('pointerdown', down)
      el.removeEventListener('pointermove', move)
      el.removeEventListener('pointerup', up)
      el.removeEventListener('pointercancel', up)
      el.removeEventListener('wheel', onWheel)
      el.removeEventListener('keydown', onKey)
    }
  }, [box, pinch, wheel, zoomBy, fit])

  return { k, zoomBy, fit, pans }
}
