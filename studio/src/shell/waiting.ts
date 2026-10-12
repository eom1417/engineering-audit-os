// The one "waiting for you" count: the report's waiting questions less the ones already answered in the live Studio.
// Home's list, the sidebar and the tab badge all read it, so they never disagree (the incident: Home 41, badge 40).
import { useMemo } from 'react'
import { useActionsMaybe } from '../data/actions/store'
import type { ReportDecision } from '../data/actions/types'
import type { Decision, StudioData } from '../data/types'

export function waitingDecisions(all: Decision[], answered: ReportDecision[]): Decision[] {
  const done = new Set(answered.filter((r) => r.response).map((r) => r.id))
  return all.filter((d) => d.state === 'waiting' && !done.has(d.id))
}

export function useWaitingDecisions(data: StudioData | null | undefined): Decision[] {
  const answered = useActionsMaybe()?.decisions
  return useMemo(() => waitingDecisions(data?.decisions?.decisions ?? [], answered ?? []), [data, answered])
}
