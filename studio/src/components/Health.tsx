// The health score (one formula, from health.json), its segmented meter, the phone stat tiles and the stat links.
// The unmeasured is shown as "not measured", never as 0 (docs/STUDIO.md, Standards: truth).
import type { ReactNode } from 'react'
import { Button as AriaButton } from 'react-aria-components'
import type { Measure } from '../data/types'
import { usePrefs } from '../i18n/prefs'
import { N } from '../i18n/text'
import { Chip, type Tone } from './Chip'
import { Go, type Search } from './Go'
import { Icon } from './Icon'
import css from './Health.module.css'

const BANDS = [40, 60, 75, 90] // the band edges, out of 100
type Band = 'critical' | 'weak' | 'fair' | 'good' | 'excellent'
const BAND_TONE: Record<Band, Tone> = { critical: 'critical', weak: 'serious', fair: 'warning', good: 'good', excellent: 'good' }
const BAND_WORD = { critical: 'bandCritical', weak: 'bandWeak', fair: 'bandFair', good: 'bandGood', excellent: 'bandExcellent' } as const

export function band(score: number): Band {
  return score < 40 ? 'critical' : score < 60 ? 'weak' : score < 75 ? 'fair' : score < 90 ? 'good' : 'excellent'
}

export function useBandWord(): (score: number) => string {
  const { t } = usePrefs()
  return (score) => t(BAND_WORD[band(score)])
}

/** The band's status dot, beside its word */
export function BandDot({ score }: { score: number }) {
  return <span className={css.bandDot} data-band={BAND_TONE[band(score)]} aria-hidden="true" />
}

export function BandChip({ score }: { score: number }) {
  const { t } = usePrefs()
  const b = band(score)
  return <Chip tone={BAND_TONE[b]}>{t(BAND_WORD[b])}</Chip>
}

/** Five segments split at the band edges, filled up to the score; ticks under the edges. */
export function Meter({ score, ticks = true }: { score: number; ticks?: boolean }) {
  const edges = [0, ...BANDS, 100]
  return (
    <div className={css.meter} aria-hidden="true">
      <div className={css.track}>
        {edges.slice(0, -1).map((from, i) => {
          const to = edges[i + 1]
          const fill = Math.max(0, Math.min(1, (score - from) / (to - from)))
          return <span key={from} className={css.seg} style={{ flex: to - from }}><i style={{ inlineSize: `${fill * 100}%` }} /></span>
        })}
      </div>
      {ticks && <div className={css.ticks}>{BANDS.map((edge) => <span key={edge} className="num" style={{ insetInlineStart: `${edge}%` }}>{edge}</span>)}</div>}
    </div>
  )
}

/** The health block: label, display number /100, band chip, meter, trend hint. Pressing it opens the health sheet. */
export function HealthBlock({ score, history, onPress }: { score: Measure; history: number; onPress?: () => void }) {
  const { t } = usePrefs()
  const value = score.value === null ? null : Math.round(score.value * 100)
  return (
    <AriaButton className={css.health} onPress={onPress} aria-label={value === null ? `${t('projectHealth')}: ${t('notMeasured')}` : `${t('projectHealth')}: ${value}/100`}>
      <span className={css.eyebrow}>{t('projectHealth')}</span>
      <span className={css.line}>
        {value === null ? <span className={css.unmeasured}>{t('notMeasured')}</span> : (
          <><N value={value} className={css.display} /><span className={css.of}>{t('outOf100')}</span><BandChip score={value} /></>
        )}
        <Icon name="chevron" />
      </span>
      {value !== null && <Meter score={value} />}
      {history < 2 && <span className={css.hint}><Icon name="pulse" />{t('oneScanHint')}</span>}
    </AriaButton>
  )
}

export function Tiles({ children }: { children: ReactNode }) {
  return <div className={css.tiles}>{children}</div>
}

/** A phone stat tile: the whole tile is the link to what it counts, or opens the sheet that explains it. */
/** A count still being read (data/stages.ts COUNT_NEEDS): an ellipsis, and "counting" for a screen reader. Never 0. */
function Counting({ className }: { className?: string }) {
  const { t } = usePrefs()
  return <span className={className}><span className={css.unmeasured} aria-hidden="true">…</span><span className="sr">{t('counting')}</span></span>
}

export function StatTile({ value, of, label, to, search, meter, onPress, counting }:
  { value: number | null; of?: string; label: ReactNode; to?: string; search?: Search; meter?: number; onPress?: () => void; counting?: boolean }) {
  const { t } = usePrefs()
  const body = (
    <>
      <span className={css.tileN}>{counting ? <Counting /> : value === null ? <span className={css.unmeasured}>—</span> : <N value={value} />}{of && <span className={css.of}>{of}</span>}</span>
      <span className={css.tileL}>{label}{!counting && value === null && <span className="sr">{t('notMeasured')}</span>}</span>
      {meter !== undefined && <Meter score={meter} ticks={false} />}
    </>
  )
  if (onPress || !to) return <AriaButton className={css.tile} onPress={onPress}>{body}</AriaButton>
  return <Go to={to} search={search} className={css.tile}>{body}</Go>
}

export function StatLinks({ children, label }: { children: ReactNode; label?: string }) {
  return <nav className={css.statLinks} aria-label={label}>{children}</nav>
}

export function StatLink({ icon, value, label, to, search, counting }: { icon?: ReactNode; value: number; label: string; to: string; search?: Search; counting?: boolean }) {
  return (
    <Go to={to} search={search} className={css.statLink}>
      {icon && <span className={css.statIcon}>{icon}</span>}
      {counting ? <Counting className={css.statN} /> : <N value={value} className={css.statN} />}
      <span className={css.statL}>{label}</span>
      <Icon name="chevron" />
    </Go>
  )
}
