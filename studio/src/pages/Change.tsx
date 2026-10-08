// Change: from today to the target in components, and the fix plan's steps with their tasks (progress only from the
// ledger). NS37.T3 and the plan pages of NS32 deepen it.
import { Panel, Section } from '../components/Panel'
import { Journey, PlanStrip } from '../components/Story'
import type { StudioData } from '../data/types'
import { usePrefs } from '../i18n/prefs'
import { Id, N, Txt } from '../i18n/text'
import { usePageChrome } from '../shell/chrome'
import { layout, MissingBanner, PageTitle, WithData } from '../shell/Layout'
import css from './Pages.module.css'

function ChangeBody({ data }: { data: StudioData }) {
  const { t } = usePrefs()
  usePageChrome(t('change'), undefined, data.manifest.project.name)
  const today = data.story?.current.components.length ?? null
  const changing = data.story ? data.story.gap.filter((row) => row.relation !== 'retain').length : null
  const target = data.story?.target.components.length ?? null
  const plan = data.plans?.plans[0]
  return (
    <div className={layout.page}>
      <MissingBanner data={data} />
      <PageTitle title={t('journeyAndPlan')} />
      <Section title={t('fromTodayToTarget')} unit={t('inComponents')}>
        <Journey label={t('fromTodayToTarget')} stages={[
          { key: t('today'), value: today, unit: t('componentsInCode'), to: '/system' },
          { key: t('changeStage'), value: changing, unit: t('componentsChange'), to: '/system' },
          { key: t('target'), value: target, unit: t('componentsInTarget'), to: '/change' },
        ]} />
      </Section>
      {plan && (
        <Section title={t('fixPlan')}>
          <PlanStrip plan={plan} to="/change" />
          <Panel>
            <ol className={css.steps}>
              {plan.steps.map((step) => (
                <li key={step.id} className={css.step}>
                  <Id value={step.id} className={css.stepId} />
                  <span className={css.stepTitle}><Txt block>{step.title ?? step.gate}</Txt></span>
                  <span className={css.muted}><N value={step.tasks.length} /></span>
                </li>
              ))}
            </ol>
          </Panel>
        </Section>
      )}
    </div>
  )
}

export function ChangePage() {
  return <WithData>{(data) => <ChangeBody data={data} />}</WithData>
}
