// Waiting for you (#/decisions, from the top bar): every question waiting for the person, one card each, the runs'
// questions first; the branches waiting for approval as one line to Fixes; the answered ones folded under one line.
import { Folded, Panel, RowLink, StateMessage } from '../components/Panel'
import { useAwaitingApproval } from '../shell/waiting'
import { DecisionCard } from '../components/Story'
import type { StudioData } from '../data/types'
import { usePrefs } from '../i18n/prefs'
import { usePageChrome } from '../shell/chrome'
import { layout, MissingBanner, PageTitle, WithData } from '../shell/Layout'
import css from './Pages.module.css'
import { Section } from '../components/Panel'
import { QuestionCard } from '../command/Questions'
import { useCmdWords } from '../command/words'
import { useActions } from '../data/actions/store'
import { labelOf } from '../data/actions/derive'

/** The questions runs ask now (the command centre), above the report's decisions: one tap answers and the run goes on. */
function RunQuestions() {
  const { questions, runs } = useActions()
  const { lang } = usePrefs()
  const w = useCmdWords()
  if (!questions.length) return null
  return (
    <Section title={w('questionsFromRuns')} count={questions.length}>
      <div className={css.cards}>
        {questions.map((q) => <QuestionCard key={q.id} question={q} runLabel={(() => { const run = runs.find((r) => r.id === q.run); return run ? labelOf(run.label, lang) : undefined })()} />)}
      </div>
    </Section>
  )
}

/** The sign-in a check waits for: one line to the sign-in page, first, since the check's pages wait for it. */
function SignInWaiting() {
  const w = useCmdWords()
  return useActions().signIn?.asked ? <Panel emphasis><RowLink to="/sign-in" icon="signIn" title={w('signInWaiting')} sub={w('signInWaitingSub')} /></Panel> : null
}

/** The branches waiting for approval live in Fixes, with their Accept and Undo: here, one line that leads there. */
function ApprovalsLink() {
  const w = useCmdWords()
  const n = useAwaitingApproval().length
  return n ? <Panel><RowLink to="/change" icon="branch" title={w('awaitingN', { n })} /></Panel> : null
}

function DecisionsBody({ data }: { data: StudioData }) {
  const { t } = usePrefs()
  usePageChrome(t('decisions'), undefined, data.manifest.project.name)
  const actions = useActions()
  const snapshot = actions.mode !== 'live'
  const all = (data.decisions?.decisions ?? []).map((d) => actions.decisions.some((r) => r.id === d.id && r.response) ? { ...d, state: 'answered' as const } : d)
  const waiting = all.filter((d) => d.state === 'waiting')
  const decided = all.filter((d) => d.state !== 'waiting')
  const card = (d: (typeof all)[number]) => (
    <DecisionCard key={d.id} decision={d} noted={snapshot} cardsTo={d.blocks.every((b) => b.startsWith('TASK-')) ? { to: '/problems', search: { who: 'you' } } : undefined} />
  )
  const asked = actions.questions.length + (actions.signIn?.asked ? 1 : 0)
  return (
    <div className={layout.page}>
      <MissingBanner data={data} />
      <PageTitle title={t('waitingForYou')} lead={t('waitingLead')} />
      <SignInWaiting />
      <ApprovalsLink />
      {snapshot && waiting.length > 0 && <Panel><StateMessage icon="info" title={t('readOnlyAnswers')} /></Panel>}
      <RunQuestions />
      {waiting.length ? <div className={css.cards}>{waiting.map(card)}</div>
        : asked > 0 ? null : <Panel><StateMessage icon="inbox" title={t('nothingWaits')} sub={t('nothingWaitsSub')} /></Panel>}
      {/* The answered ones: a record, not a question, so closed until the person opens them */}
      {decided.length > 0 && <Folded className={css.decided} summary={t('decidedAlready', { n: decided.length })}><div className={css.cards}>{decided.map(card)}</div></Folded>}
    </div>
  )
}

export function DecisionsPage() {
  // Before the first check there is no report, but the check itself may already ask (which branch): its question shows
  return <WithData empty={<><SignInWaiting /><RunQuestions /></>}>{(data) => <DecisionsBody data={data} />}</WithData>
}
