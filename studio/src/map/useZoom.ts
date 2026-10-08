// Pan and zoom for a map drawn in an <svg> whose viewBox is the map's bounds: drag to pan, wheel or pinch to zoom
// around the pointer, buttons for in / out / fit, and centring on a component. The transform lives in the SVG's own
// units (a translate and a scale on the group that holds the map), so the geometry never mirrors with the page.
// About 120 lines of our own instead of d3-zoom: docs/adoption/studio-maps.md says why.
import { useCallback, useEffect, useRef, useState, type RefObject } from 'react'

export interface ZoomState { k: number; x: number; y: number }
const IDENTITY: ZoomState = { k: 1, x: 0, y: 0 }
const MIN_K = 0.7
const MAX_K = 8
const DRAG = 4 // px a pointer must move before a press becomes a drag (a shorter press stays a click on a dot)

function clampK(k: number) {
  return Math.min(MAX_K, Math.max(MIN_K, k))
}

/** A client point in the SVG's user units (the viewBox), whatever the element's size and aspect. */
function toUser(svg: SVGSVGElement, clientX: number, clientY: number): { x: number; y: number } {
  const ctm = svg.getScreenCTM()
  if (!ctm) return { x: clientX, y: clientY }
  const p = new DOMPoint(clientX, clientY).matrixTransform(ctm.inverse())
  return { x: p.x, y: p.y }
}

export function useZoom(svgRef: RefObject<SVGSVGElement | null>, enabled = true) {
  const [t, setT] = useState<ZoomState>(IDENTITY)
  const [dragging, setDragging] = useState(false)
  const tRef = useRef(t)
  tRef.current = t

  const zoomAround = useCallback((factor: number, ux: number, uy: number) => {
    setT((cur) => {
      const k = clampK(cur.k * factor)
      const f = k / cur.k
      return { k, x: ux - (ux - cur.x) * f, y: uy - (uy - cur.y) * f }
    })
  }, [])

  const centre = useCallback(() => {
    const vb = svgRef.current?.viewBox.baseVal
    return vb ? { x: vb.x + vb.width / 2, y: vb.y + vb.height / 2 } : { x: 0, y: 0 }
  }, [svgRef])

  const zoomBy = useCallback((factor: number) => { const c = centre(); zoomAround(factor, c.x, c.y) }, [centre, zoomAround])
  const fit = useCallback(() => setT(IDENTITY), [])

  /** Brings a world point to the middle of the view, zoomed in to at least `k`. */
  const centreOn = useCallback((wx: number, wy: number, minK = 1.6) => {
    const c = centre()
    setT((cur) => {
      const k = Math.max(cur.k, minK)
      return { k, x: c.x - wx * k, y: c.y - wy * k }
    })
  }, [centre])

  useEffect(() => {
    const svg = svgRef.current
    if (!svg || !enabled) return
    const pointers = new Map<number, { x: number; y: number }>()
    let start: { t: ZoomState; ux: number; uy: number; cx: number; cy: number; dist: number; mid: { x: number; y: number } } | null = null
    let moved = false

    const begin = () => {
      const pts = [...pointers.values()]
      const cx = pts.reduce((s, p) => s + p.x, 0) / pts.length
      const cy = pts.reduce((s, p) => s + p.y, 0) / pts.length
      const u = toUser(svg, cx, cy)
      const dist = pts.length > 1 ? Math.hypot(pts[0].x - pts[1].x, pts[0].y - pts[1].y) : 0
      start = { t: tRef.current, ux: u.x, uy: u.y, cx, cy, dist, mid: u }
    }
    const down = (e: PointerEvent) => {
      if (e.button !== 0 && e.pointerType === 'mouse') return
      pointers.set(e.pointerId, { x: e.clientX, y: e.clientY })
      moved = pointers.size > 1
      begin()
    }
    const move = (e: PointerEvent) => {
      if (!pointers.has(e.pointerId) || !start) return
      pointers.set(e.pointerId, { x: e.clientX, y: e.clientY })
      const pts = [...pointers.values()]
      const cx = pts.reduce((s, p) => s + p.x, 0) / pts.length
      const cy = pts.reduce((s, p) => s + p.y, 0) / pts.length
      if (!moved && Math.hypot(cx - start.cx, cy - start.cy) < DRAG) return
      if (!moved) { moved = true; svg.setPointerCapture(e.pointerId); setDragging(true) }
      const u = toUser(svg, cx, cy)
      const s = start
      if (pts.length > 1 && s.dist > 0) {
        const k = clampK(s.t.k * Math.hypot(pts[0].x - pts[1].x, pts[0].y - pts[1].y) / s.dist)
        // the world point under the first midpoint stays under the fingers' midpoint
        const wx = (s.mid.x - s.t.x) / s.t.k
        const wy = (s.mid.y - s.t.y) / s.t.k
        setT({ k, x: u.x - wx * k, y: u.y - wy * k })
      } else {
        setT({ k: s.t.k, x: s.t.x + (u.x - s.ux), y: s.t.y + (u.y - s.uy) })
      }
    }
    const up = (e: PointerEvent) => {
      if (!pointers.delete(e.pointerId)) return
      if (svg.hasPointerCapture(e.pointerId)) svg.releasePointerCapture(e.pointerId)
      if (pointers.size) begin()
      else { start = null; setDragging(false) }
    }
    // a drag must not end in a click on the dot under the pointer
    const click = (e: MouseEvent) => { if (moved) { e.stopPropagation(); e.preventDefault(); moved = false } }
    const wheel = (e: WheelEvent) => {
      e.preventDefault()
      const u = toUser(svg, e.clientX, e.clientY)
      zoomAround(Math.exp(-e.deltaY * (e.ctrlKey ? 0.01 : 0.0018)), u.x, u.y)
    }
    svg.addEventListener('pointerdown', down)
    svg.addEventListener('pointermove', move)
    svg.addEventListener('pointerup', up)
    svg.addEventListener('pointercancel', up)
    svg.addEventListener('click', click, true)
    svg.addEventListener('wheel', wheel, { passive: false })
    return () => {
      svg.removeEventListener('pointerdown', down)
      svg.removeEventListener('pointermove', move)
      svg.removeEventListener('pointerup', up)
      svg.removeEventListener('pointercancel', up)
      svg.removeEventListener('click', click, true)
      svg.removeEventListener('wheel', wheel)
    }
  }, [svgRef, enabled, zoomAround])

  return { t, dragging, zoomBy, fit, centreOn, setT }
}

/** The part of the world the view shows: for the minimap's frame. */
export function visibleWorld(t: ZoomState, box: [number, number, number, number]): [number, number, number, number] {
  return [(box[0] - t.x) / t.k, (box[1] - t.y) / t.k, box[2] / t.k, box[3] / t.k]
}
