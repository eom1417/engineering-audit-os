// "Is this scan current?" (NS46.T19): what the scan read (branch or detached HEAD, full commit, unsaved changes, scan
// and build times), whether it still holds now, and the direct action: Re-scan now through the live command centre,
// with saved, running and done states, a link to the run and the report refreshed. Copying an instruction for an
// assistant stays as a labelled fallback; a snapshot says it is read-only and offers to open the live Studio.
import { useState } from 'react'
import { Button, copyText } from '../components/Button'
import { Chip } from '../components/Chip'
import { Go } from '../components/Go'
import { Props } from '../components/Panel'
import { Sheet, SheetLead, SheetSub } from '../components/Sheet'
import { useToast } from '../components/Toast'
import { SNAPSHOT } from '../data/actions/contract'
import { useActions } from '../data/actions/store'
import { ActionError, type LiveFreshness, type Run } from '../data/actions/types'
import { useStudio } from '../data/context'
import { usePrefs } from '../i18n/prefs'
import { Id, When } from '../i18n/text'
import { useBranchLive, useFreshView } from './live'
import { useBranchWords } from './words'
import css from './branches.module.css'

/** The run a Re-scan started, followed through the command centre's run list until it is over. */
export function useRescan() {
  const actions = useActions()
  const live = useBranchLive()
  const [run, setRun] = useState<Run | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const current = run ? actions.runs.find((r) => r.id === run.id) ?? run : null
  async function start() {
    if (!actions.client || actions.mode !== 'live') return
    setBusy(true); setError(null)
    try {
      const made = await actions.client.start({ action: 'audit', inputs: {} })
      setRun(made)
      await actions.refresh()
    } catch (problem) {
      setError(problem instanceof ActionError ? problem.message : String(problem))
    } finally { setBusy(false) }
  }
  return { run: current, error, busy, start, live: actions.mode === 'live' && Boolean(live.api), reset: () => { setRun(null); setError(null) } }
}

export function RescanStatus({ run, error }: { run: Run | null; error: string | null }) {
  const w = useBranchWords()
  if (error) return <p role="alert" className={css.error}>{error}</p>
  if (!run) return null
  const word = run.state === 'queued' ? 'rescanSaved' : run.state === 'done' ? 'rescanDone' : ['failed', 'stopped'].includes(run.state) ? 'rescanFailed' : 'rescanRunning'
  const tone = run.state === 'done' ? 'good' : ['failed', 'stopped'].includes(run.state) ? 'critical' : 'accent'
  return (
    <div className={css.status} role="status" aria-live="polite" data-run-state={run.state}>
      <Chip tone={tone}>{w(word)}</Chip>
      <Go to={`/runs/${encodeURIComponent(run.id)}`} className={css.inlineLink}>{w('openRun', { id: run.id })}</Go>
    </div>
  )
}

function why(reason: string | null, w: ReturnType<typeof useBranchWords>): string {
  if (reason === 'not_scanned') return w('whyNotScanned')
  if (reason === 'not_git') return w('whyNotGit')
  if (reason === 'branch_missing') return w('whyBranchMissing')
  return reason ?? w('whyOffline')
}

/** A complete, self-contained instruction an assistant can run to bring the Studio up to date. */
export function instruction(lang: 'ar' | 'en', o: { name: string; path: string | null; branch: string | null; tip: string | null; scanned: string | null; at: string | null }): string {
  const where = o.path ? `${o.path}` : (lang === 'ar' ? `مجلد المشروع ${o.name}` : `the folder of the project ${o.name}`)
  const branch = o.branch ?? (lang === 'ar' ? 'الفرع المفتوح الآن (أو HEAD المنفصل)' : 'the branch checked out now (or the detached HEAD)')
  if (lang === 'ar') {
    return [`افتح المشروع ${o.name} في ${where}.`,
      `شغّل أداة audit من EAOS (أداة MCP اسمها audit) على الفرع ${branch}${o.tip ? `، ورأسه الآن ${o.tip}` : ''}.`,
      o.scanned ? `التقرير المعروض فُحص على الـcommit ${o.scanned}${o.at ? ` في ${o.at} (UTC)` : ''}.` : 'التقرير المعروض لم يسجّل الـcommit الذي فحصه.',
      'لا تغيّر الفرع المفتوح ولا أي ملف.',
      'حين ينتهي، أبلغني: الفرع والـcommit الكامل اللذين فُحصا، وهل كانت فيه تعديلات غير محفوظة، ووقت التقرير الجديد. الاستوديو الحي يقرأ التقرير الجديد بنفسه.'].join('\n')
  }
  return [`Open the project ${o.name} in ${where}.`,
    `Run the EAOS audit tool (the MCP tool named audit) on the branch ${branch}${o.tip ? `, whose head is now ${o.tip}` : ''}.`,
    o.scanned ? `The report shown was scanned at commit ${o.scanned}${o.at ? ` on ${o.at} (UTC)` : ''}.` : 'The report shown did not record the commit it scanned.',
    'Do not change the checked-out branch or any file.',
    'When it finishes, tell me: the branch and full commit scanned, whether the checkout had unsaved changes, and the new report\'s time. The live Studio reads the new report by itself.'].join('\n')
}

function Lead({ fresh, view }: { fresh: LiveFreshness | null; view: NonNullable<ReturnType<typeof useFreshView>> }) {
  const w = useBranchWords()
  const data = useStudio()
  const detail = data?.head?.freshness_detail
  const behind = fresh?.behind ?? detail?.behind ?? null
  switch (view.state) {
    case 'fresh': return <SheetLead>{fresh?.behind?.eaos_only ? w('freshEaosOnly') : w('freshFreshLead')}</SheetLead>
    case 'behind':
    case 'branch_moved':
      return <>
        <SheetLead>{behind ? w('freshBehindLead', { c: behind.commits ?? 0, f: behind.files }) : w('freshBehindLead', { c: '?', f: '?' })}</SheetLead>
        {behind && behind.file_list.length > 0 && <ul className={css.files} aria-label={w('filesChanged')}>
          {behind.file_list.map((file) => <li key={file}><Id value={file} /></li>)}
          {(behind.truncated || behind.files > behind.file_list.length) && <li>{w('moreFiles', { n: behind.files - behind.file_list.length })}</li>}
        </ul>}
      </>
    case 'rewritten': return <SheetLead>{w('freshRewrittenLead')}</SheetLead>
    case 'dirty': return <SheetLead>{w('freshDirtyLead', { n: (fresh?.dirty?.tracked ?? 0) + (fresh?.dirty?.untracked ?? 0) })}</SheetLead>
    case 'other_branch': return <SheetLead>{w('freshOtherLead', { s: fresh?.scanned_branch ?? '?', b: fresh?.branch ?? '?' })}</SheetLead>
    case 'eaos_updated': return <SheetLead>{w('freshUpdatedLead')}</SheetLead>
    case 'legacy': return <SheetLead>{w('freshLegacyLead')}</SheetLead>
    default: return <SheetLead>{w('freshUnknownLead', { why: why(fresh?.reason ?? null, w) })}</SheetLead>
  }
}

export function ScanSheet({ isOpen, onOpenChange }: { isOpen: boolean; onOpenChange: (open: boolean) => void }) {
  const { t, lang } = usePrefs()
  const w = useBranchWords()
  const toast = useToast()
  const data = useStudio()
  const live = useBranchLive()
  const view = useFreshView()
  const rescan = useRescan()
  if (!data || !view) return null
  const fresh = live.freshness
  const scanned = data.head?.scanned ?? data.manifest.scanned
  const legacy = view.state === 'legacy'
  const branch = fresh ? fresh.scanned_branch : scanned.branch
  const detached = fresh ? fresh.scanned_detached : scanned.detached
  const commit = fresh ? fresh.scanned_commit : scanned.commit
  const dirty = fresh ? fresh.scanned_dirty : scanned.dirty
  const at = fresh?.scanned_at ?? scanned.at
  const notRecorded = legacy ? w('legacyNotRecorded') : t('notRecorded')
  const rows: [React.ReactNode, React.ReactNode, boolean?][] = [
    [t('scanned'), at ? <When iso={at} /> : notRecorded, !at],
    [t('reportBuilt'), <When iso={fresh?.report_built ?? data.manifest.built.built} />],
    [w('scannedBranch'), detached ? w('detached', { c: (commit ?? '').slice(0, 12) }) : branch ? <Id value={branch} /> : notRecorded, !branch && !detached],
    [w('scannedCommit'), commit && !legacy ? <Id value={commit} /> : notRecorded, !commit || legacy],
    [w('scannedDirty'), dirty === true ? w('yes') : dirty === false ? w('no') : notRecorded, dirty == null],
  ]
  if (fresh) {
    rows.push([w('headNow'), fresh.tip ? <Id value={fresh.tip} /> : t('notRecorded'), !fresh.tip])
    rows.push([w('checkedAt'), <When iso={fresh.checked_at} />])
  }
  const text = instruction(lang, { name: data.manifest.project.name, path: fresh?.project_path ?? null,
    branch: fresh?.branch ?? branch ?? null, tip: fresh?.tip ?? null, scanned: legacy ? null : commit ?? null, at })
  const otherBranch = view.state === 'other_branch' && fresh?.branch
  return (
    <Sheet isOpen={isOpen} onOpenChange={onOpenChange} title={t('isScanCurrent')}>
      <Lead fresh={fresh} view={view} />
      {live.offline && <p className={css.note} role="status">{w('freshUnknownLead', { why: w('whyOffline') })}</p>}
      <Props rows={rows} />
      {rescan.live ? (
        <div className={css.actions} data-fresh-actions="live">
          <Button variant="primary" icon="retry" busy={rescan.busy} onPress={() => void rescan.start()}
            isDisabled={Boolean(rescan.run && !['done', 'failed', 'stopped'].includes(rescan.run.state))}>
            {otherBranch ? w('rescanBranch', { b: fresh.branch as string }) : w('rescanNow')}
          </Button>
          <RescanStatus run={rescan.run} error={rescan.error} />
        </div>
      ) : (
        <div className={css.req} data-fresh-actions="snapshot">
          <p>{w('readOnlySnapshot')}</p>
          <SheetSub>{w('openLive')}</SheetSub>
          <p>{w('openLiveLead')}</p>
          <div className={css.command}>
            <code><bdi dir="ltr">{SNAPSHOT.command}</bdi></code>
            <Button variant="primary" icon="copy" onPress={async () => toast((await copyText(SNAPSHOT.command)) ? w('copied') : t('copyFailed'))}>{w('openLive')}</Button>
          </div>
        </div>
      )}
      {view.state !== 'fresh' && (
        <details className={css.fallback}>
          <summary>{w('copyFallback')}</summary>
          <p>{w('copyFallbackLead')}</p>
          <pre className={css.instruction} dir="auto" data-instruction>{text}</pre>
          <Button variant="secondary" icon="copy" onPress={async () => toast((await copyText(text)) ? w('copied') : t('copyFailed'))}>{w('copyFallback')}</Button>
        </details>
      )}
    </Sheet>
  )
}
