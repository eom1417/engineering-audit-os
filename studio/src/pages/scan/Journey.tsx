// The journey strip: the four steps of the work (eaos/guided.py STEPS, as /api/progress gives them). The running one
// glows, a done one is solid with a tick, one not started yet is dim with the sentence that says when it comes. Each
// step is a button that shows its own flow on the map below. On the phone the strip is a stepper: four numbered marks
// joined by a line, their words read to screen readers only, and the chosen step told in one line under them.
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
  if (!steps.length) return null
  const word: Record<ReturnType<typeof look>, ScanWord> = { running: 'stepRunning', stopped: 'stepStopped', done: 'stepDone', later: 'stepNotYet' }
  const sub = (step: JourneyStep) => {
    const state = look(step)
    return state === 'later' && w.has(`notYet_${step.id}`) ? w(`notYet_${step.id}` as ScanWord) : w(word[state])
  }
  const chosen = Math.max(0, steps.findIndex((step) => step.flow === flow))
  return (
    <nav className={css.journey} aria-label={w('journey')}>
      <ol className={css.journeyList}>
        {steps.map((step, index) => {
          const state = look(step)
          return (
            <li key={step.id}>
              <AriaButton className={[css.journeyStep, css[`journey_${state}`], step.flow === flow && css.journeySel].filter(Boolean).join(' ')}
                onPress={() => onFlow(step.flow)} aria-pressed={step.flow === flow} data-journey={step.id} data-journey-state={state}>
                <span className={css.journeyMark} aria-hidden="true">{state === 'done' ? <Icon name="check" size={14} /> : <span className={css.journeyNum}>{index + 1}</span>}</span>
                <span className={css.journeyMain}>
                  <span className={css.journeyTitle}>{step.title[lang]}</span>
                  <span className={css.journeySub}>{sub(step)}</span>
                </span>
              </AriaButton>
            </li>
          )
        })}
      </ol>
      <p className={css.journeyNow} aria-hidden="true">
        <span className={css.journeyNowTitle}>{w('stepOf', { n: chosen + 1, t: steps.length })} · {steps[chosen].title[lang]}</span>
        <span className={css.journeySub}>{sub(steps[chosen])}</span>
      </p>
    </nav>
  )
}
