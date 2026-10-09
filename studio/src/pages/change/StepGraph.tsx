// The plan's steps as a dependency graph: a step sits one column after the latest step it waits for, and an arrow
// from A to B says that tasks of B wait for tasks of A (a prerequisite or the same file), with how many. The steps are
// links drawn in HTML (so they read, wrap and take focus like any link); the arrows are drawn beneath, mirrored in
// right-to-left. No arrow is drawn the plan's tasks do not hold.
import { useMemo } from 'react'
import { Go } from '../../components/Go'
import { Panel, Section } from '../../components/Panel'
import type { Plan } from '../../data/types'
import { usePrefs } from '../../i18n/prefs'
import { Id, Txt } from '../../i18n/text'
import { layers, stateCounts, type StepLink } from './model'
import { StateBar } from './parts'
import { useChangeWords } from './words'
import css from './change.module.css'

const NODE_W = 240
const NODE_H = 112
const COL_GAP = 96
const ROW_GAP = 20

export function StepGraph({ plan, links }: { plan: Plan; links: StepLink[] }) {
  const w = useChangeWords()
  const { dir } = usePrefs()
  const columns = useMemo(() => layers(plan.steps.map((s) => s.id), links), [plan, links])
  const at = new Map<string, { col: number; row: number }>()
  columns.forEach((ids, col) => ids.forEach((id, row) => at.set(id, { col, row })))
  const width = columns.length * NODE_W + (columns.length - 1) * COL_GAP
  const height = Math.max(...columns.map((c) => c.length)) * (NODE_H + ROW_GAP) - ROW_GAP
  const xOf = (col: number) => col * (NODE_W + COL_GAP)
  const yOf = (row: number) => row * (NODE_H + ROW_GAP)
  const flip = (x: number) => (dir === 'rtl' ? width - x : x)
  return (
    <Section title={w('viewGraph')} count={links.length}>
      <p className={css.muted}>{links.length ? w('graphLead') : w('graphNone')}</p>
      <Panel pad>
        <div className={css.graphScroll} data-scroll-x="">
          <div className={css.graph} style={{ inlineSize: width, blockSize: height }}>
            <svg width={width} height={height} className={css.graphEdges} role="img" aria-label={w('graphAria', { n: links.length })}>
              <defs>
                <marker id="step-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
                  <path d="M0,0L10,5L0,10z" className={css.arrowHead} />
                </marker>
              </defs>
              {links.map((l) => {
                const a = at.get(l.from)
                const b = at.get(l.to)
                if (!a || !b) return null
                const x0 = flip(xOf(a.col) + NODE_W)
                const x1 = flip(xOf(b.col))
                const y0 = yOf(a.row) + NODE_H / 2
                const y1 = yOf(b.row) + NODE_H / 2
                const m = (x0 + x1) / 2
                return (
                  <g key={`${l.from}-${l.to}`}>
                    <title>{w('edgeAria', { from: l.from, to: l.to, n: l.tasks })}</title>
                    <path d={`M${x0},${y0}C${m},${y0} ${m},${y1} ${x1},${y1}`} className={css.edge} markerEnd="url(#step-arrow)" />
                    <text x={m} y={(y0 + y1) / 2 - 6} textAnchor="middle" className={css.edgeNum}>{l.tasks}</text>
                  </g>
                )
              })}
            </svg>
            {plan.steps.map((step) => {
              const p = at.get(step.id)!
              return (
                <div key={step.id} className={css.nodeAt} style={{ insetInlineStart: xOf(p.col), insetBlockStart: yOf(p.row), inlineSize: NODE_W, blockSize: NODE_H }}>
                  <Go to={`/plans/${encodeURIComponent(plan.id)}/${encodeURIComponent(step.id)}`} className={css.node}>
                    <span className={css.nodeHead}><Id value={step.id} /><span className={css.muted}>{w('tasksN', { n: step.tasks.length })}</span></span>
                    <span className={css.nodeTitle} data-truncate="" title={step.title ?? step.id}><Txt>{step.title ?? step.id}</Txt></span>
                    <StateBar counts={stateCounts(step)} />
                  </Go>
                </div>
              )
            })}
          </div>
        </div>
      </Panel>
      {links.length > 0 && (
        <Panel>
          <ul className={css.edgeList} aria-label={w('viewGraph')}>
            {links.map((l) => (
              <li key={`${l.from}-${l.to}`}><Id value={l.to} /> {w('waitsFor')} <Id value={l.from} /> · <span className={css.muted}>{w('waitsHow', { n: l.tasks })}</span></li>
            ))}
          </ul>
        </Panel>
      )}
    </Section>
  )
}
