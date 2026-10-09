// Live timers: the seconds since `since` by the server's clock, each redrawn once a second on its own, so the map and
// the page around them are not drawn again for them. With `until` the time is fixed and nothing ticks.
import { useEffect, useState } from 'react'
import { clock, secondsSince } from '../../data/scan'

function useSeconds(since: string | null, skew: number, until?: string | null): number | null {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    if (until || !since) return
    const timer = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(timer)
  }, [since, until])
  if (until && since) return Math.max(0, (Date.parse(until) - Date.parse(since)) / 1000)
  return secondsSince(since, skew, now)
}

/** Inside the SVG map. */
export function Ticker({ since, skew, until }: { since: string | null; skew: number; until?: string | null }) {
  return <tspan data-ticker="">{clock(useSeconds(since, skew, until))}</tspan>
}

/** In the page's HTML. */
export function TickerText({ since, skew, until }: { since: string | null; skew: number; until?: string | null }) {
  return <bdi dir="ltr" data-ticker="">{clock(useSeconds(since, skew, until))}</bdi>
}
