// The System section's maps, one link each: the structure (territory), the user journeys, visible and hidden, the code
// paths, the data paths, the infrastructure lens, the pipeline, the functions and the screens. Each
// map worker adds its own entry here; the current one is marked. Shown at the top of every System map page. And the
// "show hidden" switch every map carries (STUDIO-COMPLETE: hidden things drawn differently, with a switch and a legend).
import { useNavigate, useRouterState } from '@tanstack/react-router'
import { useEffect, useRef } from 'react'
import { useJourneyWords, type JourneyWord } from './words'
import css from './SystemViews.module.css'

export interface SystemView { id: string; to: string; search?: Record<string, string>; word: JourneyWord }

export const SYSTEM_VIEWS: SystemView[] = [
  { id: 'map', to: '/system', word: 'viewMap' },
  { id: 'journeys', to: '/system/journeys', word: 'viewJourneys' },
  { id: 'hidden', to: '/system/hidden', word: 'viewHidden' },
  { id: 'paths', to: '/system/paths', word: 'viewPaths' },
  { id: 'data', to: '/system/data', word: 'viewData' },
  { id: 'infra', to: '/system', search: { lens: 'infra' }, word: 'viewInfra' },
  { id: 'pipeline', to: '/system/pipeline', word: 'viewPipeline' },
  { id: 'functions', to: '/system/functions', word: 'viewFunctions' },
  { id: 'screens', to: '/screens', word: 'viewScreens' },
]

export function SystemViews({ current, persistent = false }: { current: string; persistent?: boolean }) {
  const w = useJourneyWords()
  const navigate = useNavigate()
  const location = useRouterState({ select: (s) => s.location })
  const remembered = useRef<Record<string, Record<string, unknown>>>({})
  const nav = useRef<HTMLElement>(null)
  useEffect(() => {
    remembered.current[current] = location.search as Record<string, unknown>
    nav.current?.querySelector('[aria-selected="true"]')?.scrollIntoView({ block: 'nearest', inline: 'nearest' })
  }, [current, location.search])
  if (!persistent) return null
  const select = (v: SystemView) => navigate({ to: v.to, search: remembered.current[v.id] ?? v.search ?? {}, replace: true })
  return (
    <nav ref={nav} className={css.views} role="tablist" aria-label={w('systemViews')}>
      {SYSTEM_VIEWS.map((v, index) => (
        <button key={v.id} id={`system-tab-${v.id}`} type="button" role="tab" aria-selected={v.id === current} aria-controls="system-workspace-panel"
          tabIndex={v.id === current ? 0 : -1}
          className={[css.view, v.id === current && css.on].filter(Boolean).join(' ')}
          onClick={() => select(v)} onKeyDown={(event) => {
            const rtl = document.documentElement.dir === 'rtl'
            const next = event.key === 'Home' ? 0 : event.key === 'End' ? SYSTEM_VIEWS.length - 1
              : event.key === 'ArrowRight' ? (index + (rtl ? -1 : 1) + SYSTEM_VIEWS.length) % SYSTEM_VIEWS.length
              : event.key === 'ArrowLeft' ? (index + (rtl ? 1 : -1) + SYSTEM_VIEWS.length) % SYSTEM_VIEWS.length : null
            if (next === null) return
            event.preventDefault(); select(SYSTEM_VIEWS[next]); (nav.current?.children[next] as HTMLElement)?.focus()
          }}>{w(v.word)}</button>
      ))}
    </nav>
  )
}

export function HiddenSwitch({ on, onChange }: { on: boolean; onChange: (on: boolean) => void }) {
  const w = useJourneyWords()
  return (
    <button type="button" role="switch" aria-checked={on} onClick={() => onChange(!on)} className={css.switch} data-selected={on || undefined}>
      <span className={css.track} aria-hidden="true"><span className={css.thumb} /></span>{w('showHidden')}
    </button>
  )
}
