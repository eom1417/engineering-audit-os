// A run's question, as the Decisions inbox, the run page and the toast show it: the question, the recommended
// answer as the large primary button, the others beside it, and a written answer when none fits. One tap answers;
// the run continues only after server success. Drafts remain visible after a refusal.
import { useId, useState } from 'react'
import { Label, TextArea, TextField } from 'react-aria-components'
import { Button, IconButton } from '../components/Button'
import { Chip } from '../components/Chip'
import { Go } from '../components/Go'
import { Icon } from '../components/Icon'
import { Panel } from '../components/Panel'
import { useToast } from '../components/Toast'
import { useActions } from '../data/actions/store'
import { ActionError, type Question } from '../data/actions/types'
import { usePrefs } from '../i18n/prefs'
import { Txt } from '../i18n/text'
import { useCmdWords } from './words'
import css from './command.module.css'

export function useAnswer() {
  const actions = useActions()
  const toast = useToast()
  const w = useCmdWords()
  return async (question: Question, option: string | null, text?: string) => {
    if (!actions.client) return false
    try {
      await actions.client.answer(question.id, option, text ?? null)
      actions.dropQuestion(question.id)
      toast(w('answered'))
      void actions.refresh()
      return true
    } catch (error) {
      toast(`${w('answerFailed')}: ${error instanceof ActionError ? error.message : String(error)}`)
      void actions.refresh()
      return false
    }
  }
}

export function QuestionCard({ question, runLabel, compact }: { question: Question; runLabel?: string; compact?: boolean }) {
  const { lang } = usePrefs()
  const w = useCmdWords()
  const answer = useAnswer()
  const [busy, setBusy] = useState(false)
  const send = async (option: string | null, text?: string) => { if (busy) return; setBusy(true); try { await answer(question, option, text) } finally { setBusy(false) } }
  const [writing, setWriting] = useState(false)
  const [text, setText] = useState('')
  const recommended = question.options.find((o) => o.id === question.recommendation)
  const ordered = recommended ? [recommended, ...question.options.filter((o) => o !== recommended)] : question.options
  // Two short answers sit side by side; longer ones stack, each on its own line
  const stacked = ordered.length !== 2 || ordered.some((o) => o.label[lang].length > 14)
  return (
    <Panel as="article" emphasis className={css.question} label={question.text[lang]} hook={`question:${question.id}`}>
      <div className={css.qHead}>
        <Chip tone="accent">{w('runAsks')}</Chip>
        {runLabel && !compact && <Go to={`/runs/${encodeURIComponent(question.run)}`} className={css.qRun}><span><Txt>{w('fromRun', { label: runLabel })}</Txt></span></Go>}
      </div>
      <h3 className={css.qText}><Txt block>{question.text[lang]}</Txt></h3>
      {recommended && (
        <div className={css.qRec}><span className={css.qRecLabel}>{w('recommended')}</span><Txt block>{recommended.label[lang]}</Txt></div>
      )}
      <div className={[css.qAnswers, stacked && css.qAnswersMany].filter(Boolean).join(' ')}>
        {ordered.map((option) => (
          <Button key={option.id} variant={option === recommended ? 'primary' : 'secondary'} large icon={option === recommended ? 'check' : undefined}
            className={css.qAnswer} busy={busy} isDisabled={busy} onPress={() => send(option.id)} data-option={option.id} data-recommended={option === recommended || undefined}>
            <span><Txt>{option.label[lang]}</Txt>{option === recommended && <> · {w('recommended')}</>}</span>
          </Button>
        ))}
      </div>
      {!writing ? (
        <Button variant="ghost" className={css.qMore} onPress={() => setWriting(true)} data-write-answer>{w('writeAnswer')}</Button>
      ) : (
        <form className={css.qWrite} onSubmit={(e) => { e.preventDefault(); if (text.trim()) void send(null, text) }}>
          <TextField value={text} onChange={setText} className={css.qField} autoFocus>
            <Label>{w('customAnswerLabel')}</Label>
            <TextArea className={css.input} maxLength={4000} />
          </TextField>
          <Button type="submit" variant="secondary" busy={busy} isDisabled={busy || !text.trim()} data-send-answer>{w('send')}</Button>
        </form>
      )}
    </Panel>
  )
}

/** The newest question, floating over every page but the inbox and its own run, with the recommended answer. On the
 * phone it starts as a short notice (the question and an Answer button) so it never covers the page's rows; the button
 * opens the full question in place. */
export function QuestionToast({ question, runLabel, onDismiss }: { question: Question; runLabel: string; onDismiss: () => void }) {
  const { lang } = usePrefs()
  const w = useCmdWords()
  const [open, setOpen] = useState(false)
  const full = useId()
  return (
    <div className={css.qToast} role="region" aria-label={w('runAsks')} data-open={open || undefined}>
      <div className={css.qToastHead}>
        <Icon name="inbox" />
        <span className={css.qToastKicker} data-truncate title={runLabel}><Txt>{runLabel}</Txt></span>
        <IconButton icon="x" label={w('dismiss')} onPress={onDismiss} small />
      </div>
      <div className={css.qToastBrief}>
        <p className={css.qToastText}><Txt block>{question.text[lang]}</Txt></p>
        <Button variant="primary" className={css.qToastGo} aria-expanded={false} aria-controls={full} onPress={() => setOpen(true)}>{w('answerNow')}</Button>
      </div>
      <div className={css.qToastFull} id={full}>
        <QuestionCard question={question} compact />
        <Go to="/decisions" className={css.qToastLink}>{w('otherAnswers')}</Go>
      </div>
    </div>
  )
}
