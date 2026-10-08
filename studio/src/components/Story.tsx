// The pieces that tell where the project stands and what is next: the one-sentence headline whose numbers are
// links, the decision card (Calm), the next step, the journey Today → Change → Target, and the plan strip.
import { useState, type ReactNode } from 'react'
import type { Decision, Plan } from '../data/types'
import { usePrefs } from '../i18n/prefs'
import { dirOf, Id, N, Txt } from '../i18n/text'
import { Button, CopyRequestButton, buttonClass, copyText } from './Button'
import { Chip } from './Chip'
import { Go, type Search } from './Go'
import { Icon } from './Icon'
import { Panel } from './Panel'
import { useToast } from './Toast'
import css from './Story.module.css'

/** The headline sentence: parts are text or numbers that link to the list they count. */
export type HeadlinePart = string | { value: number; to: string; search?: Search; word?: string }

export function Headline({ parts, as: Tag = 'p' }: { parts: HeadlinePart[]; as?: 'p' | 'h1' }) {
  // The sentence keeps its own direction (an Arabic report's verdict read in the English interface stays right to left)
  const dir = dirOf(parts.map((part) => (typeof part === 'string' ? part : part.word ?? '')).join(' '))
  return (
    <Tag className={css.headline} dir={dir}>
      {parts.map((part, i) => typeof part === 'string'
        ? <Txt key={i}>{part}</Txt>
        : <Go key={i} to={part.to} search={part.search} className={css.hlLink}><N value={part.value} />{part.word ? <> <Txt>{part.word}</Txt></> : null}</Go>)}
    </Tag>
  )
}

/** Splits report text around its numbers so each, with the word after it, becomes a link ("217 مشكلة، منها 165 …"):
 * the word makes the target wide enough to tap and says what the number counts. */
export function headlineParts(text: string, links: { value: number; to: string; search?: Search }[]): HeadlinePart[] {
  const parts: HeadlinePart[] = []
  let rest = text
  for (const link of links) {
    const match = new RegExp(`(^|[^\\d])${link.value}(?!\\d)(\\s+[^\\s،,.:;]+)?`).exec(rest)
    if (!match) continue
    const at = match.index + match[1].length
    if (at > 0) parts.push(rest.slice(0, at))
    const word = match[2]?.trim()
    parts.push({ ...link, word })
    rest = rest.slice(at + String(link.value).length + (match[2]?.length ?? 0))
  }
  if (rest) parts.push(rest)
  return parts
}

/** The answer copied for the assistant when a person taps an option. */
function answerRequest(decision: Decision, option: { id: string; label: string }, lang: 'ar' | 'en'): string {
  const tool = decision.tool ? (lang === 'ar' ? ` (الأداة ${decision.tool})` : ` (tool ${decision.tool})`) : ''
  return lang === 'ar'
    ? `جوابي على سؤال EAOS «${decision.question}»: ${option.label}${tool}.`
    : `My answer to the EAOS question "${decision.question}": ${option.label}${tool}.`
}

/** The option the recommendation names: its sentence opens with the option's label ("نعم: …" → "نعم"). The data
 * marks no option itself, so none is promoted when the recommendation names none. */
export function recommendedOption(decision: Decision): Decision['options'][number] | undefined {
  const rec = decision.recommendation.trim()
  return decision.options.find((o) => o.label && rec.startsWith(o.label.trim()) && /^[\s:،,.\-–]|^$/.test(rec.slice(o.label.trim().length)))
}

/**
 * One question, its recommendation, large one-tap answers (the option the recommendation names is primary, first,
 * with a "Recommended" tag), the hint that a tap only copies the answer, and the link to the cards it concerns.
 */
export function DecisionCard({ decision, cardsTo }: { decision: Decision; cardsTo?: { to: string; search?: Search } }) {
  const { t, lang } = usePrefs()
  const toast = useToast()
  const [allAnswers, setAllAnswers] = useState(false)
  const recommended = recommendedOption(decision)
  const ordered = recommended ? [recommended, ...decision.options.filter((o) => o !== recommended)] : decision.options
  const shownCount = allAnswers ? ordered.length : 3 // never a phone card longer than a screen by default
  const shown = ordered.slice(0, shownCount)
  const twoChoices = decision.options.length === 2
  const long = decision.options.some((o) => o.label.length > 40)
  const blocks = decision.blocks.length
  const tasks = decision.blocks.every((b) => b.startsWith('TASK-'))
  const blocksText = blocks === 1 ? t(tasks ? 'blocksOneTask' : 'blocksOneStep') : t(tasks ? 'blocksTasks' : 'blocksSteps', { n: blocks })
  const answer = async (option: { id: string; label: string }) =>
    toast((await copyText(answerRequest(decision, option, lang))) ? t('copiedAnswer') : t('copyFailed'))
  return (
    <Panel as="article" emphasis className={css.decision} label={decision.question}>
      <div className={css.decHead}>
        {decision.state === 'waiting' ? <Chip tone="accent">{t('waiting')}</Chip> : <Chip tone="good">{t('answered')}</Chip>}
        {blocks > 0 && (cardsTo ? <Go {...cardsTo} className={css.decBlocks}>{blocksText}</Go> : <span className={css.decBlocks}>{blocksText}</span>)}
      </div>
      <h3 className={css.decQ}><Txt block>{decision.question}</Txt></h3>
      {decision.recommendation && (
        <div className={css.decRec}><span className={css.decRecLabel}>{t('recommended')}</span><Txt block>{decision.recommendation}</Txt></div>
      )}
      {decision.state === 'waiting' && ordered.length > 0 && (
        <>
          <div className={[css.answers, (!twoChoices || long || !recommended) && css.answersMany, long && css.answersLong].filter(Boolean).join(' ')}>
            {shown.map((option) => option === recommended ? (
              <Button key={option.id} variant="primary" large className={css.answer} icon="check" onPress={() => answer(option)}>
                <Txt>{option.label}</Txt><span className={css.ansTag}>{t('recommendedTag')}</span>
              </Button>
            ) : (
              <Button key={option.id} variant="secondary" large className={css.answer} onPress={() => answer(option)}><Txt>{option.label}</Txt></Button>
            ))}
          </div>
          {ordered.length > shown.length && (
            <Button variant="ghost" className={css.decSee} onPress={() => setAllAnswers(true)} aria-expanded={false}>
              {t('showAllAnswers', { n: decision.options.length })}
            </Button>
          )}
          <p className={css.ansHint}>{t('tapCopies')}</p>
        </>
      )}
      {decision.state === 'answered' && decision.answer && <p className={css.answered}><Txt>{decision.answer}</Txt></p>}
      {cardsTo && blocks > 0 && decision.blocks.every((b) => b.startsWith('TASK-')) && (
        <Go {...cardsTo} className={[buttonClass('ghost'), css.decSee].join(' ')}>{t('seeCards', { n: blocks })}<Icon name="chevron" /></Go>
      )}
    </Panel>
  )
}

/** The next step: one sentence and the request for the assistant, labelled with its tool. */
export function NextStep({ action, sub, tool, request }: { action: string; sub?: string; tool: string | null; request: string }) {
  return (
    <Panel className={css.next}>
      <p className={css.nextText}><Txt>{action}</Txt></p>
      {sub && <p className={css.nextSub}><Txt>{sub}</Txt></p>}
      <CopyRequestButton request={request} tool={tool} block />
    </Panel>
  )
}

export interface JourneyStage { key: string; value: number | null; unit: string; to: string; search?: Search }

/** Today → Change → Target in the same unit; the arrows mirror in right-to-left. */
export function Journey({ stages, label }: { stages: JourneyStage[]; label: string }) {
  const { t } = usePrefs()
  const out: ReactNode[] = []
  stages.forEach((stage, i) => {
    if (i > 0) out.push(<span key={`a${i}`} className={css.jArrow} aria-hidden="true"><Icon name="arrow" /></span>)
    out.push(
      <Go key={stage.key} to={stage.to} search={stage.search} className={css.jTile}>
        <span className={css.jK}>{stage.key}</span>
        <span className={css.jN}>{stage.value === null ? '—' : <N value={stage.value} />}</span>
        <span className={css.jU}>{stage.value === null ? t('notMeasured') : stage.unit}</span>
      </Go>,
    )
  })
  return <nav className={css.journey} aria-label={label}>{out}</nav>
}

/** A plan's state, done/total, and a strip of its steps sized by their tasks. Progress only from the ledger. */
export function PlanStrip({ plan, to }: { plan: Plan; to: string }) {
  const { t } = usePrefs()
  const tasks = plan.steps.reduce((sum, step) => sum + step.tasks.length, 0)
  const done = plan.steps.reduce((sum, step) => sum + step.tasks.filter((task) => task.state === 'done').length, 0)
  return (
    <Go to={to} className={css.plan}>
      <span className={css.planHead}>
        <span className={css.planState}>{done === 0 ? t('planNotStarted') : t('planActive')}</span>
        <span className={css.planCount}>{t('planTasksDone', { done, total: tasks })} · {t('planSteps', { n: plan.steps.length })}</span>
        <Icon name="chevron" />
      </span>
      <span className={css.strip} aria-hidden="true">
        {plan.steps.map((step) => {
          const stepDone = step.tasks.filter((task) => task.state === 'done').length
          return <span key={step.id} className={css.ps} style={{ flex: Math.max(step.tasks.length, 1) }}><i style={{ inlineSize: `${(stepDone / Math.max(step.tasks.length, 1)) * 100}%` }} /></span>
        })}
      </span>
      <span className={css.planCap}>{t('tasksInStep')}</span>
      <ul className={css.legend}>
        {plan.steps.map((step) => <li key={step.id}><Id value={step.id} /><N value={step.tasks.length} /></li>)}
      </ul>
    </Go>
  )
}
