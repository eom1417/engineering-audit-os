// The journey strip: the steps of the person's journey (check and fix, build from a plan, or extend the project:
// eaos/data/journeys.json, as /api/progress gives them). The running one glows, a done one is solid with a tick, one not
// started yet is dim with the sentence that says when it comes. A step with a flow shows it on the map below; one
// without (the plan, the spec, the blueprint) opens the page that shows it.
import type { CSSProperties } from 'react'
import { useNavigate } from '@tanstack/react-router'
import { Button as AriaButton } from 'react-aria-components'
import { Icon } from '../../components/Icon'
import type { JourneyStep } from '../../data/scan'
import { usePrefs } from '../../i18n/prefs'
import { useScanWords, type ScanWord } from './words'
import css from './scan.module.css'

function look(step: JourneyStep): 'running' | 'stopped' | 'done' | 'later' {
  if (step.state === 'running') return 'running'
  if (step.state === 'interrupted' || step.state === 'stalled') return 'stopped'
  return step.done ? 'done' : 'later'
}

interface JourneyProps { steps: JourneyStep[]; flow: string; onFlow: (flow: string) => void }

export function Journey({ steps, flow, onFlow }: JourneyProps) {
  const w = useScanWords()
  const { lang } = usePrefs()
  const navigate = useNavigate()
  if (!steps.length) return null
  const word: Record<ReturnType<typeof look>, ScanWord> = { running: 'stepRunning', stopped: 'stepStopped', done: 'stepDone', later: 'stepNotYet' }
  const name = steps[0].journey?.title[lang]
  const press = (step: JourneyStep) => {
    if (step.flow) onFlow(step.flow)
    else if (step.page) void navigate({ href: step.page })
  }
  return (
    <nav className={css.journey} aria-label={name ? `${w('journey')}: ${name}` : w('journey')} data-journey-of={steps[0].journey?.id}>
      {name && <p className={css.journeyName}>{name}</p>}
      <ol className={css.journeyList} style={{ '--steps': steps.length } as CSSProperties}>
        {steps.map((step) => {
          const state = look(step)
          const chosen = !!step.flow && step.flow === flow
          return (
            <li key={step.id}>
              <AriaButton className={[css.journeyStep, css[`journey_${state}`], chosen && css.journeySel].filter(Boolean).join(' ')}
                onPress={() => press(step)} aria-pressed={chosen} data-journey={step.id} data-journey-state={state}>
                <span className={css.journeyMark} aria-hidden="true">{state === 'done' ? <Icon name="check" size={14} /> : null}</span>
                <span className={css.journeyMain}>
                  <span className={css.journeyTitle}>{step.title[lang]}</span>
                  <span className={css.journeySub}>{state === 'later' && step.later ? step.later[lang] : w(word[state])}</span>
                </span>
              </AriaButton>
            </li>
          )
        })}
      </ol>
    </nav>
  )
}
