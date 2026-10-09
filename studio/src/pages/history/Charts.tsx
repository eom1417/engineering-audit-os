// The history's charts, drawn in SVG with the Studio's tokens (docs/adoption/ns46-t4-library-history-quality.md): one
// question per chart, one y-axis, labelled points, time running from inline-start (right to left in Arabic). The
// geometry is model.ts's; a chart is only drawn with two points or more, which the pages check before using one.
import { useCallback, useState } from 'react'
import { usePrefs } from '../../i18n/prefs'
import { bands, labelled, place, SEVERITIES, type Plot, type Scan, type Sev } from './model'
import { useHistoryWords } from './words'
import css from './history.module.css'

/** The width the chart has to draw in, followed as the window changes. */
function useWidth(): [(el: HTMLDivElement | null) => (() => void) | undefined, number] {
  const [width, setWidth] = useState(0)
  const ref = useCallback((el: HTMLDivElement | null) => {
    if (!el) return
    setWidth(Math.floor(el.getBoundingClientRect().width))
    const observer = new ResizeObserver(([entry]) => setWidth(Math.floor(entry.contentRect.width)))
    observer.observe(el)
    return () => observer.disconnect()          // React 19 runs a ref's cleanup when the element goes
  }, [])
  return [ref, width]
}

function plotOf(width: number): Plot {
  const phone = width < 560
  return { width: Math.max(width, 240), height: phone ? 220 : 260, pad: { start: 44, end: 24, top: 26, bottom: 34 } }
}

/** The y grid with its labels at inline-start, and the first and last dates along the bottom. */
function Axes({ plot, rtl, ticks, first, last }: { plot: Plot; rtl: boolean; ticks: { at: number; label: string }[]; first: string; last: string }) {
  const tall = plot.height - plot.pad.top - plot.pad.bottom
  const x0 = rtl ? plot.pad.end : plot.pad.start
  const x1 = rtl ? plot.width - plot.pad.start : plot.width - plot.pad.end
  const labelX = rtl ? plot.width - 6 : 6
  return (
    <g>
      {ticks.map((tick) => {
        const y = plot.pad.top + (1 - tick.at) * tall
        return (
          <g key={tick.at}>
            <line x1={x0} x2={x1} y1={y} y2={y} className={tick.at === 0 ? css.baseline : css.grid} />
            <text x={labelX} y={y + 4} textAnchor={rtl ? 'end' : 'start'} className={css.tick}>{tick.label}</text>
          </g>
        )
      })}
      <text x={rtl ? x1 : x0} y={plot.height - 10} textAnchor={rtl ? 'end' : 'start'} className={css.tick}>{first}</text>
      {last !== first && <text x={rtl ? x0 : x1} y={plot.height - 10} textAnchor={rtl ? 'start' : 'end'} className={css.tick}>{last}</text>}
    </g>
  )
}

/** A value from 0 to 1 over time: the score, or the share of cards closed. */
export function LineChart({ values, label, format, ticks }:
  { values: { at: string; value: number }[]; label: string; format: (value: number) => string; ticks: { at: number; label: string }[] }) {
  const { dir, date } = usePrefs()
  const rtl = dir === 'rtl'
  const [ref, width] = useWidth()
  const plot = plotOf(width)
  const points = place(values, plot, rtl)
  const shown = labelled(points.length, plot.width < 560 ? 5 : 9)
  return (
    <div ref={ref} className={css.chart} style={{ blockSize: plot.height }}>
      {width > 0 && (
        <svg width={plot.width} height={plot.height} role="img" aria-label={label} direction="ltr" className={css.svg}>
          <Axes plot={plot} rtl={rtl} ticks={ticks} first={date(values[0].at)} last={date(values[values.length - 1].at)} />
          <polyline points={points.map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ')} className={css.line} />
          {points.map((p, i) => (
            <g key={i}>
              <circle cx={p.x} cy={p.y} r={shown.has(i) ? 4 : 2.5} className={css.dot} />
              {shown.has(i) && <text x={p.x} y={p.y - 9} textAnchor="middle" className={css.value}>{format(p.value)}</text>}
            </g>
          ))}
        </svg>
      )}
    </div>
  )
}

const SEV_CLASS: Record<Sev, string> = { critical: css.sev4, high: css.sev3, medium: css.sev2, low: css.sev1, info: css.sevOff }
const SEV_WORD = { critical: 'sevCritical', high: 'sevHigh', medium: 'sevMedium', low: 'sevLow' } as const

/** The open problems of each check, stacked by severity, the most severe at the bottom. */
export function StackedChart({ scans, label }: { scans: Scan[]; label: string }) {
  const { dir, date, t, num } = usePrefs()
  const w = useHistoryWords()
  const rtl = dir === 'rtl'
  const [ref, width] = useWidth()
  const plot = plotOf(width)
  const totals = scans.map((s) => SEVERITIES.reduce((sum, k) => sum + (s.open[k] ?? 0), 0))
  const top = Math.max(1, ...totals)
  const tops = place(scans.map((s, i) => ({ at: s.at, value: totals[i] / top })), plot, rtl)
  const shown = labelled(tops.length, plot.width < 560 ? 5 : 9)
  return (
    <div className={css.stack}>
      <div ref={ref} className={css.chart} style={{ blockSize: plot.height }}>
        {width > 0 && (
          <svg width={plot.width} height={plot.height} role="img" aria-label={label} direction="ltr" className={css.svg}>
            <Axes plot={plot} rtl={rtl} ticks={[{ at: 0, label: '0' }, { at: 0.5, label: num(Math.round(top / 2)) }, { at: 1, label: num(top) }]}
              first={date(scans[0].at)} last={date(scans[scans.length - 1].at)} />
            {bands(scans, plot, rtl).map((band) => <polygon key={band.sev} points={band.points} className={[css.band, SEV_CLASS[band.sev]].join(' ')} />)}
            {tops.map((p, i) => shown.has(i) && <text key={i} x={p.x} y={p.y - 7} textAnchor="middle" className={css.value}>{num(totals[i])}</text>)}
          </svg>
        )}
      </div>
      <ul className={css.legend}>
        {SEVERITIES.map((sev) => (
          <li key={sev}><span className={[css.swatch, SEV_CLASS[sev]].join(' ')} aria-hidden="true" />{sev === 'info' ? w('info') : t(SEV_WORD[sev])}</li>
        ))}
      </ul>
    </div>
  )
}
