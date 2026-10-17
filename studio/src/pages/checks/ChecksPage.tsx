// Checks (#/checks): the one place of a check. "Now" starts one (the tools it needs first, then one button that opens
// the check's preview) and, once it runs, follows it live on the same page; "Past checks" is every check on record and
// how the project went; "All runs" is every run, check or fix, with the queue. The old addresses (#/scan, #/tools,
// #/runs, #/history) lead here (router.tsx).
import { useNavigate, useSearch } from '@tanstack/react-router'
import { Segmented } from '../../components/Controls'
import { Panel, Skeleton } from '../../components/Panel'
import { useActions } from '../../data/actions/store'
import { useLive } from '../../data/context'
import { runningFlow, useScan } from '../../data/ScanProvider'
import { usePrefs } from '../../i18n/prefs'
import { usePageChrome } from '../../shell/chrome'
import { layout, PageTitle, WithData } from '../../shell/Layout'
import { HistoryContent } from '../history/HistoryPage'
import { RunsBody, SnapshotPanel } from '../runs/RunsPage'
import { blocked, Flow, starting } from '../scan/LiveCheckPage'
import { StartCheck } from '../scan/ToolsPage'
import { useScanWords } from '../scan/words'
import css from '../scan/scan.module.css'

type Tab = 'now' | 'checks' | 'runs'
interface ChecksSearch { tab?: string; flow?: string; stage?: string }

export function ChecksPage() {
  const w = useScanWords()
  const { t } = usePrefs()
  const search = useSearch({ strict: false }) as ChecksSearch
  const navigate = useNavigate()
  const tab: Tab = search.tab === 'checks' || search.tab === 'runs' ? search.tab : 'now'
  usePageChrome(t('checks'))
  const pick = (next: Tab) => void navigate({ to: '/checks', search: next === 'now' ? {} : { tab: next }, replace: true })
  return (
    <div className={[layout.page, css.page].join(' ')} data-tab={tab}>
      <PageTitle title={t('checks')} lead={w('checksLead')} />
      <Segmented label={t('checks')} value={tab} onChange={pick}
        options={[{ id: 'now', label: w('tabNow') }, { id: 'checks', label: w('tabChecks') }, { id: 'runs', label: w('tabRuns') }]} />
      {tab === 'now' ? <Now search={search} /> : tab === 'checks' ? <WithData needs={['history']}>{(data) => <HistoryContent data={data} />}</WithData> : <AllRuns />}
    </div>
  )
}

/** Before a check, its start; while one runs (or was just asked for), the run itself; after, the record of the last. */
function Now({ search }: { search: ChecksSearch }) {
  const w = useScanWords()
  const { mode } = useLive()
  const { all, skew, transport } = useScan()
  const { active } = useActions()
  const navigate = useNavigate()
  const flow = search.flow || runningFlow(all) || 'check'
  const why = blocked(mode, all, flow)
  if (why === 'snapshot') return <SnapshotPanel />
  if (why === 'loading' || !all) return <Panel><Skeleton label={w('loading')} /></Panel>
  const busy = runningFlow(all) !== null || (all.flows.check ? starting(active, all.flows.check) : false)
  const show = (next: { flow?: string; stage?: string }) => void navigate({ to: '/checks', search: { flow: next.flow || flow, stage: next.stage }, replace: true })
  return (
    <>
      {!busy && <StartCheck all={all} />}
      {why === null && <Flow all={all} flow={flow} skew={skew} transport={transport} stage={search.stage || null} show={show} />}
    </>
  )
}

function AllRuns() {
  const { mode } = useActions()
  return mode === 'snapshot' ? <SnapshotPanel /> : <RunsBody />
}
