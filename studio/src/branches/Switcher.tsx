// The persistent branch chip in the header and its switcher (NS46.T18): the analysis branch (or a named detached
// HEAD), which opens the person's own branches to analyse instead (main listed, never analysed or fixed from here), the
// EAOS work branches still waiting for a decision apart, and a link to #/branches. Choosing changes what the Studio
// analyses, never the person's checkout, and is refused while a run is queued or working (never retargeted).
import { useEffect, useState } from 'react'
import { Button } from '../components/Button'
import { Chip } from '../components/Chip'
import { Go } from '../components/Go'
import { Icon } from '../components/Icon'
import { Sheet, SheetLead } from '../components/Sheet'
import { type BranchContext, type BranchRow } from '../data/actions/types'
import { useActions } from '../data/actions/store'
import { useCommandMaybe } from '../command/command'
import { useStudio } from '../data/context'
import { Id } from '../i18n/text'
import { useBranchLive } from './live'
import { canWorkOn, pickerBranches } from './model'
import { refusal, SelectError, type Refusal } from './ScanSheet'
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
  // the usual case, said once: the open branch, the analysed one and the report's are the same
  if (context.analysis.branch && context.checkout.branch === context.analysis.branch && (!context.report.branch || context.report.branch === context.analysis.branch)) {
    return <p className={css.sameBranch} data-context="same">{w('sameBranch', { b: '\u2068' + context.analysis.branch + '\u2069' })}</p>
  }
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

/** Choose `name` as the analysis branch, optionally followed by a check: the branch is chosen first, then the check's
 * preview opens (PreviewSheet), where its paths and mode are chosen as for any check. Any refusal in plain words. */
export function useSelect() {
  const live = useBranchLive()
  const actions = useActions()
  const command = useCommandMaybe()
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<Refusal | null>(null)
  async function choose(name: string, withScan: boolean, expectedTip?: string | null) {
    if (!live.api) return
    setBusy(name + (withScan ? ':scan' : '')); setError(null)
    try {
      await live.api.select(name, false, expectedTip)
      await Promise.all([live.refresh(), actions.refresh()])
      if (withScan) command?.open({ action: 'audit', inputs: { fresh: true } })
    } catch (problem) {
      setError(refusal(problem))
    } finally { setBusy(null) }
  }
  return { busy, error, choose }
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
    live.api.inventory().then((inv) => { if (on) { setRows(inv.branches); setFailed(false) } }, () => { if (on) setFailed(true) })
    return () => { on = false }
  }, [isOpen, live.api, live.context?.analysis.branch])
  const { name } = useAnalysisName()
  const picked = rows ? pickerBranches(rows) : null
  return (
    <Sheet isOpen={isOpen} onOpenChange={onOpenChange} title={w('switchBranch')}>
      <div className={[css.tall, css.drawerBody].join(' ')}>
      {live.context && <ContextRows context={live.context} />}
      {!live.api && <SheetLead>{w('readOnlySnapshot')}</SheetLead>}
      {live.api && <SheetLead>{w('selectLead')}</SheetLead>}
      <SelectError error={select.error} />
      {failed && <p role="alert" className={css.error}>{w('whyOffline')}</p>}
      {live.api && picked && (
        <ul className={css.switchList} aria-label={w('yourBranches')}>
          {picked.mine.map((row) => {
            const current = row.name === name
            const workable = canWorkOn(row)
            return (
              <li key={row.ref} className={css.switchRow} data-branch={row.name}>
                <span className={css.switchMain}>
                  <Id value={row.name} />
                  <span className={css.badges}>
                    {current && <Chip tone="accent">{w('analysis')}</Chip>}
                    {row.roles.includes('checkout') && <Chip>{w('checkout')}</Chip>}
                    {row.protected && <Chip tone="warning">{workable ? w('protected') : w('protectedNoWork')}</Chip>}
                  </span>
                </span>
                {!current && workable && <span className={css.switchActions}>
                  <Button variant="secondary" busy={select.busy === row.name} onPress={() => void select.choose(row.name, false, row.tip)}>{w('useForAnalysis')}</Button>
                  <Button variant="primary" busy={select.busy === row.name + ':scan'} onPress={() => void select.choose(row.name, true, row.tip)}>{w('useForAnalysisScan')}</Button>
                </span>}
              </li>
            )
          })}
        </ul>
      )}
      {live.api && picked && picked.waiting.length > 0 && (
        <section data-branches="waiting">
          <h3 className={css.switchHead}>{w('waitingWork')}</h3>
          <p className={css.muted}>{w('waitingWorkLead')}</p>
          <ul className={css.switchList} aria-label={w('waitingWork')}>
            {picked.waiting.map((row) => (
              <li key={row.ref} className={css.switchRow} data-branch={row.name}>
                <span className={css.switchMain}><Id value={row.name} /></span>
                <span className={css.switchActions} onClick={() => onOpenChange(false)}>
                  <Go to="/branches" search={{ b: row.id }} className={css.allLink}>{w('openBranch')}</Go>
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}
      <span onClick={() => onOpenChange(false)} className={css.allLinkWrap}><Go to="/branches" className={css.allLink}><Icon name="branch" />{w('allBranchesLink')}</Go></span>
      </div>
    </Sheet>
  )
}
