// The persistent branch chip in the header and its switcher (NS46.T18): the analysis branch (or a named detached
// HEAD), which opens the list of local branches to analyse instead and a link to #/branches. Choosing changes what the
// Studio analyses, never the person's checkout, and is refused while a run is queued or working (never retargeted).
import { useEffect, useState } from 'react'
import { Button } from '../components/Button'
import { Chip } from '../components/Chip'
import { Go } from '../components/Go'
import { Icon } from '../components/Icon'
import { Sheet, SheetLead } from '../components/Sheet'
import { type BranchContext, type BranchRow, type Run } from '../data/actions/types'
import { useActions } from '../data/actions/store'
import { useStudio } from '../data/context'
import { Id } from '../i18n/text'
import { useBranchLive } from './live'
import { refusal, RescanStatus, SelectError, type Refusal } from './ScanSheet'
import { useBranchWords } from './words'
import css from './branches.module.css'

/** The analysis branch's name as the header shows it, from the live context or the report. */
export function useAnalysisName(): { name: string | null; detached: boolean; commit: string | null } {
  const { context } = useBranchLive()
  const data = useStudio()
  if (context) {
    return { name: context.analysis.branch, detached: context.analysis.branch === null && context.checkout.detached, commit: context.checkout.commit }
  }
  const scanned = data?.head?.scanned ?? data?.manifest.scanned
  return { name: scanned?.branch ?? null, detached: Boolean(scanned?.detached), commit: scanned?.commit ?? null }
}

export function BranchChip({ onPress }: { onPress: () => void }) {
  const w = useBranchWords()
  const { name, detached, commit } = useAnalysisName()
  const label = name ?? (detached ? w('detached', { c: (commit ?? '').slice(0, 7) }) : null)
  if (!label) return null
  return (
    <button type="button" className={css.branchChip} onClick={onPress} aria-label={w('branchChip', { b: label })} data-open="branches">
      <Icon name="branch" /><bdi dir="ltr" className={css.branchName}>{label}</bdi><Icon name="chevronDown" />
    </button>
  )
}

/** The four branches the Studio never mixes up, labelled in plain words; differences are said out loud. */
export function ContextRows({ context }: { context: BranchContext }) {
  const w = useBranchWords()
  const checkout = context.checkout.branch ?? (context.checkout.detached ? w('detached', { c: (context.checkout.commit ?? '').slice(0, 12) }) : '—')
  const analysis = context.analysis.branch ?? w('detachedShort')
  const notes: string[] = []
  if (context.analysis.branch && context.checkout.branch !== context.analysis.branch) notes.push(w('contextDiffers', { a: analysis, c: checkout }))
  if (context.report.branch && context.analysis.branch && context.report.branch !== context.analysis.branch) notes.push(w('reportDiffers', { r: context.report.branch, a: analysis }))
  return (
    <>
      <dl className={css.context} data-context>
        <div><dt>{w('checkout')}</dt><dd><bdi dir="ltr">{checkout}</bdi></dd></div>
        <div><dt>{w('analysis')}</dt><dd><bdi dir="ltr">{analysis}</bdi></dd></div>
        <div><dt>{w('reportOf')}</dt><dd><bdi dir="ltr">{context.report.branch ?? (context.report.detached ? w('detachedShort') : '—')}</bdi></dd></div>
      </dl>
      {notes.map((note) => <p key={note} className={css.note}>{note}</p>)}
    </>
  )
}

/** Choose `name` as the analysis branch, optionally with a scan; the result and any refusal in plain words. */
export function useSelect() {
  const live = useBranchLive()
  const actions = useActions()
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<Refusal | null>(null)
  const [scan, setScan] = useState<Run | null>(null)
  async function choose(name: string, withScan: boolean, expectedTip?: string | null) {
    if (!live.api) return
    setBusy(name + (withScan ? ':scan' : '')); setError(null)
    try {
      const done = await live.api.select(name, withScan, expectedTip)
      setScan(done.scan)
      await Promise.all([live.refresh(), actions.refresh()])
    } catch (problem) {
      setError(refusal(problem))
    } finally { setBusy(null) }
  }
  const followed = scan ? actions.runs.find((r) => r.id === scan.id) ?? scan : null
  return { busy, error, scan: followed, choose }
}

export function BranchSwitcher({ isOpen, onOpenChange }: { isOpen: boolean; onOpenChange: (open: boolean) => void }) {
  const w = useBranchWords()
  const live = useBranchLive()
  const [rows, setRows] = useState<BranchRow[] | null>(null)
  const [failed, setFailed] = useState(false)
  const select = useSelect()
  useEffect(() => {
    if (!isOpen || !live.api) return
    let on = true
    live.api.inventory().then((inv) => { if (on) { setRows(inv.branches.filter((b) => b.kind === 'local')); setFailed(false) } }, () => { if (on) setFailed(true) })
    return () => { on = false }
  }, [isOpen, live.api, live.context?.analysis.branch])
  const { name } = useAnalysisName()
  return (
    <Sheet isOpen={isOpen} onOpenChange={onOpenChange} title={w('switchBranch')}>
      <div className={[css.tall, css.drawerBody].join(' ')}>
      {live.context && <ContextRows context={live.context} />}
      {!live.api && <SheetLead>{w('readOnlySnapshot')}</SheetLead>}
      {live.api && <SheetLead>{w('selectLead')}</SheetLead>}
      <SelectError error={select.error} />
      <RescanStatus run={select.scan} />
      {failed && <p role="alert" className={css.error}>{w('whyOffline')}</p>}
      {live.api && rows && (
        <ul className={css.switchList} aria-label={w('switchBranch')}>
          {rows.map((row) => {
            const current = row.name === name
            return (
              <li key={row.ref} className={css.switchRow} data-branch={row.name}>
                <span className={css.switchMain}>
                  <Id value={row.name} />
                  <span className={css.badges}>
                    {current && <Chip tone="accent">{w('analysis')}</Chip>}
                    {row.roles.includes('checkout') && <Chip>{w('checkout')}</Chip>}
                    {row.protected && <Chip tone="warning">{w('protected')}</Chip>}
                  </span>
                </span>
                {!current && <span className={css.switchActions}>
                  <Button variant="secondary" busy={select.busy === row.name} onPress={() => void select.choose(row.name, false, row.tip)}>{w('useForAnalysis')}</Button>
                  <Button variant="primary" busy={select.busy === row.name + ':scan'} onPress={() => void select.choose(row.name, true, row.tip)}>{w('useForAnalysisScan')}</Button>
                </span>}
              </li>
            )
          })}
        </ul>
      )}
      <span onClick={() => onOpenChange(false)} className={css.allLinkWrap}><Go to="/branches" className={css.allLink}><Icon name="branch" />{w('allBranchesLink')}</Go></span>
      </div>
    </Sheet>
  )
}
