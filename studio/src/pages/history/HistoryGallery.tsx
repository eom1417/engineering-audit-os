// #/_gallery/history: the history's charts and lists on a fixed history of six checks (the shape of
// tests/fixtures/studio/v2/history.json, grown so every chart has points to draw), so the screen gate shoots the charts
// that a project with one check does not show yet.
import { FoldList, Panel, Section } from '../../components/Panel'
import { usePageChrome } from '../../shell/chrome'
import { layout, PageTitle } from '../../shell/Layout'
import { EventRow, HistoryCharts, ScanRow } from './HistoryPage'
import type { HistoryData, Scan } from './model'
import { useHistoryWords } from './words'
import css from './history.module.css'

const DAYS = ['2026-09-01', '2026-09-08', '2026-09-15', '2026-09-22', '2026-09-29', '2026-10-06']
const SCORES = [0.41, 0.46, 0.52, 0.5, 0.58, 0.63]
const OPEN = [[3, 14, 30, 40, 4], [2, 13, 28, 38, 4], [1, 11, 25, 35, 3], [1, 12, 26, 34, 3], [0, 9, 22, 31, 3], [0, 7, 19, 29, 2]]

export const GALLERY_HISTORY: HistoryData = {
  scans: DAYS.map((day, i): Scan => {
    const [critical, high, medium, low, info] = OPEN[i]
    const open = critical + high + medium + low + info
    return { id: `c${i + 1}a2b3c4d5e`, commit: `c${i + 1}a2b3c4d5e6f7`, branch: 'main', at: `${day}T09:00:00+00:00`, event: i ? 'recheck' : 'baseline',
             score: SCORES[i], open: { critical, high, medium, low, info }, open_total: open, closed: 91 - open, total: 91,
             added: i ? 2 : null, resolved: i ? 4 : null }
  }),
  progress: DAYS.flatMap((day, i) => [{ at: `${day}T09:00:00+00:00`, event: i ? 'recheck' : 'baseline', closed: [0, 5, 13, 12, 22, 30][i], total: 91,
                                       percent: [0, 5, 13, 12, 22, 30][i] / 91 }]),
  events: DAYS.flatMap((day, i) => [
    { at: `${day}T09:00:00+00:00`, kind: 'scan' as const, title: i ? 'recheck' : 'baseline', ref: `c${i + 1}a2b3c4d5e6f7`, count: 91 },
    ...(i ? [{ at: `${day}T08:00:00+00:00`, kind: 'merge' as const, title: 'merged', ref: `eaos/wave-${i}`, count: [0, 5, 13, 12, 22, 30][i] }] : []),
  ]).sort((a, b) => a.at.localeCompare(b.at)),
  cards: [],
}

export function HistoryGalleryPage() {
  const w = useHistoryWords()
  usePageChrome(w('gallery'))
  const history = GALLERY_HISTORY
  return (
    <div className={layout.page}>
      <PageTitle title={w('gallery')} lead={w('lead')} />
      <div className={css.columns}>
        <div className={css.col}><HistoryCharts history={history} project="gallery" /></div>
        <div className={css.col}>
          <Section title={w('checks')} count={history.scans.length} id="g-checks">
            <Panel><FoldList items={[...history.scans].reverse()} first={6} render={(scan) => <ScanRow scan={scan} />} /></Panel>
          </Section>
          <Section title={w('events')} count={history.events.length} id="g-events">
            <Panel><FoldList items={[...history.events].reverse()} first={4} render={(event) => <EventRow event={event} />} /></Panel>
          </Section>
        </div>
      </div>
    </div>
  )
}
