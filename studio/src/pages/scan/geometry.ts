// Where each stage of the check is drawn: the layer and order the server computed with the same pinned layered layout
// as the other maps (eaos/studio/pipeline.py layout: longest path, barycentre), left to right on a wide canvas and top
// to bottom on a tall one. Nothing here decides an order: it only turns (layer, order) into points and links.
import type { ScanStage } from '../../data/scan'

export const NODE_W = 164
export const NODE_H = 58
const STEP_X = 214        // one layer to the next, left to right
const STEP_Y = 80         // one place to the next inside a layer
const DOWN_X = 180        // one place to the next, top to bottom
const DOWN_Y = 112        // one layer to the next, top to bottom
const PAD = 24

export interface At { x: number; y: number }
export interface Layout { at: Map<string, At>; across: boolean; width: number; height: number }
export interface Link { from: string; to: string; d: string }

export function place(stages: Pick<ScanStage, 'name' | 'layer' | 'order'>[], across: boolean): Layout {
  const at = new Map<string, At>()
  let layers = 0
  let rows = 0
  for (const { name, layer = 0, order = 0 } of stages) {
    layers = Math.max(layers, layer + 1)
    rows = Math.max(rows, order + 1)
    at.set(name, across ? { x: PAD + layer * STEP_X, y: PAD + order * STEP_Y } : { x: PAD + order * DOWN_X, y: PAD + layer * DOWN_Y })
  }
  const width = PAD * 2 + NODE_W + Math.max(0, (across ? layers : rows) - 1) * (across ? STEP_X : DOWN_X)
  const height = PAD * 2 + NODE_H + Math.max(0, (across ? rows : layers) - 1) * (across ? STEP_Y : DOWN_Y)
  return { at, across, width, height }
}

/** One curve per declared requirement, from the stage it needs to the stage that needs it. */
export function links(stages: Pick<ScanStage, 'name' | 'requires'>[], layout: Layout): Link[] {
  const out: Link[] = []
  for (const s of stages) {
    const b = layout.at.get(s.name)
    for (const need of s.requires) {
      const a = layout.at.get(need)
      if (a && b) out.push({ from: need, to: s.name, d: curve(layout.across, a, b) })
    }
  }
  return out
}

function curve(across: boolean, a: At, b: At): string {
  if (across) {
    const [x1, y1, x2, y2] = [a.x + NODE_W, a.y + NODE_H / 2, b.x, b.y + NODE_H / 2]
    if (x2 > x1 + 4) { const m = (x1 + x2) / 2; return `M${x1},${y1} C${m},${y1} ${m},${y2} ${x2},${y2}` }
    const bow = Math.max(a.y, b.y) + NODE_H + 18
    return `M${a.x + NODE_W / 2},${a.y + NODE_H} C${a.x + NODE_W / 2},${bow} ${b.x + NODE_W / 2},${bow} ${b.x + NODE_W / 2},${b.y + NODE_H}`
  }
  const [x1, y1, x2, y2] = [a.x + NODE_W / 2, a.y + NODE_H, b.x + NODE_W / 2, b.y]
  if (y2 > y1 + 4) { const m = (y1 + y2) / 2; return `M${x1},${y1} C${x1},${m} ${x2},${m} ${x2},${y2}` }
  const bow = Math.max(a.x, b.x) + NODE_W + 18
  return `M${a.x + NODE_W},${a.y + NODE_H / 2} C${bow},${a.y + NODE_H / 2} ${bow},${b.y + NODE_H / 2} ${b.x + NODE_W},${b.y + NODE_H / 2}`
}

/** The first view: the whole map when it reads at that size (`whole`: the smallest zoom that still counts), else a
 * readable zoom centred on `focus`. */
export function firstView(layout: Layout, box: { w: number; h: number }, focus: At | undefined, readable = 0.82, whole = 0.7): { k: number; x: number; y: number } {
  if (!box.w || !box.h) return { k: 1, x: 0, y: 0 }
  const k = Math.min(1, (box.w - 16) / layout.width, (box.h - 16) / layout.height)
  if (k >= whole) return { k, x: Math.max(8, (box.w - layout.width * k) / 2), y: Math.max(8, (box.h - layout.height * k) / 2) }
  return centred(layout, box, focus, readable)
}

/** A view at zoom `k` with `focus` (a stage's corner) in the middle, kept inside the drawing's bounds. */
export function centred(layout: Layout, box: { w: number; h: number }, focus: At | undefined, k: number): { k: number; x: number; y: number } {
  const fx = (focus?.x ?? 0) + NODE_W / 2
  const fy = (focus?.y ?? 0) + NODE_H / 2
  const clamp = (v: number, size: number, world: number) => (world * k <= size ? (size - world * k) / 2 : Math.min(8, Math.max(size - world * k - 8, v)))
  return { k, x: clamp(box.w / 2 - fx * k, box.w, layout.width), y: clamp(box.h / 2 - fy * k, box.h, layout.height) }
}
