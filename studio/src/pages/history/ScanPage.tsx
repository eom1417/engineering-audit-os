// #/history/<check>: one check as the ledger recorded it: when, at which commit, its score and its open problems by
// severity (or "not recorded"), the cards closed and found, what happened around it, and the way to the previous and
// next checks and to the comparison with the previous one.
import { useParams } from '@tanstack/react-router'
import { buttonClass } from '../../components/Button'
import { SeverityGlyph } from '../../components/Chip'
import { Go } from '../../components/Go'
import { Icon } from '../../components/Icon'
import { FoldList, Panel, Props, Section, StateMessage } from '../../components/Panel'
import type { StudioData } from '../../data/types'
import { usePrefs } from '../../i18n/prefs'
import { Id, N } from '../../i18n/text'
import { usePageChrome } from '../../shell/chrome'
import { layout, WithData } from '../../shell/Layout'
import { decoded } from '../library/model'
import { EventRow, NoHistory, ScoreTag } from './HistoryPage'
import { historyOf, openKnown, openTotal, rangePath, scanPath, SEVERITIES, type Scan } from './model'
import { useHistoryWords } from './words'
import css from './history.module.css'

const BAR_CLASS = { critical: css.sev4, high: css.sev3, medium: css.sev2, low: css.sev1, info: css.sevOff }

export function SeverityBars({ scan }: { scan: Scan }) {
  const w = useHistoryWords()
  const top = Math.max(1, ...SEVERITIES.map((s) => scan.open[s] ?? 0))
  return (
    <div className={css.sevRows}>
      {SEVERITIES.map((sev) => {
        const n = scan.open[sev]
        return (
          <div key={sev} className={css.sevRow}>
            {sev === 'info' ? <span>{w('info')}</span> : <SeverityGlyph severity={sev} />}
            <span className={css.bar} aria-hidden="true"><i className={BAR_CLASS[sev]} style={{ inlineSize: `${((n ?? 0) / top) * 100}%` }} /></span>
            <span className={css.sevCount}>{typeof n === 'number' ? <N value={n} /> : '—'}</span>
          </div>
        )
      })}
    </div>
  )
}

function ScanBody({ data }: { data: StudioData }) {
  const w = useHistoryWords()
  const { date } = usePrefs()
  const { scanId } = useParams({ strict: false }) as { scanId?: string }
  const history = historyOf(data)
  const scans = history?.scans ?? []
  const at = scans.findIndex((s) => s.id === decoded(scanId ?? ''))
  const scan = at >= 0 ? scans[at] : undefined
  usePageChrome(scan ? w('checkOf', { d: date(scan.at) }) : w('scanNotFound'), { to: '/history', label: w('history') }, data.manifest.project.name)
  if (!history) return <div className={layout.page}><NoHistory data={data} /></div>
  if (!scan) {
    return (
      <div className={layout.page}>
        <Panel><StateMessage title={w('scanNotFound')} sub={w('scanNotFoundSub')}
          action={<div><Go to="/history" className={buttonClass('secondary')}>{w('backToHistory')}</Go></div>} /></Panel>
      </div>
    )
  }
  const previous = at > 0 ? scans[at - 1] : undefined
  const next = at < scans.length - 1 ? scans[at + 1] : undefined
  const open = openTotal(scan)
  const nextAt = next?.at ?? '9999'
  const around = history.events.filter((e) => e.at >= scan.at && e.at < nextAt)
  const notRecorded = <span className={css.tileMuted}>{w('notRecorded')}</span>
  return (
    <div className={layout.page}>
      <header className={css.head}>
        <h1 className={css.title}>{w('checkOf', { d: date(scan.at) })}</h1>
        <div className={css.meta}>
          {scan.event && <span>{w(scan.event === 'baseline' ? 'event_baseline' : scan.event === 'recheck' ? 'event_recheck' : 'event_scan')}</span>}
          {scan.commit && <Id value={scan.commit.slice(0, 12)} />}
          {scan.branch && <Id value={scan.branch} />}
        </div>
      </header>
      <div className={css.columns}>
        <div className={css.col}>
          <Section title={w('check')} id="s-check">
            <Panel pad>
              <Props rows={[
                [w('scanned'), date(scan.at, true)],
                [w('score'), <ScoreTag score={scan.score} />],
                [w('open'), open === null ? notRecorded : <N value={open} />, open === null],
                [w('total'), typeof scan.total === 'number' ? <N value={scan.total} /> : notRecorded, typeof scan.total !== 'number'],
                [w('fixed'), typeof scan.closed === 'number' ? <N value={scan.closed} /> : notRecorded, typeof scan.closed !== 'number'],
                [w('added'), typeof scan.added === 'number' ? <N value={scan.added} /> : notRecorded, typeof scan.added !== 'number'],
                [w('resolved'), typeof scan.resolved === 'number' ? <N value={scan.resolved} /> : notRecorded, typeof scan.resolved !== 'number'],
              ]} />
            </Panel>
          </Section>
          <Section title={w('bySeverity')} id="s-severity">
            <Panel>{openKnown(scan) ? <SeverityBars scan={scan} /> : <StateMessage title={w('notRecorded')} sub={w('unscored')} />}</Panel>
          </Section>
        </div>
        <div className={css.col}>
          <nav className={css.nav} aria-label={w('checks')}>
            {previous && <Go to={scanPath(previous)} className={buttonClass('secondary')}><Icon name="back" />{w('previousCheck')}</Go>}
            {next && <Go to={scanPath(next)} className={buttonClass('secondary')}>{w('nextCheck')}<Icon name="chevron" /></Go>}
            {previous && <Go to={rangePath(previous, scan)} className={buttonClass('primary')}><Icon name="change" />{w('compareWithPrevious')}</Go>}
          </nav>
          <Section title={w('events')} count={around.length} id="s-around">
            <Panel>
              {around.length ? <FoldList items={around} first={6} render={(event) => <EventRow event={event} />} label={w('events')} />
                : <StateMessage title={w('noEvents')} />}
            </Panel>
          </Section>
        </div>
      </div>
    </div>
  )
}

export function ScanPage() {
  return <WithData>{(data) => <ScanBody data={data} />}</WithData>
}
