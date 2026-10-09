// #/history/compare/<a>..<b>: two checks side by side: the score, the open problems in all and by severity, the cards
// closed, each with its change and whether it is better; then the cards closed between the two and those found new.
// What either check did not record stays "not recorded"; with one check there is nothing to compare, and the page says so.
import { useParams } from '@tanstack/react-router'
import type { ReactNode } from 'react'
import { buttonClass } from '../../components/Button'
import { Chip, SeverityGlyph } from '../../components/Chip'
import { Go } from '../../components/Go'
import { Icon } from '../../components/Icon'
import { FoldList, Panel, Section, StateMessage } from '../../components/Panel'
import type { StudioData } from '../../data/types'
import { usePrefs } from '../../i18n/prefs'
import { Id, N, Txt } from '../../i18n/text'
import { usePageChrome } from '../../shell/chrome'
import { layout, WithData } from '../../shell/Layout'
import { decoded } from '../library/model'
import { NoHistory } from './HistoryPage'
import { compare, historyOf, openTotal, parseRange, scanPath, SEVERITIES, type ChangedCard } from './model'
import { useHistoryWords, type HistoryWord } from './words'
import css from './history.module.css'

/** A change with its sign and its word: for problems, fewer is better; for the score and the cards closed, more is. */
function Delta({ value, higherIsBetter }: { value: number | null; higherIsBetter: boolean }) {
  const w = useHistoryWords()
  const { num } = usePrefs()
  if (value === null) return <span className={css.delta} data-tone="same">—</span>
  const tone = value === 0 ? 'same' : (value > 0) === higherIsBetter ? 'good' : 'bad'
  return (
    <span className={css.delta} data-tone={tone}>
      {value !== 0 && <Icon name={value > 0 ? 'up' : 'down'} />}
      <bdi dir="ltr">{value > 0 ? '+' : value < 0 ? '−' : ''}{num(Math.abs(value))}</bdi>
      <span className="sr"> ({w(tone === 'good' ? 'better' : tone === 'bad' ? 'worse' : 'same')})</span>
    </span>
  )
}

function CardRow({ card }: { card: ChangedCard }) {
  const w = useHistoryWords()
  const { date } = usePrefs()
  const state = `state_${card.state}` as HistoryWord
  const body = (
    <span className={css.eventMain}>
      <span className={css.eventTitle}><Txt>{card.title}</Txt></span>
      <span className={css.eventSub}>{card.id && <><Id value={card.id} /> · </>}{card.at ? date(card.at) : ''}</span>
    </span>
  )
  return (
    <div className={css.event}>
      <span className={css.eventIcon} data-kind={card.state === 'done' ? 'merge' : 'scan'}><Icon name={card.state === 'done' ? 'fix' : 'check'} /></span>
      {card.id ? <Go to="/problems" search={{ card: card.id }}>{body}</Go> : body}
      <Chip tone={card.state === 'done' ? 'good' : 'neutral'}>{w(state)}</Chip>
    </div>
  )
}

function CompareBody({ data }: { data: StudioData }) {
  const w = useHistoryWords()
  const { date } = usePrefs()
  const { range } = useParams({ strict: false }) as { range?: string }
  const history = historyOf(data)
  const ids = parseRange(decoded(range ?? ''))
  const found = history && ids ? compare(history, decoded(ids[0]), decoded(ids[1])) : null
  usePageChrome(w('comparing'), { to: '/history', label: w('history') }, data.manifest.project.name)
  if (!history) return <div className={layout.page}><NoHistory data={data} /></div>
  if (!found) {
    return (
      <div className={layout.page}>
        <h1 className={css.title}>{w('comparing')}</h1>
        <Panel><StateMessage icon="change" title={w('compareNeedsTwo')} sub={w('compareNeedsTwoSub')}
          action={<div><Go to="/history" className={buttonClass('secondary')}>{w('backToHistory')}</Go></div>} /></Panel>
      </div>
    )
  }
  const { from, to } = found
  const score = (s: number | null) => (s === null ? w('notRecorded') : <N value={Math.round(s * 100)} />)
  const count = (n: number | null | undefined) => (typeof n === 'number' ? <N value={n} /> : w('notRecorded'))
  const rows: [ReactNode, ReactNode, ReactNode, ReactNode][] = [
    [w('score'), score(from.score), score(to.score), <Delta value={found.score === null ? null : Math.round(found.score * 100)} higherIsBetter />],
    [w('open'), count(openTotal(from)), count(openTotal(to)), <Delta value={found.open} higherIsBetter={false} />],
    ...SEVERITIES.map((sev) => [sev === 'info' ? w('info') : <SeverityGlyph severity={sev} />, count(from.open[sev]), count(to.open[sev]),
      <Delta value={found.severity[sev]} higherIsBetter={false} />] as [ReactNode, ReactNode, ReactNode, ReactNode]),
    [w('fixed'), count(from.closed), count(to.closed), <Delta value={found.closed} higherIsBetter />],
    [w('total'), count(from.total), count(to.total), <Delta value={found.total} higherIsBetter={false} />],
  ]
  return (
    <div className={layout.page}>
      <header className={css.head}>
        <h1 className={css.title}>{w('comparing')}</h1>
        <div className={css.meta}>
          <Go to={scanPath(from)}>{date(from.at)}</Go><Icon name="arrow" /><Go to={scanPath(to)}>{date(to.at)}</Go>
        </div>
      </header>
      <div className={css.columns}>
        <div className={css.col}>
          <Panel>
            <div className={css.chart} data-scroll-x>
              <table className={css.compare}>
                <thead><tr>
                  <th scope="col">{w('measure')}</th>
                  <th scope="col" className={css.n}>{date(from.at)}</th>
                  <th scope="col" className={css.n}>{date(to.at)}</th>
                  <th scope="col" className={css.n}>{w('change')}</th>
                </tr></thead>
                <tbody>{rows.map(([label, a, b, d], i) => (
                  <tr key={i}><th scope="row">{label}</th><td className={css.n}>{a}</td><td className={css.n}>{b}</td><td className={css.n}>{d}</td></tr>
                ))}</tbody>
              </table>
            </div>
          </Panel>
        </div>
        <div className={css.col}>
          <Section title={w('closedBetween')} count={found.closedBetween.length} id="s-closed">
            <Panel>
              {found.closedBetween.length ? <FoldList items={found.closedBetween} first={6} render={(card) => <CardRow card={card} />} label={w('closedBetween')} />
                : <StateMessage title={w('noneClosed')} />}
            </Panel>
          </Section>
          {found.appeared && found.appeared.length > 0 && (
            <Section title={w('appeared')} count={found.appeared.length} id="s-appeared">
              <Panel>
                <FoldList items={found.appeared} first={6} render={(card) => <CardRow card={card} />} label={w('appeared')} />
                <p className={css.note}>{w('appearedNote')}</p>
              </Panel>
            </Section>
          )}
        </div>
      </div>
    </div>
  )
}

export function ComparePage() {
  return <WithData>{(data) => <CompareBody data={data} />}</WithData>
}
