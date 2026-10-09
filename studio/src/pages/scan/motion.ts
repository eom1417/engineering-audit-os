// What moves on the live map, and when (docs/STUDIO.md, the live map's motion). The page's state is always exact; the
// map draws each stage in the state it has *shown* so far. Every change of a stage's state the lines brought is queued
// and shown at least SLOT_MS after the one before, so a stage that lasted 50 ms is still seen glowing; the stages that
// never ran (not asked, not reached, unavailable before they started) fade in together with the change before them, so
// a stopped run does not play its twenty endings one by one. A stage shown ending ok sends a light along each link to
// the stages it opened (at most MAX_LIGHTS in flight). A stage shown changing is `fresh` for a moment, which plays its
// one-off pulse or fade. Nothing here starts a stage: only a line does.
import { ENDED, opened, type ScanProgress, type StageState } from '../../data/scan'

export const SLOT_MS = 400
export const LIGHT_MS = 700
export const FRESH_MS = 600
export const MAX_LIGHTS = 3
const NEVER_RAN: StageState[] = ['skipped', 'not_reached', 'unavailable']

/** One change of a stage's state, with the time of the line that made it. */
export interface Change { stage: string; state: StageState; at: string | null }
export interface Light { from: string; to: string; at: string | null; until: number }

export interface Motion {
  run: string | null
  /** The exact state of each stage, as last seen */
  seen: Record<string, StageState>
  /** The state each stage is drawn in */
  shown: Record<string, StageState>
  queue: Change[]
  lights: Light[]
  fresh: Record<string, number>
  last: number
}

const states = (progress: ScanProgress) => Object.fromEntries(progress.stages.map((s) => [s.name, s.state]))

/** Nothing queued: the map shows the state as it is (a new run, the first read, reduced motion). */
export function still(progress: ScanProgress): Motion {
  return { run: progress.run, seen: states(progress), shown: states(progress), queue: [], lights: [], fresh: {}, last: 0 }
}

/** The changes from the states last seen to `progress`, in the order of their lines. A stage that started and ended
 * between two looks gives both changes. */
export function changes(seen: Record<string, StageState>, progress: ScanProgress): Change[] {
  const out: Change[] = []
  for (const s of progress.stages) {
    const was = seen[s.name]
    if (was === undefined || was === s.state) continue
    if (was === 'waiting' && ENDED.includes(s.state) && s.started_at) out.push({ stage: s.name, state: 'running', at: s.started_at })
    out.push({ stage: s.name, state: s.state, at: s.state === 'running' ? s.started_at : s.ended_at })
  }
  return out.sort((a, b) => (a.at ?? '').localeCompare(b.at ?? ''))
}

/** A new exact state: its changes join the queue (a new run starts over). */
export function follow(motion: Motion, progress: ScanProgress): Motion {
  if (progress.run !== motion.run) return still(progress)
  const queued = changes(motion.seen, progress)
  return queued.length ? { ...motion, seen: states(progress), queue: [...motion.queue, ...queued] } : motion
}

/** What is due at `now`: lights and pulses that are over leave, and the next change is shown, with the stages that
 * never ran right behind it. */
export function release(motion: Motion, progress: ScanProgress, now: number): Motion {
  const next = { ...motion, shown: { ...motion.shown }, queue: [...motion.queue], fresh: { ...motion.fresh },
    lights: motion.lights.filter((light) => light.until > now) }
  for (const [stage, until] of Object.entries(next.fresh)) if (until <= now) delete next.fresh[stage]
  if (!next.queue.length || now - next.last < SLOT_MS) return next
  do show(next, progress, next.queue.shift() as Change, now)
  while (next.queue.length && NEVER_RAN.includes(next.queue[0].state) && next.shown[next.queue[0].stage] === 'waiting')
  return next
}

function show(motion: Motion, progress: ScanProgress, change: Change, now: number) {
  motion.shown[change.stage] = change.state
  motion.fresh[change.stage] = now + FRESH_MS
  motion.last = now
  if (change.state === 'ok') motion.lights.push(...lightsFrom(motion, progress, change, now))
}

function lightsFrom(motion: Motion, progress: ScanProgress, change: Change, now: number): Light[] {
  const drawn = { ...progress, stages: progress.stages.map((s) => ({ ...s, state: motion.shown[s.name] ?? s.state })) }
  const room = Math.max(0, MAX_LIGHTS - motion.lights.length)
  return opened(drawn, change.stage).slice(0, room).map((to) => ({ from: change.stage, to, at: change.at, until: now + LIGHT_MS }))
}

/** Milliseconds until something is due, or null when nothing waits. */
export function nextDue(motion: Motion, now: number): number | null {
  const times = [...motion.lights.map((l) => l.until), ...Object.values(motion.fresh)]
  if (motion.queue.length) times.push(motion.last + SLOT_MS)
  return times.length ? Math.max(0, Math.min(...times) - now) : null
}
