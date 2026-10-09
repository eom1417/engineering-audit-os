// #/change/bridge: where each part goes (C-experience 3.6). Wide screens: a sankey from today's components (inline-start)
// to the target's (inline-end), each ribbon exactly as thick as its files and coloured by its operation; components
// under 2% of the files gather in "Other" when the column would pass 24 rows; a ribbon opens its gap. The phone, and
// ?view=table everywhere: the transfer list, grouped by target component with its responsibility and the mix of operations moving into it.
import { useNavigate, useSearch } from '@tanstack/react-router'
import { useLayoutEffect, useMemo, useRef, useState } from 'react'
import { OperationChip } from '../../components/Chip'
import { Segmented } from '../../components/Controls'
import { FoldList, Panel, RowLink, Section } from '../../components/Panel'
import { RELATION_OF } from '../../data/change'
import type { Story, StudioData } from '../../data/types'
import { usePrefs } from '../../i18n/prefs'
import { Id, Txt } from '../../i18n/text'
import { usePageChrome } from '../../shell/chrome'
import { layout as page, MissingBanner, PageTitle, WithData } from '../../shell/Layout'
import { usePhone } from '../SystemMap'
import { band, bridge, layout, OP_LABEL, OTHER, REMOVED, type Bridge, type Side } from './model'
import { ChangeNav, NotMeasured } from './parts'
import { useChangeWords } from './words'
import css from './change.module.css'

const LABEL_L = 230
const LABEL_R = 210
const BAR = 10

function sideName(side: Side, w: ReturnType<typeof useChangeWords>) {
  return side.id === REMOVED ? w('removed') : side.id === OTHER ? w('other', { n: side.components }) : side.id
}

function gapHref(id: string | null) {
  return id ? `#/change/gaps/${encodeURIComponent(id)}` : '#/change/gaps'
}

/** The sankey, laid out in the pixels of its column so its words stay at reading size. */
function Sankey({ b }: { b: Bridge }) {
  const w = useChangeWords()
  const { t, dir } = usePrefs()
  const box = useRef<HTMLDivElement>(null)
  const [width, setWidth] = useState(0)
  useLayoutEffect(() => {
    const el = box.current
    if (!el) return
    const read = () => setWidth(el.clientWidth)
    read()
    const watch = new ResizeObserver(read)
    watch.observe(el)
    return () => watch.disconnect()
  }, [])
  const rows = Math.max(b.left.length, b.right.length)
  const placed = useMemo(() => layout(b, Math.max(rows * 30, 420)), [b, rows])
  const rtl = dir === 'rtl'
  const x = (v: number) => (rtl ? width - v : v)
  const x0 = LABEL_L + BAR
  const x1 = width - LABEL_R - BAR
  const h = placed.height + 4
  // An identifier is laid out left to right, so its anchor mirrors with the page; a word in the page's own direction
  // already reads from the inline start, so its anchor stays.
  const label = (side: Side, at: number, anchor: 'start' | 'end', y: number, hh: number, newOne: boolean) => {
    const word = side.id === REMOVED || side.id === OTHER
    return (
      <text x={x(at)} y={y + hh / 2} dominantBaseline="middle" textAnchor={rtl && !word ? (anchor === 'start' ? 'end' : 'start') : anchor}
        className={word ? css.sankeyWord : css.sankeyId} direction={word ? dir : 'ltr'}>
        {sideName(side, w)}{newOne ? ` · ${w('newHere')}` : ''}
        {!newOne && <tspan className={css.sankeyNum}>{`  ${side.files}`}</tspan>}
      </text>
    )
  }
  return (
    <div ref={box} className={css.sankeyBox}>
      {width > 0 && (
        <svg width={width} height={h} role="group" aria-label={w('bridgeAria', { c: b.components, t: b.targets })} className={css.sankey}>
          <defs>
            <pattern id="bridge-hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
              <rect width="6" height="6" className={css.hatchBack} /><line x1="0" y1="0" x2="0" y2="6" className={css.hatchLine} />
            </pattern>
          </defs>
          <g transform="translate(0,2)">
            {placed.ribbons.map((r, i) => {
              const from = b.left.find((s) => s.id === r.from)!
              const to = b.right.find((s) => s.id === r.to)!
              const xa = x(x0)
              const xb = x(x1)
              return (
                <a key={i} href={gapHref(r.gap)} className={css.ribbonLink}
                  aria-label={w('ribbonAria', { from: sideName(from, w), n: r.files, op: t(OP_LABEL[r.op]), to: sideName(to, w) })}>
                  <path d={band(xa, xb, r.y0, r.y1, r.w)} className={[css.ribbon, r.op === 'delete' ? '' : css[`fill_${r.op}`]].join(' ')} fill={r.op === 'delete' ? 'url(#bridge-hatch)' : undefined} />
                </a>
              )
            })}
            {b.left.map((s) => {
              const p = placed.left.get(s.id)!
              return (
                <g key={s.id}>
                  <rect x={Math.min(x(LABEL_L), x(LABEL_L + BAR))} y={p.y} width={BAR} height={p.h} rx={2} className={css[`bar_${s.op ?? 'other'}`]} />
                  {label(s, LABEL_L - 8, 'end', p.y, p.h, false)}
                </g>
              )
            })}
            {b.right.map((s) => {
              const p = placed.right.get(s.id)!
              return (
                <g key={s.id}>
                  <rect x={Math.min(x(x1), x(x1 + BAR))} y={p.y} width={BAR} height={p.h} rx={2} className={css[`bar_${s.op ?? 'other'}`]} />
                  {label(s, x1 + BAR + 8, 'start', p.y, p.h, s.op === 'new')}
                </g>
              )
            })}
          </g>
        </svg>
      )}
    </div>
  )
}

/** The operations moving into one target, as a 100% bar of their files (each with its word in the rows below). */
function Mix({ rows }: { rows: { op: keyof typeof RELATION_OF; files: number }[] }) {
  const total = rows.reduce((s, r) => s + r.files, 0)
  if (!total) return null
  return <span className={css.mix} aria-hidden="true">{rows.map((r, i) => <i key={i} className={css[`fill_${r.op}`]} style={{ flexGrow: r.files }} />)}</span>
}

/** The phone's Bridge (and the table view): each target with what moves into it. */
function TransferList({ b, story }: { b: Bridge; story: Story }) {
  const w = useChangeWords()
  return (
    <div className={css.groups}>
      {b.right.map((side) => {
        const rows = story.gap.filter((g) => (side.id === REMOVED ? g.relation === 'delete' || !g.to : g.to === side.id && g.relation !== 'delete'))
          .sort((a, c) => c.files - a.files || a.component.localeCompare(c.component))
        const mix = b.flows.filter((f) => f.to === side.id)
        return (
          <Section key={side.id} title={side.id === REMOVED ? w('removed') : side.id} count={rows.length} id={`to-${side.id}`}>
            <Panel>
              <div className={css.groupHead}>
                {side.responsibility && <span className={css.muted}><Txt block>{side.responsibility}</Txt></span>}
                <span className={css.groupMeta}>
                  <span>{w('filesN', { n: side.files })}</span>
                  {side.op === 'new' && <OperationChip relation="introduce" />}
                </span>
                <Mix rows={mix} />
              </div>
              {rows.length > 0 && (
                <FoldList items={rows} first={6} label={side.id === REMOVED ? w('removed') : side.id} render={(g) => (
                  <RowLink to={`/change/gaps/${encodeURIComponent(g.component)}`} chevron={false}
                    title={<Id value={g.component} keep={3} />} sub={w('filesN', { n: g.files })}
                    end={<OperationChip relation={g.relation} />} />
                )} />
              )}
            </Panel>
          </Section>
        )
      })}
    </div>
  )
}

function BridgeBody({ data }: { data: StudioData }) {
  const w = useChangeWords()
  const { t } = usePrefs()
  const phone = usePhone()
  const navigate = useNavigate()
  const search = useSearch({ strict: false }) as { view?: string }
  usePageChrome(w('bridgeTitle'), { to: '/change', label: t('journeyAndPlan') }, data.manifest.project.name)
  const story = data.story && data.story.gap.length > 0 ? data.story : undefined
  const b = useMemo(() => (story ? bridge(story) : null), [story])
  const table = phone || search.view === 'table'
  return (
    <div className={page.page}>
      <MissingBanner data={data} />
      <ChangeNav />
      <PageTitle title={w('bridgeTitle')} lead={w('bridgeLead')} />
      {!story || !b ? <NotMeasured data={data} section="story" title={w('noTarget')} /> : (
        <>
          <div className={css.summaries}>
            <Panel pad><span className={css.kicker}>{w('todaySummary')}</span>
              <span>{w('todayLine', { c: b.components, f: b.files, d: b.right.find((r) => r.id === REMOVED)?.components ?? 0 })}</span></Panel>
            <Panel pad><span className={css.kicker}>{w('targetSummary')}</span>
              <span>{w('targetLine', { t: b.targets, m: b.right.filter((r) => r.op === 'merge').length, n: b.right.filter((r) => r.op === 'new').length })}</span></Panel>
          </div>
          {!phone && (
            <div className={css.toolbar}>
              <Segmented label={w('showAs')} value={table ? 'table' : 'diagram'}
                onChange={(v) => navigate({ to: '/change/bridge', replace: true, search: v === 'table' ? { view: 'table' } : {} })}
                options={[{ id: 'diagram', label: w('asDiagram') }, { id: 'table', label: w('asTable') }]} />
            </div>
          )}
          {table ? <><p className={css.muted}>{w('transferLead')}</p><TransferList b={b} story={story} /></> : <Panel pad><Sankey b={b} /></Panel>}
        </>
      )}
    </div>
  )
}

export function BridgePage() {
  return <WithData>{(data) => <BridgeBody data={data} />}</WithData>
}

