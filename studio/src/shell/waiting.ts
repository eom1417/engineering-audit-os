// The one "waiting for you" count: the report's waiting questions less the ones already answered in the live Studio.
// Home's link and the top bar's Waiting for you read it, so they never disagree (the incident: Home 41, badge 40). The
// branches waiting for approval are counted beside it.
import { useMemo } from 'react'
import { useActionsMaybe } from '../data/actions/store'
import type { ReportDecision, Run } from '../data/actions/types'
import type { Decision, StudioData } from '../data/types'

export function waitingDecisions(all: Decision[], answered: ReportDecision[]): Decision[] {
  const done = new Set(answered.filter((r) => r.response).map((r) => r.id))
  return all.filter((d) => d.state === 'waiting' && !done.has(d.id))
}

export function useWaitingDecisions(data: StudioData | null | undefined): Decision[] {
  const answered = useActionsMaybe()?.decisions
  return useMemo(() => waitingDecisions(data?.decisions?.decisions ?? [], answered ?? []), [data, answered])
}

/** A run whose branch waits for the person's Accept or Undo: it ended well, handed a branch over, and nobody decided. */
export const awaitsApproval = (run: Run) => run.state === 'done' && Boolean(run.result?.branch) && !run.outcome

export function useAwaitingApproval(): Run[] {
  const runs = useActionsMaybe()?.runs
  return useMemo(() => (runs ?? []).filter(awaitsApproval), [runs])
}
