// What the first view does not draw waits for it: a section read when the browser is idle (data/context.tsx
// useSections), and the frame's parts that open on demand (the palette, the command centre's sheets), each its own
// chunk (vite.config.ts classicChunks), read once the report is drawn and drawn from the first time they open.
import { useState } from 'react'

/** Runs `task` once the browser is idle (after the next frame where requestIdleCallback is missing); returns a cancel. */
export function whenIdle(task: () => void, timeout = 2000): () => void {
  if (window.requestIdleCallback) {
    const id = window.requestIdleCallback(task, { timeout })
    return () => window.cancelIdleCallback(id)
  }
  const id = window.setTimeout(task, 50)
  return () => window.clearTimeout(id)
}

/** True from the first time `open` is true: a part that has opened stays drawn, so it can close as it opened. */
export function useOpenedOnce(open: boolean): boolean {
  const [opened, setOpened] = useState(open)
  if (open && !opened) setOpened(true)
  return opened || open
}
