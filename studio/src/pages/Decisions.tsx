// Decisions: every question waiting for the person, one card each (Calm), then the answered ones.
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

function DecisionsBody({ data }: { data: StudioData }) {
  const { t } = usePrefs()
  usePageChrome(t('decisions'), undefined, data.manifest.project.name)
  const all = data.decisions?.decisions ?? []
  const ordered = [...all.filter((d) => d.state === 'waiting'), ...all.filter((d) => d.state !== 'waiting')]
  const asked = useActions().questions.length
  return (
    <div className={layout.page}>
      <MissingBanner data={data} />
      <PageTitle title={t('waitingForYou')} />
      <RunQuestions />
      {ordered.length === 0 && asked > 0 ? null : ordered.length === 0
        ? <Panel><StateMessage icon="inbox" title={t('nothingWaits')} sub={t('nothingWaitsSub')} /></Panel>
        : <div className={css.cards}>{ordered.map((d) => (
          <DecisionCard key={d.id} decision={d} cardsTo={d.blocks.every((b) => b.startsWith('TASK-')) ? { to: '/problems', search: { who: 'you' } } : undefined} />
        ))}</div>}
    </div>
  )
}

export function DecisionsPage() {
  return <WithData>{(data) => <DecisionsBody data={data} />}</WithData>
}
