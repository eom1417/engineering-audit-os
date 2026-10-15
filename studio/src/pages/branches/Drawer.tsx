// One branch's drawer (#/branches): what is known of it, its changes and diff, its runs, and its commands: analyse it,
// and the guarded merge and deletion.
import { useEffect, useState, type ReactNode } from 'react'
import { Button } from '../../components/Button'
import { Props } from '../../components/Panel'
import { Sheet, SheetSub } from '../../components/Sheet'
import { useActions } from '../../data/actions/store'
import type { BranchDetail, BranchRow, Run } from '../../data/actions/types'
import { labelOf } from '../../data/actions/derive'
import { usePrefs } from '../../i18n/prefs'
import { Id, N, When } from '../../i18n/text'
import { useBranchLive } from '../../branches/live'
import { useSelect } from '../../branches/Switcher'
import { RescanStatus, SelectError } from '../../branches/ScanSheet'
import { useBranchWords } from '../../branches/words'
import css from '../../branches/branches.module.css'
import { DeletePanel, MergePanel } from './Panels'
import { Badges, Reasons, RunLinks, Subject, WorktreeNote } from './parts'

export function Drawer({ row, base, onClose, onChanged }: { row: BranchRow; base: string | null; onClose: () => void; onChanged: () => void }) {
  const w = useBranchWords()
  const { lang } = usePrefs()
  const { api } = useBranchLive()
  const [detail, setDetail] = useState<BranchDetail | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [panel, setPanel] = useState<'merge' | 'delete' | null>(null)
  const [more, setMore] = useState(false)
  const [result, setResult] = useState<Run | null>(null)
  const select = useSelect()
  const actions = useActions()
  useEffect(() => {
    if (!api) return
    let on = true
    api.detail(row.name, row.kind, row.remote, base).then((d) => { if (on) setDetail(d) }, (problem) => { if (on) setError(problem instanceof Error ? problem.message : String(problem)) })
    return () => { on = false }
  }, [api, row.name, row.kind, row.remote, base, result])
  const done = (run: Run) => { setResult(run); setPanel(null); onChanged(); void actions.refresh() }
  const followed = result ? actions.runs.find((r) => r.id === result.id) ?? result : null
  const commands = detail?.commands ?? {}
  return (
    <Sheet isOpen onOpenChange={(open) => { if (!open) onClose() }} title={w('details', { b: row.name })}>
      <div className={[css.tall, css.drawerBody].join(' ')}>
      <Badges row={row} />
      {error && <p role="alert" className={css.error}>{error}</p>}
      {followed && <RescanStatus run={followed} />}
      {select.scan && <RescanStatus run={select.scan} />}
      <SelectError error={select.error} />
      {detail && <>
        <DetailProps row={row} detail={detail} />
        {row.worktree && <WorktreeNote row={row} />}
        <ChangesList detail={detail} />
        {detail.runs.length > 0 && <><SheetSub>{w('linkedRuns')}</SheetSub><RunLinks runs={detail.runs} all /></>}
        <SheetSub>{w('commands')}</SheetSub>
        <div className={css.commandList}>
          {row.kind === 'local' && !row.roles.includes('analysis') && <div className={css.command}>
            <Button variant="secondary" busy={select.busy === row.name} onPress={() => void select.choose(row.name, false, row.tip)}>{w('useForAnalysis')}</Button>
            <Button variant="secondary" busy={select.busy === row.name + ':scan'} onPress={() => void select.choose(row.name, true, row.tip)}>{w('useForAnalysisScan')}</Button>
          </div>}
          {commands.merge && <div className={css.command}>
            <Button variant="secondary" icon="opMerge" onPress={() => setPanel(panel === 'merge' ? null : 'merge')} aria-expanded={panel === 'merge'}>{w('mergePreview')}</Button>
            {!commands.merge.available && panel !== 'merge' && <Reasons reasons={commands.merge.blocked} />}
          </div>}
          {panel === 'merge' && <MergePanel row={row} target={detail.destination.recommended} onDone={done} />}
          {(commands.delete_local || commands.delete_remote) && !more && panel !== 'delete' && (
            <Button variant="ghost" icon="chevronDown" onPress={() => setMore(true)} aria-expanded={false}>{w('more')}</Button>
          )}
          {(commands.delete_local || commands.delete_remote) && (more || panel === 'delete') && <div className={css.command}>
            <Button variant="secondary" icon="opDelete" onPress={() => setPanel(panel === 'delete' ? null : 'delete')} aria-expanded={panel === 'delete'}>
              {row.kind === 'remote' ? w('deleteRemote', { r: row.remote ?? '' }) : w('deleteLocal')}</Button>
            {!(commands.delete_local ?? commands.delete_remote).available && panel !== 'delete' && <Reasons reasons={(commands.delete_local ?? commands.delete_remote).blocked} />}
          </div>}
          {panel === 'delete' && <DeletePanel row={row} onDone={done} />}
        </div>
      </>}
      {!detail && !error && <p className={css.muted}>…</p>}
      <span className="sr" aria-live="polite">{followed ? labelOf(followed.label, lang) : ''}</span>
      </div>
    </Sheet>
  )
}

/** What is known, in plain words: a short commit, the subject in its own direction, and no row for what nobody knows. */
function DetailProps({ row, detail }: { row: BranchRow; detail: BranchDetail }) {
  const w = useBranchWords()
  return (
    <Props rows={[
      ['Commit', <Id value={row.tip.slice(0, 7)} />],
      [w('lastCommit'), row.last_commit ? <><When iso={row.last_commit} /> · <Subject text={row.subject} /></> : '—'],
      ...(detail.base && detail.base !== row.name ? [[w('base'), <Id value={detail.base} />] as [string, ReactNode]] : []),
      ...(detail.lineage ? [[w('lineage'), <>{detail.lineage.parent ?? '—'}{detail.lineage.parent_commit ? <> @ <Id value={detail.lineage.parent_commit.slice(0, 7)} /></> : null}{detail.lineage.recorded_at ? <> · <When iso={detail.lineage.recorded_at} /></> : null}</>] as [string, ReactNode]] : []),
      ...(detail.checks.status !== 'not_recorded' ? [[w('checks'), detail.checks.status === 'passed' ? w('checksPassed', { c: detail.checks.commit.slice(0, 7) }) : w('checksFailed', { c: detail.checks.commit.slice(0, 7) })] as [string, ReactNode]] : []),
      ...(detail.destination.recommended || detail.destination.confirmed ? [[w('destination'), detail.destination.confirmed ? w('confirmedInto', { b: detail.destination.confirmed.branch }) : w('recommended', { b: detail.destination.recommended ?? '' })] as [string, ReactNode]] : []),
    ]} />
  )
}

/** The commits ahead of the base, the files changed and, on request, the diff. */
function ChangesList({ detail }: { detail: BranchDetail }) {
  const w = useBranchWords()
  const [diff, setDiff] = useState(false)
  return (
    <>
      {detail.commits.length > 0 && <>
        <SheetSub>{w('commitsAhead', { b: detail.base ?? '' })} (<N value={detail.commits.length} />)</SheetSub>
        <ul className={css.files}>{detail.commits.map((c) => <li key={c.commit}><Id value={c.commit.slice(0, 7)} /> <Subject text={c.subject} /> <span className={css.muted}>· {c.author}</span></li>)}</ul>
      </>}
      {detail.files.length > 0 && <>
        <SheetSub>{w('filesChanged')} (<N value={detail.files_total} />)</SheetSub>
        <ul className={css.files}>{detail.files.slice(0, 40).map((f) => <li key={f.path}><span className={css.muted}>{f.status}</span> <Id value={f.path} /></li>)}</ul>
        <Button variant="ghost" onPress={() => setDiff(!diff)} aria-expanded={diff}>{diff ? w('hideDiff') : w('showDiff')}</Button>
        {diff && <>{detail.diff_cut && <p className={css.muted}>{w('diffCut')}</p>}<pre className={css.diff} tabIndex={0} dir="ltr">{detail.diff}</pre></>}
      </>}
    </>
  )
}
