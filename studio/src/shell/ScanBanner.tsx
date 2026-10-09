// While a check runs, every page says so in one line under the top bar and links to the live check (pages/scan). It
// is the whole line that is the link, so it is a large target on the phone; it is not shown on the live check itself.
import { useRouterState } from '@tanstack/react-router'
import { Go } from '../components/Go'
import { summarize } from '../data/scan'
import { useScan } from '../data/ScanProvider'
import { useScanWords } from '../pages/scan/words'
import css from './ScanBanner.module.css'

export function ScanBanner() {
  const { progress } = useScan()
  const w = useScanWords()
  const here = useRouterState({ select: (s) => s.location.pathname === '/scan' })
  if (!progress || progress.state !== 'running' || here) return null
  const sum = summarize(progress)
  const running = sum.running[0]
  return (
    <div data-scan-banner="">
    <Go to="/scan" className={css.banner} label={`${w('banner', { s: running ? w.stageTitle(running.name) : '' })} ${w('bannerOf', { n: sum.position, t: sum.total })} · ${w('watch')}`}>
      <span className={css.pulse} aria-hidden="true" />
      <span className={css.text}>
        {w('banner', { s: running ? w.stageTitle(running.name) : '' })} <span className={css.of}>{w('bannerOf', { n: sum.position, t: sum.total })}</span>
      </span>
      <span className={css.watch}>{w('watch')}</span>
    </Go>
    </div>
  )
}
