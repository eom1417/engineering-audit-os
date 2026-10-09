// Branches (#/branches, NS46.T18): the repository's local and remote branches as git tells them now, the checkout,
// the analysis branch, the report's branch and the base kept apart, ownership only from durable provenance, and every
// command with the reasons it is blocked. Desktop shows a table and the phone cards, with the same details and
// actions; a drawer holds the compare, diff, checks, runs and the guarded merge and deletion. A snapshot is read-only.
import { useCallback, useEffect, useMemo, useState } from 'react'
import { useSearch, useNavigate } from '@tanstack/react-router'
import { Button } from '../../components/Button'
import { Chip, type Tone } from '../../components/Chip'
import { SearchField, Segmented } from '../../components/Controls'
import { Go } from '../../components/Go'
import { Panel, Props, Section, StateMessage } from '../../components/Panel'
import { Sheet, SheetLead, SheetSub } from '../../components/Sheet'
import { useActions } from '../../data/actions/store'
import { ActionError, type BranchDetail, type BranchRow, type DeletePreview, type Inventory, type MergePreview, type Reason, type Run, type RunLink } from '../../data/actions/types'
import { labelOf } from '../../data/actions/derive'
import { useStudio } from '../../data/context'
import { usePrefs } from '../../i18n/prefs'
import { Id, N, When } from '../../i18n/text'
import { normalize } from '../../search/normalize'
import { usePageChrome } from '../../shell/chrome'
import { layout, PageTitle } from '../../shell/Layout'
import { useBranchLive } from '../../branches/live'
import { ContextRows, SelectError, useSelect } from '../../branches/Switcher'
import { RescanStatus } from '../../branches/ScanSheet'
import { SnapshotPanel } from '../runs/RunsPage'
import { useBranchWords } from '../../branches/words'
import css from '../../branches/branches.module.css'

type Show = 'work' | 'all'

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
  const owner: [Tone, string] = row.ownership.owner === 'eaos' ? ['accent', w('ownerEaos')] : row.ownership.owner === 'shared' ? ['warning', w('ownerShared')] : ['neutral', w('ownerUnknown')]
  return (
    <span className={css.badges}>
      <Chip dot={false}>{row.kind === 'local' ? w('local') : w('remote', { r: row.remote ?? '' })}</Chip>
      {row.roles.includes('checkout') && <Chip tone="good">{w('checkout')}</Chip>}
      {row.roles.includes('analysis') && <Chip tone="accent">{w('analysis')}</Chip>}
      {row.roles.includes('report') && <Chip>{w('reportOf')}</Chip>}
      {row.roles.includes('default') && <Chip>{w('defaultBranch')}</Chip>}
      {row.protected && <Chip tone="warning">{w('protected')}</Chip>}
      <Chip tone={owner[0]}>{owner[1]}</Chip>
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

function RunLinks({ runs }: { runs: RunLink[] }) {
  const { lang } = usePrefs()
  if (!runs.length) return null
  return (
    <ul className={css.runLinks}>
      {runs.slice(0, 6).map((run) => <li key={run.id + run.role}><Go to={`/runs/${encodeURIComponent(run.id)}`} className={css.inlineLink}>{labelOf(run.label, lang)}</Go> <span className={css.muted}>· {run.state}</span></li>)}
    </ul>
  )
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
        [preview.source, <Id value={preview.source_head.slice(0, 12)} />],
        [preview.target, <Id value={preview.target_head.slice(0, 12)} />],
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
        {preview.unmerged && <ul className={css.files}>{(preview.lost_commits ?? []).map((c) => <li key={c.commit}><Id value={c.commit.slice(0, 12)} /> {c.subject}</li>)}</ul>}
        <p>{w('remoteKept')}</p>
      </>}
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
  const [diff, setDiff] = useState(false)
  const [panel, setPanel] = useState<'merge' | 'delete' | null>(null)
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
      <Badges row={row} />
      {error && <p role="alert" className={css.error}>{error}</p>}
      {followed && <RescanStatus run={followed} error={null} />}
      {select.scan && <RescanStatus run={select.scan} error={null} />}
      <SelectError error={select.error} />
      {detail && <>
        <Props rows={[
          ['Commit', <Id value={row.tip} />],
          [w('lastCommit'), row.last_commit ? <><When iso={row.last_commit} /> · {row.subject}</> : '—'],
          [w('base'), detail.base ? <Id value={detail.base} /> : '—', !detail.base],
          [w('lineage'), detail.lineage ? <>{detail.lineage.parent ?? '—'}{detail.lineage.parent_commit ? <> @ <Id value={detail.lineage.parent_commit.slice(0, 12)} /></> : null} · {detail.lineage.evidence}</> : w('lineageUnknown'), !detail.lineage],
          [w('checks'), detail.checks.status === 'passed' ? w('checksPassed', { c: detail.checks.commit.slice(0, 12) }) : detail.checks.status === 'failed' ? w('checksFailed', { c: detail.checks.commit.slice(0, 12) }) : w('checksNone')],
          [w('destination'), <>{detail.destination.recommended ? w('recommended', { b: detail.destination.recommended }) : '—'} · {detail.destination.confirmed ? w('confirmedInto', { b: detail.destination.confirmed.branch }) : w('notMergedYet')}</>],
        ]} />
        {row.worktree && <WorktreeNote row={row} />}
        {detail.commits.length > 0 && <>
          <SheetSub>{w('commitsAhead', { b: detail.base ?? '' })} (<N value={detail.commits.length} />)</SheetSub>
          <ul className={css.files}>{detail.commits.map((c) => <li key={c.commit}><Id value={c.commit.slice(0, 12)} /> {c.subject} <span className={css.muted}>· {c.author}</span></li>)}</ul>
        </>}
        {detail.files.length > 0 && <>
          <SheetSub>{w('filesChanged')} (<N value={detail.files_total} />)</SheetSub>
          <ul className={css.files}>{detail.files.slice(0, 40).map((f) => <li key={f.path}><span className={css.muted}>{f.status}</span> <Id value={f.path} /></li>)}</ul>
          <Button variant="ghost" onPress={() => setDiff(!diff)} aria-expanded={diff}>{diff ? w('hideDiff') : w('showDiff')}</Button>
          {diff && <>{detail.diff_cut && <p className={css.muted}>{w('diffCut')}</p>}<pre className={css.diff} tabIndex={0} dir="ltr">{detail.diff}</pre></>}
        </>}
        {detail.runs.length > 0 && <><SheetSub>{w('linkedRuns')}</SheetSub><RunLinks runs={detail.runs} /></>}
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
          {(commands.delete_local || commands.delete_remote) && <div className={css.command}>
            <Button variant="secondary" icon="opDelete" onPress={() => setPanel(panel === 'delete' ? null : 'delete')} aria-expanded={panel === 'delete'}>
              {row.kind === 'remote' ? w('deleteRemote', { r: row.remote ?? '' }) : w('deleteLocal')}</Button>
            {!(commands.delete_local ?? commands.delete_remote).available && panel !== 'delete' && <Reasons reasons={(commands.delete_local ?? commands.delete_remote).blocked} />}
          </div>}
          {panel === 'delete' && <DeletePanel row={row} onDone={done} />}
        </div>
      </>}
      {!detail && !error && <p className={css.muted}>…</p>}
      <span className="sr" aria-live="polite">{followed ? labelOf(followed.label, lang) : ''}</span>
    </Sheet>
  )
}

// ------------------------------------------------------------------ the page

function Row({ row, onOpen }: { row: BranchRow; onOpen: () => void }) {
  const w = useBranchWords()
  return (
    <tr data-branch={row.name} data-kind={row.kind}>
      <th scope="row"><Id value={row.name} /><div><Badges row={row} /></div></th>
      <td>{row.last_commit ? <When iso={row.last_commit} /> : '—'}<div className={css.muted}>{row.subject}</div></td>
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
  const [fetching, setFetching] = useState(false)
  const [fetchRun, setFetchRun] = useState<Run | null>(null)
  const base = search.base ?? null
  useEffect(() => {
    if (!live.api) return
    let on = true
    live.api.inventory(base).then((inv) => { if (on) { setInventory(inv); setError(null) } }, (problem) => { if (on) setError(problem instanceof Error ? problem.message : String(problem)) })
    return () => { on = false }
  }, [live.api, base, round, live.context?.analysis.branch, live.freshness?.checked_at])
  const changed = useCallback(() => { setRound((n) => n + 1); void live.refresh() }, [live])
  const set = (patch: Record<string, string | undefined>) => navigate({ to: '/branches', search: { ...search, ...patch }, replace: true })
  const rows = useMemo(() => {
    const words = normalize(q).split(' ').filter(Boolean)
    return (inventory?.branches ?? []).filter((row) => (show === 'all' || row.work || row.roles.length > 0) && words.every((word) => normalize(`${row.name} ${row.remote ?? ''} ${row.subject}`).includes(word)))
  }, [inventory, q, show])
  const opened = inventory?.branches.find((row) => row.id === search.b) ?? null
  if (error && !inventory) return <Panel><StateMessage kind="error" title={w('failed')} sub={error} action={<Button variant="secondary" icon="retry" onPress={changed}>{w('retry')}</Button>} /></Panel>
  if (!inventory) return <Panel><p className={css.muted}>…</p></Panel>
  if (!inventory.git) return <Panel><StateMessage title={w('notGit')} /></Panel>
  const locals = inventory.branches.filter((b) => b.kind === 'local')
  return (
    <>
      {inventory.context && <Panel className={css.contextPanel}><ContextRows context={inventory.context} /></Panel>}
      <div className={css.toolbar}>
        <Segmented label={w('branches')} value={show} onChange={(next) => set({ show: next })} options={[{ id: 'work', label: w('work') }, { id: 'all', label: w('all') }]} />
        <SearchField label={w('searchBranches')} placeholder={w('searchBranches')} value={q} onChange={(next) => { setQ(next); set({ q: next || undefined }) }} />
        <label className={css.baseSelect}>
          <span>{w('base')}</span>
          <select value={inventory.base ?? ''} onChange={(event) => set({ base: event.target.value || undefined })}>
            {locals.map((b) => <option key={b.ref} value={b.name}>{b.name}</option>)}
          </select>
        </label>
      </div>
      <div className={css.remoteLine}>
        {!inventory.has_origin && (inventory.remotes ?? []).length === 0 ? <span>{w('noOrigin')}</span> : <>
          <span>{inventory.last_fetch ? <>{w('remoteAsOf', { d: '' })}<When iso={inventory.last_fetch} /></> : w('remoteNever')}</span>
          <Button variant="secondary" icon="retry" busy={fetching} onPress={async () => {
            if (!live.api) return
            setFetching(true)
            try { setFetchRun((await live.api.fetch((inventory.remotes ?? [])[0])).run) } catch (problem) { setError(problem instanceof Error ? problem.message : String(problem)) } finally { setFetching(false); changed() }
          }}>{w('refreshRemote')}</Button>
          {fetchRun && <RescanStatus run={fetchRun} error={null} />}
        </>}
      </div>
      {error && <p role="alert" className={css.error}>{error}</p>}
      {inventory.truncated && <p className={css.note}>{w('truncated', { n: inventory.branches.length })}</p>}
      {rows.length === 0 ? <Panel><StateMessage title={show === 'work' ? w('noBranchesWork') : w('noBranches')} /></Panel> : <>
        <div className={css.tableWrap}>
          <table className={css.table}>
            <thead><tr><th scope="col">{w('branches')}</th><th scope="col">{w('lastCommit')}</th><th scope="col">{w('base')}: {inventory.base ?? '—'}</th><th scope="col">{w('linkedRuns')}</th><th scope="col"><span className="sr">{w('commands')}</span></th></tr></thead>
            <tbody>{rows.map((row) => <Row key={row.id} row={row} onOpen={() => set({ b: row.id })} />)}</tbody>
          </table>
        </div>
        <ul className={css.cards}>{rows.map((row) => <Card key={row.id} row={row} onOpen={() => set({ b: row.id })} />)}</ul>
      </>}
      <Recoveries inventory={inventory} onChanged={changed} />
      {(inventory.missing_linked ?? []).length > 0 && <Section title={w('missingLinked')} count={inventory.missing_linked!.length}>
        <Panel><ul className={css.recoveries}>{inventory.missing_linked!.map((m) => <li key={m.name}><Id value={m.name} /><RunLinks runs={m.runs} /></li>)}</ul></Panel>
      </Section>}
      {opened && <Drawer row={opened} base={inventory.base ?? null} onClose={() => set({ b: undefined })} onChanged={changed} />}
      <span className="sr" aria-live="polite">{t('branch')}: {inventory.context?.analysis.branch ?? ''}</span>
    </>
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
          [w('scannedCommit'), scanned?.commit && scanned.recorded ? <Id value={scanned.commit} /> : w('legacyNotRecorded'), !scanned?.recorded],
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
    <div className={layout.page} data-page="branches">
      <PageTitle title={w('branches')} lead={w('branchesLead')} />
      {live.api ? <LiveBranches /> : actions.mode === 'live' ? <Panel><p className={css.muted}>…</p></Panel> : <SnapshotBranches />}
    </div>
  )
}
