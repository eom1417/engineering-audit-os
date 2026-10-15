// Cleaning up (#/branches): the merged branches and the old worktrees that may go, the ones that stay and why, and the
// run that removes them, each branch restorable.
import { useCallback, useEffect, useState } from 'react'
import { Button } from '../../components/Button'
import { Sheet, SheetLead, SheetSub } from '../../components/Sheet'
import { ActionError, type CleanupPreview, type Run } from '../../data/actions/types'
import { usePrefs } from '../../i18n/prefs'
import { Id } from '../../i18n/text'
import { useBranchLive } from '../../branches/live'
import { RescanStatus } from '../../branches/ScanSheet'
import { useBranchWords } from '../../branches/words'
import css from '../../branches/branches.module.css'
import { Reasons } from './parts'

/** The cleanup's preview, loaded when its sheet opens, and its confirmation (the run it starts). */
function useCleanup(open: boolean, onChanged: () => void) {
  const { api } = useBranchLive()
  const [preview, setPreview] = useState<CleanupPreview | null>(null)
  const [busy, setBusy] = useState(false)
  const [run, setRun] = useState<Run | null>(null)
  const [error, setError] = useState<string | null>(null)
  const load = useCallback(async () => {
    if (!api) return
    setError(null)
    try { setPreview(await api.previewCleanup()) } catch (problem) { setError(problem instanceof Error ? problem.message : String(problem)) }
  }, [api])
  useEffect(() => { if (open) void load() }, [open, load])
  async function confirm() {
    if (!api || !preview) return
    setBusy(true); setError(null)
    try { setRun((await api.cleanup(preview)).run); onChanged(); await load() } catch (problem) {
      if (problem instanceof ActionError && problem.needs === 'refresh') await load()
      setError(problem instanceof Error ? problem.message : String(problem))
    } finally { setBusy(false) }
  }
  return { preview, busy, run, error, confirm }
}

const cleanupState = (open: boolean, preview: CleanupPreview | null, goes: number) => (open ? (preview ? (goes ? 'ready' : 'nothing') : 'loading') : 'closed')

export function Cleanup({ onChanged }: { onChanged: () => void }) {
  const w = useBranchWords()
  const [open, setOpen] = useState(false)
  const [technical, setTechnical] = useState(false)
  const { preview, busy, run, error, confirm } = useCleanup(open, onChanged)
  const goes = preview ? preview.branches.length + preview.worktrees.length : 0
  return (
    <div className={css.cleanup} data-cleanup={cleanupState(open, preview, goes)}>
      <Button variant="secondary" icon="opDelete" onPress={() => setOpen(true)} aria-expanded={open}>{w('cleanup')}</Button>
      {open && <Sheet isOpen onOpenChange={(next) => { if (!next) setOpen(false) }} title={w('cleanup')}>
        <div className={css.drawerBody}>
          {preview ? <CleanupBody preview={preview} goes={goes} run={run} error={error} busy={busy} onConfirm={confirm}
            technical={technical} onTechnical={() => setTechnical(!technical)} />
            : error ? <p role="alert" className={css.error}>{error}</p> : <p className={css.muted}>…</p>}
        </div>
      </Sheet>}
    </div>
  )
}

/** A sheet that leads with what happens in plain words, the branches that stay (the one thing that may need the
 * person) next, and the raw branch list and worktree paths only behind "technical details". */
function CleanupBody({ preview, goes, run, error, busy, onConfirm, technical, onTechnical }: { preview: CleanupPreview; goes: number; run: Run | null;
  error: string | null; busy: boolean; onConfirm: () => void; technical: boolean; onTechnical: () => void }) {
  const w = useBranchWords()
  const { lang } = usePrefs()
  return <>
    {goes === 0 ? <SheetLead>{w('cleanupNothing')}</SheetLead> : <SheetLead>
      {w('cleanupSummary', { n: preview.branches.length })}{preview.worktrees.length > 0 ? ` ${w('cleanupSummaryTrees', { n: preview.worktrees.length })}` : ''}
    </SheetLead>}
    {run && <RescanStatus run={run} />}
    {preview.kept.length > 0 && <>
      <SheetSub>{w('cleanupStays', { n: preview.kept.length })}</SheetSub>
      <ul className={css.files}>{preview.kept.map((k) => <li key={k.branch} data-stays={k.branch}><Id value={k.branch} />: {k.reasons.map((r) => r[lang]).join(' · ')}</li>)}</ul>
    </>}
    <Reasons reasons={preview.blocked} />
    {error && <p role="alert" className={css.error}>{error}</p>}
    {goes > 0 && preview.confirm && <Button variant="primary" icon="opDelete" busy={busy} onPress={onConfirm}>{w('cleanupConfirm')}</Button>}
    {goes > 0 && <Button variant="ghost" icon="chevronDown" onPress={onTechnical} aria-expanded={technical}>{w('technicalDetails')}</Button>}
    {technical && <CleanupTechnical preview={preview} />}
  </>
}

/** The branches kept as the base, the branches that go with the branch each was merged into, and the worktrees. */
function CleanupTechnical({ preview }: { preview: CleanupPreview }) {
  const w = useBranchWords()
  const { lang } = usePrefs()
  return <>
    <p className={css.muted}>{w('cleanupLead', { b: [preview.base, ...preview.kept_branches.filter((b) => b !== preview.base)].filter(Boolean).join(lang === 'ar' ? '، ' : ', ') })}</p>
    {preview.branches.length > 0 && <>
      <SheetSub>{w('cleanupGoes', { n: preview.branches.length })}</SheetSub>
      <ul className={css.files}>{preview.branches.map((b) => <li key={b.branch} data-goes={b.branch}><Id value={b.branch} /> · {w('cleanupMergedInto', { b: b.merged_into })}{b.worktree ? ` · ${w('worktreeGoes', { p: b.worktree })}` : ''}</li>)}</ul>
    </>}
    {preview.worktrees.length > 0 && <>
      <SheetSub>{w('cleanupWorktrees', { n: preview.worktrees.length })}</SheetSub>
      <ul className={css.files}>{preview.worktrees.map((t) => <li key={t.path}><Id value={t.path} /></li>)}</ul>
    </>}
  </>
}
