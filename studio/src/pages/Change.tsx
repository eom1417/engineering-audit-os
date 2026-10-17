// Fixes (#/change): everything that changes the code. The branches waiting for approval first, then the fix plan's
// steps with their tasks (progress only from the ledger), and folded below them the way from today to the target.
import { Folded, Panel, RowLink, Section } from '../components/Panel'
import { Journey, PlanStrip } from '../components/Story'
import type { StudioData } from '../data/types'
import { usePrefs } from '../i18n/prefs'
import { Id, Txt } from '../i18n/text'
import { usePageChrome } from '../shell/chrome'
import { layout, MissingBanner, PageTitle, WithData } from '../shell/Layout'
import css from './Pages.module.css'
import { CompareMaps, GapList } from '../map/ChangeMaps'
import { JourneyStrip } from '../map/home'
import { useMapWords } from '../map/words'
import { usePhone } from './SystemMap'
import { TimelineEntry } from './paths/TimelinePage'
import { IdealEntry } from './ideal/IdealPage'
import { GroupBox, ListTools } from '../command/Selectable'
import { stepCards } from '../command/groups'
import { useCmdWords } from '../command/words'
import cmd from '../command/command.module.css'
import { ChangeNav } from './change/parts'
import { useChangeWords } from './change/words'
import { Approvals } from './change/Approvals'

function ChangeBody({ data }: { data: StudioData }) {
  const { t } = usePrefs()
  const w = useMapWords()
  const cw = useCmdWords()
  const phone = usePhone()
  const cw2 = useChangeWords()
  const system = data.system && data.system.current.nodes.length > 0 ? data.system : undefined
  usePageChrome(t('fixes'), undefined, data.manifest.project.name)
  const today = data.story?.current.components.length ?? null
  const changing = data.story ? data.story.gap.filter((row) => row.relation !== 'retain').length : null
  const target = data.story?.target.components.length ?? null
  const plan = data.plans?.plans[0]
  return (
    <div className={layout.page}>
      <MissingBanner data={data} />
      <ChangeNav />
      <PageTitle title={t('fixes')} lead={t('fixesLead')} />
      <Approvals />
      {plan && (
        <Section title={t('fixPlan')}>
          <PlanStrip plan={plan} to={`/plans/${encodeURIComponent(plan.id)}`} />
          <TimelineEntry data={data} />
          <ListTools shown={[]} />
          <Panel>
            <ol className={css.steps}>
              {plan.steps.map((step) => (
                <li key={step.id} className={[css.step, cmd.stepRow].join(' ')}>
                  <GroupBox ids={stepCards(data, step.id)} group={{ by: 'step', value: step.id, label: step.title ?? step.id }} label={cw('selectStep', { id: step.id })} />
                  <Id value={step.id} className={css.stepId} />
                  <span className={css.stepTitle}><Txt block>{step.title ?? step.gate}</Txt><span className={css.muted}>{cw2('tasksN', { n: step.tasks.length })}</span></span>
                </li>
              ))}
            </ol>
          </Panel>
        </Section>
      )}
      {/* From today to the target: below the plan and folded, opened when the person wants the why behind the steps */}
      <Folded className={css.fold} summary={t('fromTodayToTarget')}>
        <Section title={t('fromTodayToTarget')} unit={t('inComponents')}>
          {system ? <JourneyStrip data={data} system={system} /> : (
            <Journey label={t('fromTodayToTarget')} stages={[
              { key: t('today'), value: today, unit: t('componentsInCode'), to: '/system' },
              { key: t('changeStage'), value: changing, unit: t('componentsChange'), to: '/system' },
              { key: t('target'), value: target, unit: t('componentsInTarget'), to: '/change/ideal' },
            ]} />
          )}
        </Section>
        <IdealEntry data={data} />
        {system && (
          <Section title={w('twoMaps')}>
            <CompareMaps system={system} phone={phone} />
          </Section>
        )}
        {system && (
          <Section title={w('gapList')} count={system.current.nodes.filter((n) => n.op !== 'retain').length}>
            <GapList system={system} />
            <Panel>
              <RowLink to="/change/bridge" icon="change" title={cw2('bridgeTitle')} />
              <RowLink to="/change/gaps" icon="layers" title={cw2('gapsTitle')} />
            </Panel>
          </Section>
        )}
      </Folded>
    </div>
  )
}

export function ChangePage() {
  return <WithData>{(data) => <ChangeBody data={data} />}</WithData>
}
