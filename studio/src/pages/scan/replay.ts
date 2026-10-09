// "Replay the last check": the check's real progress file (run-progress.jsonl, read through /api/report-file) played
// again at 10x or 30x through the same fold, so the map moves exactly as it did, faster. The places on the map are the
// live check's (the same declared stages); the timers count from each line's own time.
import { useEffect, useRef, useState } from 'react'
import { liveToken } from '../../data/live'
import { apply, emptyProgress, type ProgressRow, type ScanProgress } from '../../data/scan'

/** `id` tells one playing from the next: the map starts over for each. */
export interface Replay { id: number; speed: number; progress: ScanProgress; skew: number }

function rowsOf(text: string): ProgressRow[] {
  const rows: ProgressRow[] = []
  for (const line of text.split('\n')) {
    try { const row = JSON.parse(line); if (row && typeof row === 'object') rows.push(row) } catch { /* a line still being written */ }
  }
  return rows
}

export function useReplay(live: ScanProgress | undefined) {
  const [replay, setReplay] = useState<Replay | null>(null)
  const timer = useRef(0)
  const plays = useRef(0)
  useEffect(() => () => window.clearTimeout(timer.current), [])
  const stop = () => { window.clearTimeout(timer.current); setReplay(null) }

  async function start(speed: number) {
    window.clearTimeout(timer.current)
    const answer = await fetch('/api/report-file?path=run-progress.jsonl', { headers: { 'X-EAOS-Token': liveToken() ?? '' }, cache: 'no-store', credentials: 'same-origin' })
    const rows = answer.ok ? rowsOf(await answer.text()) : []
    if (!rows.length) return
    const places = new Map((live?.stages ?? []).map((s) => [s.name, s]))
    let state = emptyProgress()
    const id = ++plays.current
    const play = (i: number) => {
      const row = rows[i]
      state = apply(state, row)
      if (row.event === 'run.started') state = { ...state, stages: state.stages.map((s) => ({ ...s, layer: places.get(s.name)?.layer, order: places.get(s.name)?.order })) }
      setReplay({ id, speed, progress: state, skew: Date.parse(row.at ?? '') - Date.now() || 0 })
      if (i + 1 < rows.length) timer.current = window.setTimeout(() => play(i + 1), Math.max(0, Date.parse(rows[i + 1].at ?? '') - Date.parse(row.at ?? '')) / speed || 0)
    }
    play(0)
  }
  return { replay, start, stop }
}
