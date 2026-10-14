// Branches (#/branches, NS46.T18): the repository's local and remote branches as git tells them now, the checkout,
// the analysis branch, the report's branch and the base kept apart, ownership only from durable provenance, and every
// command with the reasons it is blocked. Desktop shows a table and the phone cards, with the same details and
// actions; a drawer holds the compare, diff, checks, runs and the guarded merge and deletion. A snapshot is read-only.
import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import { useSearch, useNavigate } from '@tanstack/react-router'
import { Button } from '../../components/Button'
import { Chip, type Tone } from '../../components/Chip'
import { SearchField, Segmented } from '../../components/Controls'
import { Go } from '../../components/Go'
import { Panel, Props, Section, StateMessage } from '../../components/Panel'
import { Sheet, SheetLead, SheetSub } from '../../components/Sheet'
import { useActions } from '../../data/actions/store'
import { ActionError, type BranchDetail, type BranchRow, type CleanupPreview, type DeletePreview, type Inventory, type MergePreview, type Reason, type Run, type RunLink } from '../../data/actions/types'
import { labelOf } from '../../data/actions/derive'
import { STATE_WORDS } from '../../data/actions/contract'
import { useStudio } from '../../data/context'
import { usePrefs } from '../../i18n/prefs'
import { Id, N, When } from '../../i18n/text'
import { latestRun, shownBranches, type Show } from '../../branches/model'
import { usePageChrome } from '../../shell/chrome'
import { layout, PageTitle } from '../../shell/Layout'
import { useBranchLive } from '../../branches/live'
import { ContextRows, useSelect } from '../../branches/Switcher'
import { RescanStatus, SelectError } from '../../branches/ScanSheet'
import { SnapshotPanel } from '../runs/RunsPage'
import { useBranchWords } from '../../branches/words'
import css from '../../branches/branches.module.css'

function Reasons({ reasons }: { reasons: Reason[] }) {
  const { lang } = usePrefs()
  const w = useBranchWords()
  if (!reasons.length) return null
  return (
    <div className={css.blocked} data-blocked={reasons.map((r) => r.code).join(' ')}>
      <span>{w('blockedBecause')}</span>
      <ul>{reasons.map((r) => <li key={r.code + r.en}>{r[lang]}</li>)}</ul>
    </div>
  )
}

function Badges({ row }: { row: BranchRow }) {
  const w = useBranchWords()
  // the exceptions only: a branch is the person's own unless EAOS made it, and its group already says where it lives
  const owner: [Tone, string] | null = row.ownership.owner === 'eaos' ? ['accent', w('ownerEaos')] : row.ownership.owner === 'shared' ? ['warning', w('ownerShared')] : null
  return (
    <span className={css.badges}>
      {row.kind === 'remote' && row.remote !== 'origin' && <Chip dot={false}>{w('remote', { r: row.remote ?? '' })}</Chip>}
      {row.roles.includes('checkout') && <Chip tone="good">{w('checkout')}</Chip>}
      {row.roles.includes('analysis') && !row.roles.includes('checkout') && <Chip tone="accent">{w('analysis')}</Chip>}
      {row.roles.includes('default') && <Chip>{w('defaultBranch')}</Chip>}
      {row.protected && <Chip tone="warning">{w('protected')}</Chip>}
      {owner && <Chip tone={owner[0]}>{owner[1]}</Chip>}
    </span>
  )
}

function Compare({ row }: { row: BranchRow }) {
  const w = useBranchWords()
  const c = row.compare
  if (c.ahead === null || c.behind === null) return <span className={css.muted}>{w('compareUnknown')}</span>
  if (c.merged && c.base && c.base !== row.name) return <span>{w('merged', { b: c.base })} · {w('aheadBehind', { a: c.ahead, b: c.behind })}</span>
  return <span>{w('aheadBehind', { a: c.ahead, b: c.behind })}</span>
}

function WorktreeNote({ row }: { row: BranchRow }) {
  const w = useBranchWords()
  if (!row.worktree) return null
  const dirty = row.worktree.dirty ? row.worktree.dirty.tracked + row.worktree.dirty.untracked : 0
  return <span className={css.muted}>{row.worktree.current ? w('worktreeHere') : w('worktreeOther', { p: row.worktree.path })}{dirty ? ` · ${w('unsaved', { n: dirty })}` : ''}</span>
}

function RunLinks({ runs, all = false }: { runs: RunLink[]; all?: boolean }) {
  const { lang } = usePrefs()
  const w = useBranchWords()
  if (!runs.length) return null
  const { run, more } = latestRun(runs)
  const link = (r: RunLink) => <li key={r.id + r.role}><Go to={`/runs/${encodeURIComponent(r.id)}`} className={css.inlineLink}>{labelOf(r.label, lang)}</Go> <span className={css.muted}>· {STATE_WORDS[r.state]?.[lang] ?? r.state}</span></li>
  if (all) return <ul className={css.runLinks}>{runs.slice(0, 20).map(link)}</ul>
  return (
    <ul className={css.runLinks}>
      {run && link(run)}
      {more > 0 && <li className={css.muted}>{w('moreRuns', { n: more })}</li>}
    </ul>
  )
}

/** A commit subject: often English inside an Arabic line, so it keeps its own direction. */
function Subject({ text }: { text: string }) {
  return text ? <bdi dir="ltr" className={css.subject}>{text}</bdi> : null
}

// ------------------------------------------------------------------ merge and delete panels

function MergePanel({ row, target, onDone }: { row: BranchRow; target: string | null; onDone: (run: Run) => void }) {
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
      {!preview.blocked.length && <Button variant="primary" icon="check" busy={busy} isDisabled={preview.needs_unchecked_ack && !ack} onPress={() => void confirm()}>{w('confirmMerge')}</Button>}
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

function DeletePanel({ row, onDone }: { row: BranchRow; onDone: (run: Run) => void }) {
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
      {!preview.blocked.length && <Button variant="primary" icon="opDelete" busy={busy} isDisabled={Boolean(preview.unmerged) && !second} onPress={() => void confirm()}>{w('confirmDelete')}</Button>}
    </div>
  )
}

// ------------------------------------------------------------------ the drawer

function Drawer({ row, base, onClose, onChanged }: { row: BranchRow; base: string | null; onClose: () => void; onChanged: () => void }) {
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

// ------------------------------------------------------------------ the page

function Row({ row, onOpen }: { row: BranchRow; onOpen: () => void }) {
  const w = useBranchWords()
  return (
    <tr data-branch={row.name} data-kind={row.kind}>
      <th scope="row"><Id value={row.name} /><div><Badges row={row} /></div></th>
      <td>{row.last_commit ? <When iso={row.last_commit} /> : '—'}<div className={css.muted}><Subject text={row.subject} /></div></td>
      <td><Compare row={row} /><div><WorktreeNote row={row} /></div></td>
      <td><RunLinks runs={row.runs} /></td>
      <td><Button variant="secondary" onPress={onOpen} aria-label={w('details', { b: row.name })}>{w('detailsShort')}</Button></td>
    </tr>
  )
}

function Card({ row, onOpen }: { row: BranchRow; onOpen: () => void }) {
  const w = useBranchWords()
  return (
    <li className={css.card} data-branch={row.name} data-kind={row.kind}>
      <div className={css.cardHead}><Id value={row.name} /></div>
      <Badges row={row} />
      <div className={css.cardMeta}>{row.last_commit ? <When iso={row.last_commit} /> : '—'} · <Compare row={row} /></div>
      <WorktreeNote row={row} />
      <RunLinks runs={row.runs} />
      <Button variant="secondary" block onPress={onOpen} aria-label={w('details', { b: row.name })}>{w('detailsShort')}</Button>
    </li>
  )
}

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

function Cleanup({ onChanged }: { onChanged: () => void }) {
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
          {preview ? <CleanupBody preview={preview} goes={goes} run={run} error={error} busy={busy} onConfirm={() => void confirm()}
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

function Recoveries({ inventory, onChanged }: { inventory: Inventory; onChanged: () => void }) {
  const w = useBranchWords()
  const { api } = useBranchLive()
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const open = (inventory.recovery ?? []).filter((r) => !r.restored && r.where === 'local')
  if (!open.length) return null
  return (
    <Section title={w('recoverable')} count={open.length}>
      <Panel>
        <ul className={css.recoveries}>
          {open.slice().reverse().map((r) => (
            <li key={r.id} data-recovery={r.id}>
              <span><Id value={r.branch} /> · <Id value={r.tip.slice(0, 12)} /> · <When iso={r.at} /></span>
              <Button variant="secondary" icon="retry" busy={busy === r.id} onPress={async () => {
                if (!api) return
                setBusy(r.id); setError(null)
                try { await api.restore(r.id); onChanged() } catch (problem) { setError(problem instanceof Error ? problem.message : String(problem)) } finally { setBusy(null) }
              }}>{w('restore')}</Button>
            </li>
          ))}
        </ul>
        {error && <p role="alert" className={css.error}>{error}</p>}
      </Panel>
    </Section>
  )
}

function LiveBranches() {
  const w = useBranchWords()
  const { t } = usePrefs()
  const live = useBranchLive()
  const navigate = useNavigate()
  const search = useSearch({ strict: false }) as { show?: Show; q?: string; base?: string; b?: string }
  const show: Show = search.show === 'all' ? 'all' : 'work'
  const [q, setQ] = useState(search.q ?? '')
  const [inventory, setInventory] = useState<Inventory | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [round, setRound] = useState(0)
  const base = search.base ?? null
  useEffect(() => {
    if (!live.api) return
    let on = true
    live.api.inventory(base).then((inv) => { if (on) { setInventory(inv); setError(null) } }, (problem) => { if (on) setError(problem instanceof Error ? problem.message : String(problem)) })
    return () => { on = false }
  }, [live.api, base, round, live.context?.analysis.branch, live.freshness?.checked_at])
  const changed = useCallback(() => { setRound((n) => n + 1); void live.refresh() }, [live])
  const set = (patch: Record<string, string | undefined>) => navigate({ to: '/branches', search: { ...search, ...patch }, replace: true })
  const shown = useMemo(() => shownBranches(inventory?.branches ?? [], show, q), [inventory, q, show])
  const opened = inventory?.branches.find((row) => row.id === search.b) ?? null
  if (error && !inventory) return <Panel><StateMessage kind="error" title={w('failed')} sub={error} action={<Button variant="secondary" icon="retry" onPress={changed}>{w('retry')}</Button>} /></Panel>
  if (!inventory) return <Panel><p className={css.muted}>…</p></Panel>
  if (!inventory.git) return <Panel><StateMessage title={w('notGit')} /></Panel>
  return (
    <>
      {inventory.context && <Panel className={css.contextPanel}><ContextRows context={inventory.context} /></Panel>}
      <BranchToolbar inventory={inventory} show={show} q={q} onQ={(next) => { setQ(next); set({ q: next || undefined }) }} set={set} />
      <RemoteLine inventory={inventory} onError={setError} onChanged={changed} />
      <Cleanup onChanged={changed} />
      {error && <p role="alert" className={css.error}>{error}</p>}
      {inventory.truncated && <p className={css.note}>{w('truncated', { n: inventory.branches.length })}</p>}
      {shown.local.length + shown.remote.length === 0 ? <Panel><StateMessage title={show === 'work' ? w('noBranchesWork') : w('noBranches')} /></Panel>
        : <BranchGroups shown={shown} base={inventory.base} onOpen={(id) => set({ b: id })} />}
      <Recoveries inventory={inventory} onChanged={changed} />
      <MissingLinked inventory={inventory} />
      {opened && <Drawer row={opened} base={inventory.base ?? null} onClose={() => set({ b: undefined })} onChanged={changed} />}
      <span className="sr" aria-live="polite">{t('branch')}: {inventory.context?.analysis.branch ?? ''}</span>
    </>
  )
}

/** Work or every branch, the search, and the base the branches are compared with. */
function BranchToolbar({ inventory, show, q, onQ, set }:
  { inventory: Inventory; show: Show; q: string; onQ: (next: string) => void; set: (patch: Record<string, string | undefined>) => void }) {
  const w = useBranchWords()
  const locals = inventory.branches.filter((b) => b.kind === 'local')
  return (
    <div className={css.toolbar}>
      <Segmented comfortable label={w('branches')} value={show} onChange={(next) => set({ show: next })} options={[{ id: 'work', label: w('work') }, { id: 'all', label: w('all') }]} />
      <SearchField label={w('searchBranches')} placeholder={w('searchBranches')} value={q} onChange={onQ} />
      <label className={css.baseSelect}>
        <span>{w('base')}</span>
        <select value={inventory.base ?? ''} onChange={(event) => set({ base: event.target.value || undefined })}>
          {locals.map((b) => <option key={b.ref} value={b.name}>{b.name}</option>)}
        </select>
      </label>
    </div>
  )
}

/** When the remote was last fetched, and fetching it again; or that there is no remote. */
function RemoteLine({ inventory, onError, onChanged }: { inventory: Inventory; onError: (error: string) => void; onChanged: () => void }) {
  const w = useBranchWords()
  const live = useBranchLive()
  const [fetching, setFetching] = useState(false)
  const [fetchRun, setFetchRun] = useState<Run | null>(null)
  return (
    <div className={css.remoteLine}>
      {!inventory.has_origin && (inventory.remotes ?? []).length === 0 ? <span>{w('noOrigin')}</span> : <>
        <span>{inventory.last_fetch ? <>{w('remoteAsOf', { d: '' })}<When iso={inventory.last_fetch} /></> : w('remoteNever')}</span>
        <Button variant="secondary" icon="retry" busy={fetching} onPress={async () => {
          if (!live.api) return
          setFetching(true)
          try { setFetchRun((await live.api.fetch((inventory.remotes ?? [])[0])).run) } catch (problem) { onError(problem instanceof Error ? problem.message : String(problem)) } finally { setFetching(false); onChanged() }
        }}>{w('refreshRemote')}</Button>
        {fetchRun && <RescanStatus run={fetchRun} />}
      </>}
    </div>
  )
}

/** The branches on this computer, then on the remote: a table on the desktop and cards on the phone. */
function BranchGroups({ shown, base, onOpen }: { shown: ReturnType<typeof shownBranches>; base?: string | null; onOpen: (id: string) => void }) {
  const w = useBranchWords()
  return (
    <>
      {([['local', w('onComputer'), shown.local], ['remote', w('onRemote'), shown.remote]] as const).filter(([, , rows]) => rows.length > 0).map(([kind, title, rows]) => (
        <section key={kind} data-group={kind}>
          <h2 className={css.groupTitle}>{title}</h2>
          <div className={css.tableWrap}>
            <table className={css.table}>
              <thead><tr><th scope="col">{w('branches')}</th><th scope="col">{w('lastCommit')}</th><th scope="col">{w('base')}: {base ?? '—'}</th><th scope="col">{w('linkedRuns')}</th><th scope="col"><span className="sr">{w('commands')}</span></th></tr></thead>
              <tbody>{rows.map((row) => <Row key={row.id} row={row} onOpen={() => onOpen(row.id)} />)}</tbody>
            </table>
          </div>
          <ul className={css.cards}>{rows.map((row) => <Card key={row.id} row={row} onOpen={() => onOpen(row.id)} />)}</ul>
        </section>
      ))}
    </>
  )
}

/** Branches runs were linked to that no longer exist here. */
function MissingLinked({ inventory }: { inventory: Inventory }) {
  const w = useBranchWords()
  const missing = inventory.missing_linked ?? []
  if (!missing.length) return null
  return (
    <Section title={w('missingLinked')} count={missing.length}>
      <Panel><ul className={css.recoveries}>{missing.map((m) => <li key={m.name}><Id value={m.name} /><RunLinks runs={m.runs} /></li>)}</ul></Panel>
    </Section>
  )
}

function SnapshotBranches() {
  const w = useBranchWords()
  const data = useStudio()
  const scanned = data?.head?.scanned ?? data?.manifest.scanned
  return (
    <>
      <Panel className={css.contextPanel}>
        <SheetLead>{w('readOnlySnapshot')}</SheetLead>
        <Props rows={[
          [w('scannedBranch'), scanned?.detached ? w('detachedShort') : scanned?.branch ? <Id value={scanned.branch} /> : w('legacyNotRecorded'), !scanned?.branch],
          [w('scannedCommit'), scanned?.commit && scanned.recorded ? <span title={scanned.commit}><Id value={scanned.commit.slice(0, 12)} /></span> : w('legacyNotRecorded'), !scanned?.recorded],
          [w('scannedDirty'), scanned?.dirty === true ? w('yes') : scanned?.dirty === false ? w('no') : w('legacyNotRecorded'), scanned?.dirty == null],
        ]} />
      </Panel>
      <SnapshotPanel />
    </>
  )
}

export function BranchesPage() {
  const w = useBranchWords()
  const data = useStudio()
  const live = useBranchLive()
  const actions = useActions()
  usePageChrome(w('branches'), undefined, data?.manifest.project.name)
  return (
    <div className={[layout.page, css.tall].join(' ')} data-page="branches">
      <PageTitle title={w('branches')} lead={w('branchesLead')} />
      {live.api ? <LiveBranches /> : actions.mode === 'live' ? <Panel><p className={css.muted}>…</p></Panel> : <SnapshotBranches />}
    </div>
  )
}
