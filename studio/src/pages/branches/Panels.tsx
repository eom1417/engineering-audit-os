// The guarded merge and deletion of a branch (#/branches): each loads its preview, shows what would happen and why it
// may be blocked, and confirms only that preview.
import { useCallback, useEffect, useState } from 'react'
import { Button } from '../../components/Button'
import { Props } from '../../components/Panel'
import { SheetSub } from '../../components/Sheet'
import { ActionError, type BranchRow, type DeletePreview, type MergePreview, type Run } from '../../data/actions/types'
import { usePrefs } from '../../i18n/prefs'
import { Id, N, When } from '../../i18n/text'
import { useBranchLive } from '../../branches/live'
import { useBranchWords } from '../../branches/words'
import css from '../../branches/branches.module.css'
import { Reasons, Subject } from './parts'

export function MergePanel({ row, target, onDone }: { row: BranchRow; target: string | null; onDone: (run: Run) => void }) {
  const w = useBranchWords()
  const { api } = useBranchLive()
  const [preview, setPreview] = useState<MergePreview | null>(null)
  const [ack, setAck] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [stale, setStale] = useState(false)
  const load = useCallback(async () => {
    if (!api) return
    setError(null)
    setAck(false)                       // an acknowledgement belongs to the preview it was given for
    try { setPreview(await api.previewMerge(row.name, target)) } catch (problem) { setError(problem instanceof Error ? problem.message : String(problem)) }
  }, [api, row.name, target])
  useEffect(() => { void load() }, [load])
  async function confirm() {
    if (!api || !preview) return
    setBusy(true); setError(null)
    try {
      const done = await api.merge(preview, ack)
      onDone(done.run)
    } catch (problem) {
      if (problem instanceof ActionError && problem.needs === 'refresh') { setStale(true); await load() }
      else setError(problem instanceof Error ? problem.message : String(problem))
    } finally { setBusy(false) }
  }
  if (!preview) return error ? <p role="alert" className={css.error}>{error}</p> : <p className={css.muted}>…</p>
  return (
    <div className={css.panel} data-merge-preview={preview.blocked.length ? 'blocked' : 'ready'}>
      <SheetSub>{w('mergeInto', { s: preview.source, t: preview.target })}</SheetSub>
      {stale && <p role="alert" className={css.note}>{w('stale')}</p>}
      <p>{w('mergePath', { p: preview.path === 'accept' ? w('pathAccept') : w('pathTransaction') })}{preview.fast_forward ? ` · ${w('fastForward')}` : ''}</p>
      <Props rows={[
        [preview.source, <Id value={preview.source_head.slice(0, 7)} />],
        [preview.target, <Id value={preview.target_head.slice(0, 7)} />],
        [w('commitsAhead', { b: preview.target }), <N value={preview.commits.length} />],
        [w('filesChanged'), <N value={preview.files.length} />],
        [w('checks'), preview.checks.status === 'passed' ? w('checksPassed', { c: preview.checks.commit.slice(0, 12) }) : preview.checks.status === 'failed' ? w('checksFailed', { c: preview.checks.commit.slice(0, 12) }) : w('checksNone')],
      ]} />
      {preview.files.length > 0 && <ul className={css.files}>{preview.files.slice(0, 30).map((f) => <li key={f.path}><span className={css.muted}>{f.status}</span> <Id value={f.path} /></li>)}</ul>}
      {preview.conflicts.length > 0 && <>
        <p className={css.note}>{w('conflicts', { n: preview.conflicts.length })}</p>
        <ul className={css.files}>{preview.conflicts.map((f) => <li key={f}><Id value={f} /></li>)}</ul>
        <ResolutionButton source={preview.source} target={preview.target} onDone={onDone} />
      </>}
      <Reasons reasons={preview.blocked.filter((r) => r.code !== 'conflict')} />
      {!preview.blocked.length && preview.needs_unchecked_ack && (
        <label className={css.check}><input type="checkbox" checked={ack} onChange={(e) => setAck(e.target.checked)} />{w('uncheckedAck')}</label>
      )}
      {error && <p role="alert" className={css.error}>{error}</p>}
      {!preview.blocked.length && <Button variant="primary" icon="check" busy={busy} isDisabled={preview.needs_unchecked_ack && !ack} onPress={confirm}>{w('confirmMerge')}</Button>}
    </div>
  )
}

function ResolutionButton({ source, target, onDone }: { source: string; target: string; onDone: (run: Run) => void }) {
  const w = useBranchWords()
  const { api } = useBranchLive()
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  return <>
    <Button variant="secondary" icon="explain" busy={busy} onPress={async () => {
      if (!api) return
      setBusy(true); setError(null)
      try { onDone((await api.proposeResolution(source, target)).run) } catch (problem) { setError(problem instanceof Error ? problem.message : String(problem)) } finally { setBusy(false) }
    }}>{w('proposeResolution')}</Button>
    {error && <p role="alert" className={css.error}>{error}</p>}
  </>
}

export function DeletePanel({ row, onDone }: { row: BranchRow; onDone: (run: Run) => void }) {
  const w = useBranchWords()
  const { lang } = usePrefs()
  const { api } = useBranchLive()
  const where = row.kind
  const [preview, setPreview] = useState<DeletePreview | null>(null)
  const [second, setSecond] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const load = useCallback(async () => {
    if (!api) return
    setError(null)
    try { setPreview(await api.previewDelete(row.name, where, row.remote)) } catch (problem) { setError(problem instanceof Error ? problem.message : String(problem)) }
  }, [api, row.name, row.remote, where])
  useEffect(() => { void load() }, [load])
  async function confirm() {
    if (!api || !preview) return
    setBusy(true); setError(null)
    try { onDone((await api.remove(preview, second)).run) } catch (problem) {
      if (problem instanceof ActionError && problem.needs === 'refresh') await load()
      setError(problem instanceof Error ? problem.message : String(problem))
    } finally { setBusy(false) }
  }
  if (!preview) return error ? <p role="alert" className={css.error}>{error}</p> : <p className={css.muted}>…</p>
  return (
    <div className={css.panel} data-delete-preview={preview.blocked.length ? 'blocked' : preview.unmerged ? 'unmerged' : 'merged'}>
      <SheetSub>{where === 'remote' ? w('deleteRemote', { r: row.remote ?? '' }) : w('deletePreview')}</SheetSub>
      {where === 'remote' ? <>
        <p>{w('deleteRemoteLead')}</p>
        {preview.local_kept && <p>{w('localKept')}</p>}
        {preview.as_of && <p className={css.muted}>{w('remoteAsOf', { d: '' })}<When iso={preview.as_of} /></p>}
      </> : <>
        {preview.unmerged
          ? <p className={css.note}>{w('deleteUnmerged', { n: preview.lost_commits?.length ?? 0 })}</p>
          : <p>{w('deleteMerged', { b: (preview.merged_into ?? []).join(', ') || '—' })}</p>}
        {preview.unmerged && <ul className={css.files}>{(preview.lost_commits ?? []).map((c) => <li key={c.commit}><Id value={c.commit.slice(0, 7)} /> <Subject text={c.subject} /></li>)}</ul>}
        {preview.worktree && <p className={css.note}>{w('worktreeGoes', { p: preview.worktree })}</p>}
        <p>{w('remoteKept')}</p>
      </>}
      {preview.whose && <p className={css.muted} data-whose={preview.whose.code}>{preview.whose[lang]}</p>}
      <Reasons reasons={preview.blocked} />
      {preview.unmerged && !preview.blocked.length && (
        <label className={css.check}><input type="checkbox" checked={second} onChange={(e) => setSecond(e.target.checked)} />{w('confirmUnmerged')}</label>
      )}
      {error && <p role="alert" className={css.error}>{error}</p>}
      {!preview.blocked.length && <Button variant="primary" icon="opDelete" busy={busy} isDisabled={Boolean(preview.unmerged) && !second} onPress={confirm}>{w('confirmDelete')}</Button>}
    </div>
  )
}
