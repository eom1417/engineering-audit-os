// The branches EAOS handed over and that wait for the person's word: Accept merges one (behind its confirm sheet, the
// same as a run's page), Undo throws it away. At the top of Fixes, its one home; Waiting for you links here.
import { useState } from 'react'
import { Button } from '../../components/Button'
import { Panel, Section } from '../../components/Panel'
import { useCmdWords } from '../../command/words'
import { useActions } from '../../data/actions/store'
import type { Run } from '../../data/actions/types'
import { useAwaitingApproval } from '../../shell/waiting'
import { RunRow } from '../runs/parts'
import { DecideSheet } from '../runs/RunPage'
import css from './change.module.css'

export function Approvals() {
  const w = useCmdWords()
  const actions = useActions()
  const awaiting = useAwaitingApproval()
  const [deciding, setDeciding] = useState<{ run: Run; op: 'accept' | 'undo' } | null>(null)
  if (!awaiting.length) return null
  return (
    <Section title={w('awaitingApproval')} count={awaiting.length} id="approvals">
      <Panel>
        <ul>{awaiting.map((run) => (
          <li key={run.id} className={css.approval} data-approval={run.id}>
            <RunRow run={run} />
            <span className={css.approvalTools}>
              <Button variant="primary" icon="check" onPress={() => setDeciding({ run, op: 'accept' })}>{w('acceptBranch')}</Button>
              <Button variant="secondary" icon="x" onPress={() => setDeciding({ run, op: 'undo' })}>{w('undoBranch')}</Button>
            </span>
          </li>
        ))}</ul>
      </Panel>
      {deciding && <DecideSheet run={deciding.run} op={deciding.op} onClose={() => setDeciding(null)}
        onDone={(next) => { actions.patch(next.id, next); void actions.refresh() }} />}
    </Section>
  )
}
