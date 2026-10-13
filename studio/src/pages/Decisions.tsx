// Decisions: every question waiting for the person, one card each (Calm); the answered ones folded under one line.
import { useState, type ReactNode } from 'react'
import { Panel, StateMessage } from '../components/Panel'
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

/** The answered decisions, closed until the person opens them: they are a record, not a question. */
function Decided({ count, children }: { count: number; children: ReactNode }) {
  const { t } = usePrefs()
  const [open, setOpen] = useState(false)
  return (
    <details className={css.decided} onToggle={(e) => setOpen(e.currentTarget.open)}>
      <summary>{t('decidedAlready', { n: count })}</summary>
      {open && <div className={css.cards}>{children}</div>}
    </details>
  )
}

function DecisionsBody({ data }: { data: StudioData }) {
  const { t } = usePrefs()
  usePageChrome(t('decisions'), undefined, data.manifest.project.name)
  const responses = useActions().decisions
  const all = (data.decisions?.decisions ?? []).map((d) => responses.some((r) => r.id === d.id && r.response) ? { ...d, state: 'answered' as const } : d)
  const waiting = all.filter((d) => d.state === 'waiting')
  const decided = all.filter((d) => d.state !== 'waiting')
  const card = (d: (typeof all)[number]) => (
    <DecisionCard key={d.id} decision={d} cardsTo={d.blocks.every((b) => b.startsWith('TASK-')) ? { to: '/problems', search: { who: 'you' } } : undefined} />
  )
  const asked = useActions().questions.length
  return (
    <div className={layout.page}>
      <MissingBanner data={data} />
      <PageTitle title={t('waitingForYou')} />
      <RunQuestions />
      {waiting.length ? <div className={css.cards}>{waiting.map(card)}</div>
        : asked > 0 ? null : <Panel><StateMessage icon="inbox" title={t('nothingWaits')} sub={t('nothingWaitsSub')} /></Panel>}
      {decided.length > 0 && <Decided count={decided.length}>{decided.map(card)}</Decided>}
    </div>
  )
}

export function DecisionsPage() {
  // Before the first check there is no report, but the check itself may already ask (which branch): its question shows
  return <WithData empty={<RunQuestions />}>{(data) => <DecisionsBody data={data} />}</WithData>
}
