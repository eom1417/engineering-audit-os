// The one data interface the pages read through: a snapshot (the data scripts beside the Studio on disk, opened from
// a file or any static server) or the live server of `eaos studio`. Both give the same StudioData from the same
// files, so a page shows the same thing either way; only the live one changes by itself.
import { load, type Loaded } from './load'
import { liveToken, loadLive, subscribe, type LiveEvent, type LiveStatus } from './live'
import type { StudioData } from './types'

export type Mode = 'live' | 'snapshot'

export interface DataSource {
  mode: Mode
  /** The report; with `previous`, sections whose sha256 did not change are kept as they are. */
  load(previous?: StudioData | null): Promise<Loaded>
  /** Follow what changes (live only); `onEvent(null)` means reload everything. Returns the stop function. */
  follow?(onEvent: (event: LiveEvent | null) => void, onStatus: (status: LiveStatus) => void): () => void
}

export const snapshotSource: DataSource = { mode: 'snapshot', load: () => load() }

export function liveSource(token: string): DataSource {
  return {
    mode: 'live',
    load: (previous) => loadLive(token, previous),
    follow: (onEvent, onStatus) => subscribe(token, onEvent, onStatus),
  }
}

/** Live when this tab holds the token of the server that opened it; otherwise the snapshot. */
export function pickSource(): DataSource {
  const token = liveToken()
  return token ? liveSource(token) : snapshotSource
}
