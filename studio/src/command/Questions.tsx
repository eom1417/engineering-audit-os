// A run's question, as the Decisions inbox, the run page and the toast show it: the question, the recommended
// answer as the large primary button, the others beside it, and a written answer when none fits. One tap answers;
// the run goes on at once (optimistic), and a refusal brings the question back with the reason.
import { useState } from 'react'
import { Input, TextField } from 'react-aria-components'
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
    actions.dropQuestion(question.id)
    actions.patch(question.run, { state: 'running', question: null })
    try {
      await actions.client.answer(question.id, option, text ?? null)
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
  const [writing, setWriting] = useState(false)
  const [text, setText] = useState('')
  const recommended = question.options.find((o) => o.id === question.recommendation)
  const ordered = recommended ? [recommended, ...question.options.filter((o) => o !== recommended)] : question.options
  return (
    <Panel as="article" emphasis className={css.question} label={question.text[lang]}>
      <div className={css.qHead}>
        <Chip tone="accent">{w('runAsks')}</Chip>
        {runLabel && !compact && <Go to={`/runs/${encodeURIComponent(question.run)}`} className={css.qRun}><Txt>{w('fromRun', { label: runLabel })}</Txt></Go>}
      </div>
      <h3 className={css.qText}><Txt block>{question.text[lang]}</Txt></h3>
      {recommended && (
        <div className={css.qRec}><span className={css.qRecLabel}>{w('recommended')}</span><Txt block>{recommended.label[lang]}</Txt></div>
      )}
      <div className={[css.qAnswers, ordered.length !== 2 && css.qAnswersMany].filter(Boolean).join(' ')}>
        {ordered.map((option) => (
          <Button key={option.id} variant={option === recommended ? 'primary' : 'secondary'} large icon={option === recommended ? 'check' : undefined}
            className={css.qAnswer} onPress={() => answer(question, option.id)}>
            <span><Txt>{option.label[lang]}</Txt></span>
          </Button>
        ))}
      </div>
      {!writing ? (
        <Button variant="ghost" className={css.qMore} onPress={() => setWriting(true)}>{w('writeAnswer')}</Button>
      ) : (
        <form className={css.qWrite} onSubmit={(e) => { e.preventDefault(); if (text.trim()) void answer(question, null, text.trim()) }}>
          <TextField aria-label={w('writeAnswer')} value={text} onChange={setText} className={css.qField} autoFocus>
            <Input className={css.input} />
          </TextField>
          <Button type="submit" variant="secondary" isDisabled={!text.trim()}>{w('send')}</Button>
        </form>
      )}
    </Panel>
  )
}

/** The newest question, floating over every page but the inbox and its own run, with the recommended answer. */
export function QuestionToast({ question, runLabel, onDismiss }: { question: Question; runLabel: string; onDismiss: () => void }) {
  const { lang } = usePrefs()
  const w = useCmdWords()
  const answer = useAnswer()
  const recommended = question.options.find((o) => o.id === question.recommendation) ?? question.options[0]
  return (
    <div className={css.qToast} role="region" aria-label={w('runAsks')}>
      <div className={css.qToastHead}>
        <Icon name="inbox" />
        <span className={css.qToastKicker} data-truncate title={runLabel}><Txt>{runLabel}</Txt></span>
        <IconButton icon="x" label={w('dismiss')} onPress={onDismiss} small />
      </div>
      <p className={css.qToastText}><Txt>{question.text[lang]}</Txt></p>
      <div className={css.qToastActions}>
        {recommended && (
          <Button variant="primary" icon="check" className={css.qToastGo} onPress={() => answer(question, recommended.id)}>
            <span><Txt>{w('answerWith', { label: recommended.label[lang] })}</Txt></span>
          </Button>
        )}
        <Go to="/decisions" className={css.qToastLink}>{w('otherAnswers')}</Go>
      </div>
    </div>
  )
}
