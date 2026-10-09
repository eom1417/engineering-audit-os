// #/quality: how far EAOS's analysis of this project can be trusted (STUDIO-COMPLETE: "EAOS quality"). The detectors
// that worked here with their precision and recall on EAOS's labelled set and whether their findings are shown or held
// back; what EAOS measured for this report (studio/coverage.json); and the plan's indicators that judge the analysis.
// Every number is read from the data; what is not measured says so, and those states are counted on the page.
import type { ReactNode } from 'react'
import { Chip, type Tone } from '../../components/Chip'
import { FoldList, Panel, Section, StateMessage } from '../../components/Panel'
import type { StudioData } from '../../data/types'
import { usePrefs } from '../../i18n/prefs'
import { Id, N, Txt } from '../../i18n/text'
import { usePageChrome } from '../../shell/chrome'
import { layout, MissingBanner, PageTitle, WithData } from '../../shell/Layout'
import { useCoverageRow, useLazySection, type CoverageRow } from '../library/model'
import { usePhone } from '../SystemMap'
import { active, byCapability, nameIn, idle, notMeasured, qualityOf, statusOf, tally, type Detector, type Status } from './model'
import { QUALITY_WORDS, useQualityWords, type QualityWord } from './words'
import css from './quality.module.css'

const STATUS_TONE: Record<Status, Tone> = { meets_bar: 'good', below_bar: 'warning', not_measured: 'neutral' }
const STATE_TONE: Record<string, Tone> = { measured: 'good', empty: 'good', partial: 'warning', not_measured: 'neutral', failed: 'critical' }

/** A ratio from 0 to 1 as a bar with its number, and the bar's threshold marked; or "not measured yet". */
function Meter({ label, value, threshold, sub }: { label: string; value: number | null; threshold?: number; sub?: string }) {
  const w = useQualityWords()
  const { num } = usePrefs()
  return (
    <div className={css.meter}>
      <span className={css.meterLabel}>{label}</span>
      {value === null ? <span className={css.unmeasured}>{w('notMeasuredYet')}</span> : (
        <>
          <span className={css.track} aria-hidden="true">
            <i style={{ inlineSize: `${value * 100}%` }} data-low={threshold !== undefined && value < threshold ? '' : undefined} />
            {threshold !== undefined && <b style={{ insetInlineStart: `${threshold * 100}%` }} />}
          </span>
          <span className={css.meterValue}><bdi dir="ltr">{num(Math.round(value * 100))}%</bdi></span>
        </>
      )}
      {sub && <span className={css.meterSub}>{sub}</span>}
    </div>
  )
}

function DetectorRow({ d, bar }: { d: Detector; bar: { precision?: number; recall?: number; judged?: number } }) {
  const w = useQualityWords()
  const { lang } = usePrefs()
  const status = statusOf(d)
  const judged = d.judged ?? 0
  const precisionSub = judged === 0 ? w('noCases') : bar.judged && judged < bar.judged ? w('tooFew', { n: judged, b: bar.judged }) : w('judgedN', { n: judged })
  const here = [d.here?.shown ? w('hereShown', { n: d.here.shown }) : '', d.here?.withheld ? w('hereWithheld', { n: d.here.withheld }) : '',
    d.here?.facts ? w('hereFacts', { n: d.here.facts }) : ''].filter(Boolean)
  return (
    <div className={css.detector}>
      <div className={css.detHead}>
        <span className={css.detName}><Txt>{nameIn(d, lang)}</Txt></span>
        <Chip tone={STATUS_TONE[status]}>{w(`status_${status}`)}</Chip>
      </div>
      <div className={css.meters}>
        <Meter label={w('precision')} value={d.precision.value} threshold={bar.precision} sub={precisionSub} />
        <Meter label={w('recall')} value={d.recall.value} threshold={bar.recall} />
      </div>
      {(here.length > 0 || d.project) && (
        <div className={css.detMeta}>
          {here.length > 0 && <span>{here.join(' · ')}</span>}
          {d.project && (d.project.tp + d.project.fp > 0) && <span>{w('onThisProject', { tp: d.project.tp, fp: d.project.fp })}</span>}
        </div>
      )}
    </div>
  )
}

function Tile({ label, value, sub }: { label: string; value: ReactNode; sub?: ReactNode }) {
  return (
    <Panel className={css.tile}>
      <span className={css.tileLabel}>{label}</span>
      <span className={css.tileValue}>{value}</span>
      {sub && <span className={css.tileSub}>{sub}</span>}
    </Panel>
  )
}

function CoverageList({ data }: { data: StudioData }) {
  const w = useQualityWords()
  const coverage = useLazySection<{ sections?: CoverageRow[] }>(data, 'coverage')
  const phone = usePhone()
  if (coverage.kind === 'loading') return null
  const rows = coverage.kind === 'ready' ? coverage.data.sections ?? [] : []
  if (!rows.length) return <Panel><StateMessage title={w('noCoverage')} /></Panel>
  const count = (states: string[]) => rows.filter((r) => states.includes(r.state)).length
  const order = (r: CoverageRow) => ({ not_measured: 0, failed: 0, partial: 1 } as Record<string, number>)[r.state] ?? 2
  const sorted = [...rows].sort((a, b) => order(a) - order(b))
  return (
    <Section title={w('coverage')} count={rows.length} id="s-coverage">
      <p className={css.lead}>{w('coverageLead')} <span className="num">{w('coverageCounts', { m: count(['measured', 'empty']), p: count(['partial']), n: count(['not_measured', 'failed']) })}</span></p>
      <Panel>
        <FoldList items={sorted} first={phone ? 4 : 8} label={w('coverage')} render={(row) => {
          const name = `sec_${row.section}` as QualityWord
          const state = `state_${row.state}` as QualityWord
          return (
            <div className={css.covRow}>
              <div className={css.detHead}>
                <span className={css.detName}>{name in QUALITY_WORDS ? w(name) : <Id value={row.section} />}</span>
                <Chip tone={STATE_TONE[row.state] ?? 'neutral'}>{state in QUALITY_WORDS ? w(state) : row.state}</Chip>
              </div>
              {row.detail && <span className={css.covDetail}><Txt>{row.detail}</Txt>{row.step && <> · <Id value={row.step} /></>}</span>}
            </div>
          )
        }} />
      </Panel>
    </Section>
  )
}

function QualityBody({ data }: { data: StudioData }) {
  const w = useQualityWords()
  const { lang } = usePrefs()
  const phone = usePhone()
  usePageChrome(w('quality'), undefined, data.manifest.project.name)
  const quality = qualityOf(data)
  const row = useCoverageRow(data, 'quality')
  if (!quality) {
    return (
      <div className={layout.page}>
        <PageTitle title={w('quality')} lead={w('lead')} />
        <Panel><StateMessage title={w('noQuality')} sub={<>{row?.detail && <Txt>{row.detail}</Txt>}{row?.step && <> · <Id value={row.step} /></>}</>} /></Panel>
        <CoverageList data={data} />
      </div>
    )
  }
  const bar = quality.bar ?? {}
  const sums = tally(quality.detectors)
  const here = active(quality.detectors)
  const others = idle(quality.detectors)
  const projects = quality.labelled?.projects ?? []
  return (
    <div className={layout.page}>
      <MissingBanner data={data} />
      <PageTitle title={w('quality')} lead={w('lead')} />
      <div className={css.tiles}>
        <Tile label={w('shownHere')} value={<N value={sums.shown} />} sub={w('shownSub', { n: sums.meeting })} />
        <Tile label={w('heldBack')} value={<N value={sums.withheld} />} sub={w('heldSub', { n: sums.under + sums.unmeasured })} />
        <Tile label={w('labelledSet')} value={quality.labelled?.items != null ? <N value={quality.labelled.items} /> : <span className={css.unmeasured}>{w('notMeasuredYet')}</span>}
          sub={<>{w('labelledSub', { n: projects.length })}{quality.labelled?.this_project && <> · {w('thisProjectLabelled')}</>}</>} />
        <Tile label={w('notMeasuredYet')} value={<N value={notMeasured(quality)} />} sub={w('notMeasuredSub')} />
      </div>
      <div className={css.columns}>
        <div className={css.col}>
          <Section title={w('detectorsHere')} count={here.length} id="s-detectors">
            <p className={css.lead}>{w('detectorsLead', { p: Math.round((bar.precision ?? 0) * 100), r: Math.round((bar.recall ?? 0) * 100), j: bar.judged ?? 0 })}</p>
            <Panel><FoldList items={here} first={phone ? 4 : 8} label={w('detectorsHere')} render={(d) => <DetectorRow d={d} bar={bar} />} /></Panel>
          </Section>
          {others.length > 0 && (
            <Section title={w('otherDetectors')} count={others.length} id="s-others">
              <Panel><FoldList items={others} first={3} label={w('otherDetectors')} render={(d) => <DetectorRow d={d} bar={bar} />} /></Panel>
            </Section>
          )}
        </div>
        <div className={css.col}>
          <CoverageList data={data} />
          <Section title={w('indicators')} id="s-indicators">
            <p className={css.lead}>{w('indicatorsLead')}</p>
            <FoldList items={byCapability(quality)} first={phone ? 2 : 8} label={w('indicators')} render={({ capability, indicators }) => (
              <Panel className={css.capability} label={nameIn(capability, lang)}>
                <div className={css.capHead}>
                  <span className={css.detName}><Txt>{nameIn(capability, lang)}</Txt></span>
                  <Meter label={w('measuredOf', { m: capability.measured ?? 0, n: capability.indicators ?? indicators.length })} value={capability.value.value} />
                </div>
                <FoldList items={indicators} first={phone ? 3 : 4} label={nameIn(capability, lang)} render={(i) => (
                  <div className={css.indicator}>
                    <span className={css.indName}><Id value={i.id} /> <Txt>{nameIn(i, lang)}</Txt>{i.how === 'recorded' && <span className={css.meterSub}> · {w('recorded')}</span>}</span>
                    {i.value.value === null ? <Chip>{w('notMeasuredYet')}</Chip>
                      : <span className={css.indValue} data-low={i.value.value < i.target ? '' : undefined}>
                        <bdi dir="ltr"><N value={Math.round(i.value.value * 100)} />%</bdi> <span className={css.meterSub}>{w('target', { t: '' })}<bdi dir="ltr">{Math.round(i.target * 100)}%</bdi></span>
                      </span>}
                  </div>
                )} />
              </Panel>
            )} />
            <p className={css.note}>{w('asOf')}{quality.measured_at && <> <span className="num">({quality.measured_at})</span></>}</p>
          </Section>
        </div>
      </div>
    </div>
  )
}

export function QualityPage() {
  return <WithData>{(data) => <QualityBody data={data} />}</WithData>
}
