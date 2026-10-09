// The System section's maps, one link each: the structure (territory), the user journeys, visible and hidden, the code
// paths, the data paths, the infrastructure lens, the pipeline, the functions and the screens. Each
// map worker adds its own entry here; the current one is marked. Shown at the top of every System map page. And the
// "show hidden" switch every map carries (STUDIO-COMPLETE: hidden things drawn differently, with a switch and a legend).
import { Go } from '../../components/Go'
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

export function SystemViews({ current }: { current: string }) {
  const w = useJourneyWords()
  return (
    <nav className={css.views} aria-label={w('systemViews')}>
      {SYSTEM_VIEWS.map((v) => (
        <Go key={v.id} to={v.to} search={v.search} className={[css.view, v.id === current && css.on].filter(Boolean).join(' ')} current={v.id === current}>{w(v.word)}</Go>
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
