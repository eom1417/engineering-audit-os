// #/history: "Are we getting better?" Every check the ledger recorded, the score over the checks, the open problems by
// severity, the fixes taken in, and what happened, from studio/history.json. A chart appears only with two points to
// draw between; one check shows its numbers and the designed "one check so far" state. A report without the section
// shows its coverage row: why it is missing and which step writes it.
import { useState, type ReactNode } from 'react'
import { buttonClass } from '../../components/Button'
import { DirectAction } from '../../command/Direct'
import { Go } from '../../components/Go'
import { Icon, type IconName } from '../../components/Icon'
import { FoldList, Panel, RowLink, Section, StateMessage } from '../../components/Panel'
import type { StudioData } from '../../data/types'
import { usePrefs } from '../../i18n/prefs'
import { Id, N, Txt } from '../../i18n/text'
import { usePageChrome } from '../../shell/chrome'
import { layout, MissingBanner, PageTitle, WithData } from '../../shell/Layout'
import { useCoverageRow } from '../library/model'
import { LineChart, StackedChart } from './Charts'
import { historyOf, last, openKnown, openTotal, rangePath, scanPath, scored, type HistoryData, type HistoryEvent, type Scan } from './model'
import { useHistoryWords } from './words'
import css from './history.module.css'

export function ScoreTag({ score }: { score: number | null }) {
  const w = useHistoryWords()
  if (score === null) return <span className={css.tileMuted}>{w('notRecorded')}</span>
  return <span className={css.scoreTag}><N value={Math.round(score * 100)} /><small>/100</small></span>
}

function Tile({ label, children }: { label: string; children: ReactNode }) {
  return <Panel className={css.tile}><span className={css.tileLabel}>{label}</span><span className={css.tileValue}>{children}</span></Panel>
}

const EVENT_ICON: Record<HistoryEvent['kind'], IconName> = { scan: 'verify', batch: 'fix', merge: 'branch', decision: 'inbox', release: 'flow' }

export function EventRow({ event }: { event: HistoryEvent }) {
  const w = useHistoryWords()
  const { date } = usePrefs()
  const title = event.kind === 'batch' ? w('event_batch', { n: event.title.replace(/\D+/g, '') })
    : event.title === 'baseline' || event.title === 'recheck' || event.title === 'merged' ? w(`event_${event.title}`) : event.kind === 'scan' ? w('event_scan') : event.title
  const count = typeof event.count === 'number'
    ? event.kind === 'scan' ? w('cardsN', { n: event.count }) : event.kind === 'batch' ? w('fixesN', { n: event.count }) : w('closedN', { n: event.count })
    : null
  return (
    <div className={css.event}>
      <span className={css.eventIcon} data-kind={event.kind}><Icon name={EVENT_ICON[event.kind]} /></span>
      <span className={css.eventMain}>
        <span className={css.eventTitle}><Txt>{title}</Txt></span>
        <span className={css.eventSub}>{date(event.at, true)}{event.ref && <> · <Id value={event.ref.length === 40 ? event.ref.slice(0, 12) : event.ref} /></>}</span>
      </span>
      {count && <span className={css.eventEnd}>{count}</span>}
    </div>
  )
}

export function ScanRow({ scan }: { scan: Scan }) {
  const w = useHistoryWords()
  const { date } = usePrefs()
  const open = openTotal(scan)
  return (
    <RowLink to={scanPath(scan)} icon="verify" title={w('checkOf', { d: date(scan.at) })}
      sub={<>{scan.commit ? <Id value={scan.commit.slice(0, 12)} /> : w('notRecorded')}{open !== null && <> · {w('open')} <N value={open} /></>}</>}
      end={<ScoreTag score={scan.score} />} />
  )
}

/** The headline of the score chart: the change since the previous scored check, in one sentence. */
function scoreAnswer(w: ReturnType<typeof useHistoryWords>, scans: Scan[]): string {
  const [a, b] = scans.slice(-2).map((s) => Math.round((s.score ?? 0) * 100))
  return b > a ? w('scoreUp', { n: b - a }) : b < a ? w('scoreDown', { n: a - b }) : w('scoreSame')
}

/** The charts of a history, each only when it has two points; else the designed state of one check. */
export function HistoryCharts({ history, project }: { history: HistoryData; project: string }) {
  const w = useHistoryWords()
  const { lang, num } = usePrefs()
  const withScore = scored(history.scans)
  const withOpen = history.scans.filter(openKnown)
  const progress = history.progress ?? []
  const pct = (v: number) => `${num(Math.round(v * 100))}%`
  return (
    <>
      {withScore.length >= 2 ? (
        <Section title={w('scoreTitle')} id="s-score">
          <Panel className={css.chartPanel}>
            <p className={css.answer}>{scoreAnswer(w, withScore)}</p>
            <LineChart values={withScore.map((s) => ({ at: s.at, value: s.score! }))} format={(v) => num(Math.round(v * 100))}
              ticks={[{ at: 0, label: '0' }, { at: 0.5, label: '50' }, { at: 1, label: '100' }]}
              label={w('scoreAria', { n: withScore.length, a: Math.round(withScore[0].score! * 100), b: Math.round(last(withScore)!.score! * 100) })} />
          </Panel>
        </Section>
      ) : (
        <Panel>
          <StateMessage icon="clock" title={history.scans.length < 2 ? w('oneScan') : w('unscored')}
            sub={<>{history.scans.length < 2 ? w('oneScanSub') : (history.missing ?? []).map((m) => m.detail[lang]).join(' ')}
              {history.scans.length >= 2 && history.missing?.[0] && <> · <Id value={history.missing[0].step} /></>}</>}
            action={history.scans.length < 2 ? <div><DirectAction request={{ action: 'audit', inputs: { fresh: true } }} label={w('checkAgain')} copy={{ request: w('checkAgainRequest', { p: project }), tool: 'audit' }} /></div> : undefined} />
        </Panel>
      )}
      {withOpen.length >= 2 && (
        <Section title={w('openTitle')} id="s-open">
          <Panel className={css.chartPanel}>
            <StackedChart scans={withOpen} label={w('openAria', { n: withOpen.length, a: openTotal(withOpen[0]) ?? 0, b: openTotal(last(withOpen)!) ?? 0 })} />
          </Panel>
        </Section>
      )}
      {progress.filter((p) => p.percent !== null).length >= 2 && (
        <Section title={w('progressTitle')} id="s-progress">
          <Panel className={css.chartPanel}>
            <p className={css.chartLead}>{w('progressLead')}</p>
            <LineChart values={progress.filter((p) => p.percent !== null).map((p) => ({ at: p.at, value: p.percent! }))} format={pct}
              ticks={[{ at: 0, label: '0%' }, { at: 0.5, label: '50%' }, { at: 1, label: '100%' }]}
              label={w('progressAria', { n: progress.length, a: Math.round((progress[0].percent ?? 0) * 100), b: Math.round((last(progress)!.percent ?? 0) * 100) })} />
          </Panel>
        </Section>
      )}
    </>
  )
}

function ComparePicker({ scans }: { scans: Scan[] }) {
  const w = useHistoryWords()
  const { date } = usePrefs()
  const [from, setFrom] = useState(scans[0].id)
  const [to, setTo] = useState(last(scans)!.id)
  const a = scans.find((s) => s.id === from)!, b = scans.find((s) => s.id === to)!
  const option = (s: Scan) => <option key={s.id} value={s.id}>{date(s.at, true)} · {s.id}</option>
  return (
    <div className={css.pickers}>
      <label className={css.picker}>{w('from')}<select className={css.select} value={from} onChange={(e) => setFrom(e.target.value)}>{scans.map(option)}</select></label>
      <label className={css.picker}>{w('to')}<select className={css.select} value={to} onChange={(e) => setTo(e.target.value)}>{scans.map(option)}</select></label>
      {from !== to && <Go to={rangePath(a, b)} className={buttonClass('primary')}><Icon name="change" />{w('compare')}</Go>}
    </div>
  )
}

/** A report without the history section: its coverage row says why, and which step writes it. */
export function NoHistory({ data }: { data: StudioData }) {
  const w = useHistoryWords()
  const row = useCoverageRow(data, 'history')
  return <Panel><StateMessage title={w('oneScan')} sub={<>{row?.detail ? <Txt>{row.detail}</Txt> : w('oneScanSub')}{row?.step && <> · <Id value={row.step} /></>}</>} /></Panel>
}

function HistoryBody({ data }: { data: StudioData }) {
  const w = useHistoryWords()
  usePageChrome(w('history'), undefined, data.manifest.project.name)
  const history = historyOf(data)
  if (!history || !history.scans.length) {
    return <div className={layout.page}><PageTitle title={w('history')} lead={w('lead')} /><NoHistory data={data} /></div>
  }
  const now = last(history.scans)!
  const open = openTotal(now)
  const events = [...history.events].reverse()
  return (
    <div className={layout.page}>
      <MissingBanner data={data} />
      <PageTitle title={w('history')} lead={w('lead')} />
      <div className={css.tiles}>
        <Tile label={w('checks')}><N value={history.scans.length} /></Tile>
        <Tile label={w('scoreNow')}><ScoreTag score={now.score} /></Tile>
        <Tile label={w('openNow')}>{open === null ? <span className={css.tileMuted}>{w('notRecorded')}</span> : <N value={open} />}</Tile>
        <Tile label={w('fixed')}>{typeof now.closed === 'number' && typeof now.total === 'number'
          ? <span className={css.scoreTag}><N value={now.closed} /><small>/ <N value={now.total} /></small></span>
          : <span className={css.tileMuted}>{w('notRecorded')}</span>}</Tile>
      </div>
      <div className={css.columns}>
        <div className={css.col}>
          <HistoryCharts history={history} project={data.manifest.project.name} />
        </div>
        <div className={css.col}>
          <Section title={w('checks')} count={history.scans.length} id="s-checks">
            <Panel>
              <FoldList items={[...history.scans].reverse()} first={5} render={(scan) => <ScanRow scan={scan} />} label={w('checks')} />
            </Panel>
            {history.scans.length >= 2 && (
              <Panel label={w('compareTwo')}><ComparePicker scans={history.scans} /></Panel>
            )}
          </Section>
          <Section title={w('events')} count={events.length} id="s-events">
            <Panel>
              {events.length ? <FoldList items={events} first={6} render={(event) => <EventRow event={event} />} label={w('events')} />
                : <StateMessage title={w('noEvents')} />}
            </Panel>
          </Section>
        </div>
      </div>
    </div>
  )
}

export function HistoryPage() {
  return <WithData>{(data) => <HistoryBody data={data} />}</WithData>
}
