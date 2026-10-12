// The pieces that tell where the project stands and what is next: the one-sentence headline whose numbers are
// links, the decision card (Calm), the next step, the journey Today → Change → Target, and the plan strip.
import { useState, type ReactNode } from 'react'
import { useActions } from '../data/actions/store'
import { STATE_WORDS } from '../data/actions/contract'
import { labelOf } from '../data/actions/derive'
import type { Decision, Plan } from '../data/types'
import { usePrefs } from '../i18n/prefs'
import { dirOf, Id, N, Txt } from '../i18n/text'
import { Button, CopyRequestButton, buttonClass, copyText } from './Button'
import { DirectAction } from '../command/Direct'
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
  if (decision.recommended_option) return decision.options.find((o) => o.id === decision.recommended_option)
  const rec = decision.recommendation.trim()
  const matches = decision.options.filter((o) => o.label && rec.startsWith(o.label.trim()) && /^[\s:،,.\-–]|^$/.test(rec.slice(o.label.trim().length)))
  return matches.length === 1 ? matches[0] : undefined
}

/**
 * One question, its recommendation, large one-tap answers (the option the recommendation names is primary, first,
 * with a "Recommended" tag), durable live answers and the link to the cards it concerns.
 */
export function DecisionCard({ decision, cardsTo, compact }: { decision: Decision; cardsTo?: { to: string; search?: Search }; compact?: boolean }) {
  const { t, lang } = usePrefs()
  const toast = useToast()
  const actions = useActions()
  const saved = actions.decisions.find((d) => d.id === decision.id)
  const live = actions.mode === 'live' && !!actions.client?.answerDecision
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [writing, setWriting] = useState(false)
  const [text, setText] = useState('')
  const say = (en: string, ar: string) => lang === 'ar' ? ar : en
  const [allAnswers, setAllAnswers] = useState(false)
  const recommended = recommendedOption(decision)
  const ordered = recommended ? [recommended, ...decision.options.filter((o) => o !== recommended)] : decision.options
  const blocks = decision.blocks.length
  const tasks = decision.blocks.every((b) => b.startsWith('TASK-'))
  const blocksText = blocks === 1 ? t(tasks ? 'blocksOneTask' : 'blocksOneStep') : t(tasks ? 'blocksTasks' : 'blocksSteps', { n: blocks })
  const answer = async (option: { id: string; label: string } | null) => {
    if (busy || !live || !saved || !actions.client?.answerDecision) return
    setBusy(true); setError('')
    try {
      actions.rememberDecision(await actions.client.answerDecision(decision.id, saved.scope, option?.id ?? null, option ? undefined : text))
      await actions.refresh()
    } catch (problem) { setError(String(problem)) }
    finally { setBusy(false) }
  }
  const run = async (work: () => Promise<void>) => {
    setBusy(true)
    try { await work() } catch (e) { setError(String(e)) } finally { setBusy(false) }
  }
  const retryDelivery = () => run(async () => {
    if (!saved?.response) return
    const row = await actions.client?.answerDecision?.(decision.id, saved.scope, saved.response.option, saved.response.text ?? undefined)
    if (row) actions.rememberDecision(row)
    await actions.refresh()
  })
  const retryAssistant = () => run(async () => {
    if (!saved?.execution) return
    await actions.client?.control(saved.execution.id, 'retry')
    await actions.refresh()
  })
  const copyAnswer = async () => toast((await copyText(answerRequest(decision, { id: saved?.response?.option ?? '', label: saved?.response?.label ?? (text || decision.answer || say('No answer selected', 'لم تُحدد إجابة')) }, lang))) ? t('copied') : t('copyFailed'))
  const waiting = decision.state === 'waiting' && !saved?.response
  const disabled = !live || !saved || busy
  return (
    <Panel as="article" emphasis className={[css.decision, compact && css.compactDecision].filter(Boolean).join(' ')} label={decision.question} hook={`decision:${decision.id}`}>
      <DecisionHead waiting={waiting} blocks={blocks} blocksText={blocksText} cardsTo={cardsTo} />
      <h3 className={css.decQ}><Txt block>{decision.question}</Txt></h3>
      {decision.recommendation && (
        <div className={css.decRec}><span className={css.decRecLabel}>{t('recommended')}</span><Txt block>{decision.recommendation}</Txt></div>
      )}
      {waiting && ordered.length > 0 && (
        <AnswerChoices decision={decision} ordered={ordered} recommended={recommended} all={allAnswers} onShowAll={() => setAllAnswers(true)}
          pressed={saved?.response?.option} disabled={disabled} busy={busy} onAnswer={(option) => answer(option)} />
      )}
      {live && !saved && <p role="status">{say('Connecting to live decision storage…', 'جاري الاتصال بحفظ القرارات…')}</p>}
      {!live && <p>{say('Read-only snapshot. Open this project in live Studio to save an answer.', 'هذه نسخة للقراءة. افتح المشروع في الاستوديو الحي لحفظ الإجابة.')}</p>}
      {waiting && (!writing ? <Button isDisabled={disabled} onPress={() => setWriting(true)} data-write-answer>{say('Write a different answer', 'اكتب إجابة مختلفة')}</Button> :
        <WriteAnswer text={text} setText={setText} busy={busy} canSend={!busy && !!saved && !!text.trim()} onSend={() => answer(null)} say={say} />)}
      <SavedAnswer decision={decision} saved={saved} busy={busy} say={say} onRetryDelivery={retryDelivery} onRetryAssistant={retryAssistant} />
      {error && <p role="alert">{error}</p>}
      <Button variant="ghost" icon="copy" onPress={copyAnswer}>{say('Copy answer for export', 'انسخ الإجابة للتصدير')}</Button>
      {decision.state === 'answered' && decision.answer && <p className={css.answered}><Txt>{decision.answer}</Txt></p>}
      {cardsTo && blocks > 0 && decision.blocks.every((b) => b.startsWith('TASK-')) && (
        <Go {...cardsTo} className={[buttonClass('ghost'), css.decSee].join(' ')}>{t('seeCards', { n: blocks })}<Icon name="chevron" /></Go>
      )}
    </Panel>
  )
}

type Say = (en: string, ar: string) => string
type Option = Decision['options'][number]
type Saved = ReturnType<typeof useActions>['decisions'][number]

/** The question's state, and what it holds up (a link to those cards when there is a page for them). */
function DecisionHead({ waiting, blocks, blocksText, cardsTo }: { waiting: boolean; blocks: number; blocksText: string; cardsTo?: { to: string; search?: Search } }) {
  const { t } = usePrefs()
  return (
    <div className={css.decHead}>
      {waiting ? <Chip tone="accent">{t('waiting')}</Chip> : <Chip tone="good">{t('answered')}</Chip>}
      {blocks > 0 && (cardsTo ? <Go {...cardsTo} className={css.decBlocks}>{blocksText}</Go> : <span className={css.decBlocks}>{blocksText}</span>)}
    </div>
  )
}

/** The one-tap answers, the recommended one first and primary; three until the person asks for all. */
function AnswerChoices({ decision, ordered, recommended, all, onShowAll, pressed, disabled, busy, onAnswer }: {
  decision: Decision; ordered: Option[]; recommended?: Option; all: boolean; onShowAll: () => void
  pressed?: string | null; disabled: boolean; busy: boolean; onAnswer: (option: Option) => void
}) {
  const { t } = usePrefs()
  const shown = ordered.slice(0, all ? ordered.length : 3) // never a phone card longer than a screen by default
  const long = decision.options.some((o) => o.label.length > 40)
  const many = decision.options.length !== 2 || long || !recommended
  return (
    <>
      <div className={[css.answers, many && css.answersMany, long && css.answersLong].filter(Boolean).join(' ')}>
        {shown.map((option) => option === recommended ? (
          <Button key={option.id} variant="primary" large aria-pressed={pressed === option.id} className={css.answer} isDisabled={disabled} busy={busy} icon="check" onPress={() => onAnswer(option)} data-option={option.id} data-recommended>
            <Txt>{option.label}</Txt><span className={css.ansTag}>{t('recommendedTag')}</span>
          </Button>
        ) : (
          <Button key={option.id} variant="secondary" large aria-pressed={pressed === option.id} className={css.answer} isDisabled={disabled} busy={busy} onPress={() => onAnswer(option)} data-option={option.id}><Txt>{option.label}</Txt></Button>
        ))}
      </div>
      {ordered.length > shown.length && (
        <Button variant="ghost" className={css.decSee} onPress={onShowAll} aria-expanded={false}>
          {t('showAllAnswers', { n: decision.options.length })}
        </Button>
      )}
    </>
  )
}

/** A written answer of the person's own, up to 4000 characters. */
function WriteAnswer({ text, setText, busy, canSend, onSend, say }: { text: string; setText: (text: string) => void; busy: boolean; canSend: boolean; onSend: () => void; say: Say }) {
  return (
    <form className={css.writeAnswer} onSubmit={(e) => { e.preventDefault(); if (text.trim()) void onSend() }}>
      <label>{say('Your answer (up to 4000 characters)', 'إجابتك (حتى ٤٠٠٠ حرف)')}<textarea className={css.answerInput} value={text} onChange={(e) => setText(e.target.value)} maxLength={4000} /></label>
      <Button type="submit" busy={busy} isDisabled={!canSend} data-send-answer>{say('Send answer', 'أرسل الإجابة')}</Button>
    </form>
  )
}

/** The saved answer, the run it started, and the retries when its delivery or the assistant failed. */
function SavedAnswer({ decision, saved, busy, say, onRetryDelivery, onRetryAssistant }: {
  decision: Decision; saved?: Saved; busy: boolean; say: Say; onRetryDelivery: () => void; onRetryAssistant: () => void
}) {
  const { lang } = usePrefs()
  return (
    <div role="status" aria-live="polite" data-hook="decision-status" data-saved={saved?.response ? (saved.response.option ?? 'text') : undefined}>
      {saved?.response && <p><Txt>{saved.response.option ? decision.options.find((o) => o.id === saved.response?.option)?.label ?? saved.response.label : saved.response.text}</Txt> — {say('Your answer · Saved', 'إجابتك · محفوظة')}
        {saved.execution && <> · <Go to={`/runs/${encodeURIComponent(saved.execution.id)}`}>{labelOf(saved.execution.label, lang)}: {labelOf(STATE_WORDS[saved.execution.state], lang)}</Go></>}
      </p>}
      {saved?.response && <p>{say('Saving an answer does not mean the assistant acknowledged or implemented it. Changes require a separate preview and confirmation.', 'حفظ الإجابة لا يعني أن المساعد استلمها أو نفّذها. التغييرات تحتاج معاينة وموافقة مستقلة.')}</p>}
      {saved?.response && !saved.execution && <Button busy={busy} onPress={onRetryDelivery}>{say('Retry delivery', 'أعد إرسال الإجابة')}</Button>}
      {saved?.execution?.state === 'failed' && <Button busy={busy} onPress={onRetryAssistant}>{say('Retry assistant', 'أعد تشغيل المساعد')}</Button>}
    </div>
  )
}

/** The next step: one sentence and the request for the assistant, labelled with its tool. */
export function NextStep({ action, sub, tool, request }: { action: string; sub?: string; tool: string | null; request: string }) {
  return (
    <Panel className={css.next}>
      <p className={css.nextText}><Txt>{action}</Txt></p>
      {sub && <p className={css.nextSub}><Txt>{sub}</Txt></p>}
      {tool ? <DirectAction request={{ action: tool }} label={action} block copy={{ request, tool }} /> : <CopyRequestButton request={request} tool={tool} block />}
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
