// While EAOS works (a check, setting the app up, recording its screens, fixing), every page says so in one line under
// the top bar, with the step and its running stage, and links to the live map (pages/scan); it is not shown on the map
// itself. The whole line is the link, so it is a large target on the phone. The tab's title carries the progress too
// ("3/26"), and a tick once the work this tab watched has ended well.
import { useRouterState } from '@tanstack/react-router'
import { useEffect, useRef } from 'react'
import { Go } from '../components/Go'
import { summarize, TOOLS, type AllProgress, type Summary } from '../data/scan'
import { runningFlow, useScan } from '../data/ScanProvider'
import { usePrefs } from '../i18n/prefs'
import { useScanWords } from '../pages/scan/words'
import { setTitleProgress } from './chrome'
import css from './ScanBanner.module.css'

/** The tab's title follows the running work ("3/26"), and keeps a tick once the work this tab watched ended well. */
function useTabProgress(all: AllProgress | null, flow: string | null, sum: Summary | null) {
  const watched = useRef<string | null>(null)
  if (flow) watched.current = flow
  const ended = watched.current ? all?.flows[watched.current]?.status === 'COMPLETE' : false
  const count = sum ? `${sum.position}/${sum.total}` : ended ? '✓' : ''
  useEffect(() => setTitleProgress(count), [count])
}

export function ScanBanner() {
  const { all } = useScan()
  const w = useScanWords()
  const { lang } = usePrefs()
  const flow = runningFlow(all) ?? (all?.flows[TOOLS]?.state === 'running' ? TOOLS : null)
  const to = flow === TOOLS ? '/tools' : '/scan'
  const here = useRouterState({ select: (s) => s.location.pathname === to })
  const progress = flow ? all?.flows[flow] : undefined
  const sum = progress ? summarize(progress) : null
  useTabProgress(all, flow, sum)
  if (!flow || !sum || here) return null
  const step = all?.journey.find((s) => s.flow === flow)
  const running = sum.running[0]
  const text = w('banner', { f: step ? step.title[lang] : w('toolsTitle'), s: running ? w.stageTitle(running.name, flow) : '' })
  const of = w('bannerOf', { n: flow === TOOLS ? sum.ended : sum.position, t: sum.total })
  return (
    <div data-scan-banner="">
    <Go to={to} search={flow === TOOLS ? undefined : { flow }} className={css.banner} label={`${text} ${of} · ${w('watch')}`}>
      <span className={css.pulse} aria-hidden="true" />
      <span className={css.text}>{text} <span className={css.of}>{of}</span></span>
      <span className={css.watch}>{w('watch')}</span>
    </Go>
    </div>
  )
}
