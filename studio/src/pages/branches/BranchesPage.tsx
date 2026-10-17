// Branches (#/branches, NS46.T18): the repository's local and remote branches as git tells them now, the checkout,
// the analysis branch, the report's branch and the base kept apart, ownership only from durable provenance, and every
// command with the reasons it is blocked. Desktop shows a table and the phone cards, with the same details and
// actions; a drawer holds the compare, diff, checks, runs and the guarded merge and deletion (Drawer.tsx, Panels.tsx);
// the cleanup has its own sheet (Cleanup.tsx). A snapshot is read-only.
import { useCallback, useEffect, useMemo, useState } from 'react'
import { useSearch, useNavigate } from '@tanstack/react-router'
import { Button } from '../../components/Button'
import { SearchField, Segmented } from '../../components/Controls'
import { Panel, Props, Section, StateMessage } from '../../components/Panel'
import { SheetLead } from '../../components/Sheet'
import { useActions } from '../../data/actions/store'
import type { BranchRow, Inventory, Run } from '../../data/actions/types'
import { useStudio } from '../../data/context'
import { usePrefs } from '../../i18n/prefs'
import { Id, When } from '../../i18n/text'
import { shownBranches, type Show } from '../../branches/model'
import { usePageChrome } from '../../shell/chrome'
import { layout, PageTitle } from '../../shell/Layout'
import { ChangeNav } from '../change/parts'
import { useBranchLive } from '../../branches/live'
import { ContextRows } from '../../branches/Switcher'
import { RescanStatus } from '../../branches/ScanSheet'
import { SnapshotPanel } from '../runs/RunsPage'
import { useBranchWords } from '../../branches/words'
import css from '../../branches/branches.module.css'
import { Cleanup } from './Cleanup'
import { Drawer } from './Drawer'
import { Badges, Compare, RunLinks, Subject, WorktreeNote } from './parts'

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
      <ChangeNav />
      <PageTitle title={w('branches')} lead={w('branchesLead')} />
      {live.api ? <LiveBranches /> : actions.mode === 'live' ? <Panel><p className={css.muted}>…</p></Panel> : <SnapshotBranches />}
    </div>
  )
}
