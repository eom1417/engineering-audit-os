// A path as a sequence diagram (the person or caller, then the lanes it crosses as lifelines, its links as messages
// in the order EAOS walked them) and as a linear list of steps, which reads better on a phone and serves screen
// readers. Both come from model.sequence(); neither adds a message the data does not hold.
import { useState } from 'react'
import { Button as AriaButton } from 'react-aria-components'
import { Button } from '../../components/Button'
import { usePrefs } from '../../i18n/prefs'
import { Id, N } from '../../i18n/text'
import { sequence, where, type CodePath, type Index, type Participant, type PathsData } from './model'
import { GAP_WORD, HOW_WORD, LANE_WORD, usePathWords, type PathWord } from './words'
import css from './paths.module.css'

const COL = 156
const NUM = 40
const HEADER = 46
const ROW = 48

function participantWord(p: Participant, path: CodePath): PathWord {
  return p === 'actor' ? (path.surface === 'page' ? 'actor' : 'caller') : LANE_WORD[p]
}

function short(text: string, room: number): string {
  return text.length <= room ? text : '…' + text.slice(-(room - 1))
}

export function SequenceDiagram({ data, index, path, selected, onSelect }:
  { data: PathsData; index: Index; path: CodePath; selected?: string; onSelect: (id: string) => void }) {
  const w = usePathWords()
  const { participants, messages } = sequence(data, path, index)
  const x = (p: Participant) => NUM + participants.indexOf(p) * COL + COL / 2
  const width = NUM + participants.length * COL + 12
  const height = HEADER + messages.length * ROW + 24
  return (
    <div className={css.seqWrap} data-scroll-x="">
      <svg className={css.seqSvg} width={width} height={height} viewBox={`0 0 ${width} ${height}`} direction="ltr" role="group"
        aria-label={w('sequenceAria', { t: path.title, n: messages.length })}>
        {participants.map((p) => (
          <g key={p}>
            <line x1={x(p)} y1={HEADER - 6} x2={x(p)} y2={height - 8} className={css.life} />
            <rect x={x(p) - COL / 2 + 8} y={8} width={COL - 16} height={30} rx={8} className={css.partBox} />
            <text x={x(p)} y={28} textAnchor="middle" className={css.partText}>{w(participantWord(p, path))}</text>
          </g>
        ))}
        {messages.map((m, i) => {
          const y = HEADER + i * ROW + ROW / 2 + 6
          const a = x(m.from)
          const b = x(m.to)
          const node = index.node.get(m.toNode)
          const label = node ? (m.gap ? `? ${node.reason === 'trace_stopped' ? w('callsNotResolved', { n: Number(node.detail) || node.items.length }) : node.label}` : node.label) : ''
          const self = a === b
          const room = Math.max(14, Math.floor((self ? COL : Math.abs(b - a)) / 7))
          const d = self ? `M${a},${y - 6} h30 v10 h-26` : `M${a},${y} L${b + (b > a ? -6 : 6)},${y}`
          return (
            <g key={m.n} className={[css.msgRow, m.toNode === selected && css.msgSel].filter(Boolean).join(' ')} role="button" tabIndex={0}
              aria-label={`${m.n}. ${w(participantWord(m.from, path))} → ${w(participantWord(m.to, path))}: ${label} (${w(HOW_WORD[m.how])})`}
              onClick={() => onSelect(m.toNode)} onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onSelect(m.toNode) } }}>
              <rect className={css.msgHit} x={2} y={y - ROW / 2 - 4} width={width - 4} height={ROW - 2} rx={6} />
              <text x={NUM - 10} y={y + 4} textAnchor="end" className={css.msgN}>{m.n}</text>
              <path d={d} className={[css.msg, m.gap && css.msgGap].filter(Boolean).join(' ')} markerEnd="url(#seq-arrow)" />
              <text x={self ? a + 36 : (a + b) / 2} y={y - 6} textAnchor={self ? 'start' : 'middle'} className={css.msgText}>{short(label, room)}</text>
            </g>
          )
        })}
        <defs>
          <marker id="seq-arrow" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path d="M0,0 L8,4 L0,8 z" className={css.arrow} />
          </marker>
        </defs>
      </svg>
    </div>
  )
}

export function StepList({ data, index, path, selected, onSelect, first }:
  { data: PathsData; index: Index; path: CodePath; selected?: string; onSelect?: (id: string) => void; first?: number }) {
  const w = usePathWords()
  const { t } = usePrefs()
  const [all, setAll] = useState(false)
  const { messages: every } = sequence(data, path, index)
  const messages = all || !first ? every : every.slice(0, first)
  return (
    <ol className={css.steps} aria-label={w('asSteps')}>
      {messages.map((m) => {
        const from = m.fromNode ? index.node.get(m.fromNode) : undefined
        const to = index.node.get(m.toNode)
        const edge = m.edge !== null ? data.edges[m.edge] : undefined
        const at = edge ? where(edge.path, edge.line) : to ? where(to.path, to.line) : null
        const fact = edge?.fact ?? (m.edge === null ? to?.fact : null)
        return (
          <li key={m.n} className={[css.stepItem, m.gap && css.stepGap].filter(Boolean).join(' ')} aria-current={m.toNode === selected ? 'step' : undefined}>
            <span className={css.stepN}><N value={m.n} /></span>
            <div className={css.stepBody}>
              <div className={css.stepLine}>
                <span className={css.stepLane}>{w(participantWord(m.from, path))}</span>
                {from && <Id value={from.label} />}
                <span aria-hidden="true">→</span>
                <span className={css.stepLane}>{w(participantWord(m.to, path))}</span>
                {to && (onSelect
                  ? <AriaButton className={css.stepBtn} onPress={() => onSelect(to.id)}><Id value={to.label} /></AriaButton>
                  : <Id value={to.label} />)}
              </div>
              <span className={css.stepHow}>{m.gap && to?.reason ? w(GAP_WORD[to.reason].title) : w(HOW_WORD[m.how])}</span>
              {(at || fact) && <span className={css.muted}>{at && <Id value={at} keep={2} />}{at && fact ? ' · ' : ''}{fact && <Id value={fact} />}</span>}
            </div>
          </li>
        )
      })}
      {messages.length < every.length && <li><Button variant="ghost" onPress={() => setAll(true)}>{t('showAllN', { n: every.length })}</Button></li>}
    </ol>
  )
}
