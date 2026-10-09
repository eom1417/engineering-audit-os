// #/plans: every plan with its state and progress (from the ledger only). #/plans/<planId>?view=timeline|graph|board: the
// plan board (C-experience 3.8): its state as a stepper, progress, the request for the next step that waits for nothing
// open, and three views: the steps in order with their task states and waits, the steps' dependency graph (a task of one
// waiting for a task of another), and the operations in order, one lane per kind. The phone keeps the timeline, with
// each step's waits written in its row, and the operations as one ordered list.
import { useNavigate, useParams, useSearch } from '@tanstack/react-router'
import { useMemo } from 'react'
import { CopyRequestButton } from '../../components/Button'
import { OperationChip } from '../../components/Chip'
import { Segmented } from '../../components/Controls'
import { Go } from '../../components/Go'
import { FoldList, Panel, RowLink, Section, StateMessage } from '../../components/Panel'
import { RELATION_OF, type ChangeOp, type Operation } from '../../data/change'
import type { Plan, PlanStep, StudioData } from '../../data/types'
import { usePrefs } from '../../i18n/prefs'
import { Id, N, Txt } from '../../i18n/text'
import { usePageChrome } from '../../shell/chrome'
import { layout as page, MissingBanner, PageTitle, WithData } from '../../shell/Layout'
import { usePhone } from '../SystemMap'
import { usePaths, type Timeline } from '../paths/model'
import { StepGraph } from './StepGraph'
import { nextStep, OP_LABEL, PLAN_STATES, stateCounts, stepLinks, type StepLink as Link } from './model'
import { ChangeNav, NotMeasured, StateBar } from './parts'
import { STATE_WORD, useChangeWords } from './words'
import css from './change.module.css'

type View = 'timeline' | 'graph' | 'board'

function planState(state: string, w: ReturnType<typeof useChangeWords>) {
  return (PLAN_STATES as readonly string[]).includes(state) ? w(`ps_${state as (typeof PLAN_STATES)[number]}`) : state
}

export function Progress({ plan }: { plan: Plan }) {
  const w = useChangeWords()
  const value = plan.progress.value
  if (value === null || value === undefined) return <span className={css.muted}>{w('notMeasured')}</span>
  if (value === 0) return <span className={css.muted}>{w('notStarted')}</span>
  return <span>{w('donePct', { p: Math.round(value * 100) })}</span>
}

function PlansBody({ data }: { data: StudioData }) {
  const w = useChangeWords()
  const { t } = usePrefs()
  usePageChrome(w('plansTitle'), { to: '/change', label: t('journeyAndPlan') }, data.manifest.project.name)
  const plans = data.plans?.plans ?? []
  return (
    <div className={page.page}>
      <MissingBanner data={data} />
      <ChangeNav />
      <PageTitle title={w('plansTitle')} lead={w('plansLead')} />
      {!data.plans ? <NotMeasured data={data} section="plans" title={w('noPlans')} /> : !plans.length ? <Panel><StateMessage title={w('noPlans')} /></Panel> : (
        <Panel>
          <ul aria-label={w('plansTitle')}>
            {plans.map((plan) => (
              <li key={plan.id}>
                <RowLink to={`/plans/${encodeURIComponent(plan.id)}`} icon="plan" title={<Txt>{plan.title ?? plan.id}</Txt>}
                  sub={<>{planState(plan.state, w)} · {w('stepsN', { n: plan.steps.length })} · {w('tasksN', { n: plan.steps.reduce((s, x) => s + x.tasks.length, 0) })}</>}
                  end={<Progress plan={plan} />} />
              </li>
            ))}
          </ul>
        </Panel>
      )}
    </div>
  )
}

export function PlansPage() {
  return <WithData>{(data) => <PlansBody data={data} />}</WithData>
}

/** The plan's life as stops; the current one marked (registered → approved → active → review → merged → closed). */
function Stepper({ state }: { state: string }) {
  const w = useChangeWords()
  const at = PLAN_STATES.indexOf(state as (typeof PLAN_STATES)[number])
  return (
    <ol className={css.stepper} aria-label={w('planState')}>
      {PLAN_STATES.map((s, i) => (
        <li key={s} data-past={i < at ? '' : undefined} aria-current={i === at ? 'step' : undefined}>
          <i aria-hidden="true" /><span>{w(`ps_${s}`)}</span>
        </li>
      ))}
    </ol>
  )
}

function waves(timeline: Timeline | null, step: string) {
  const row = timeline?.steps.find((s) => s.id === step)
  return row && row.first !== null && row.last !== null ? row : null
}

/** One step of the timeline: its place, title, exit gate, task states, waves and the steps it waits for. */
function StepRow({ plan, step, links, timeline }: { plan: Plan; step: PlanStep; links: Link[]; timeline: Timeline | null }) {
  const w = useChangeWords()
  const span = waves(timeline, step.id)
  const waits = links.filter((l) => l.to === step.id)
  const before = links.filter((l) => l.from === step.id)
  return (
    <Go to={`/plans/${encodeURIComponent(plan.id)}/${encodeURIComponent(step.id)}`} className={css.stepRow}>
      <Id value={step.id} className={css.stepId} />
      <span className={css.stepMain}>
        <span className={css.stepTitle}><Txt>{step.title ?? step.id}</Txt></span>
        {step.gate && <span className={css.stepGate}><Txt>{step.gate}</Txt></span>}
        <StateBar counts={stateCounts(step)} />
        <span className={css.stepMeta}>
          {span && <span>{span.first === span.last ? w('waveOne', { a: span.first! }) : w('wavesSpan', { a: span.first!, b: span.last! })}</span>}
          <span>{waits.length ? <>{w('waitsFor')}: {waits.map((l, i) => <span key={l.from}>{i ? w('sep') : ''}<Id value={l.from} /></span>)}</> : w('waitsNone')}</span>
          {before.length > 0 && <span>{w('comesBefore')}: {before.map((l, i) => <span key={l.to}>{i ? w('sep') : ''}<Id value={l.to} /></span>)}</span>}
        </span>
      </span>
    </Go>
  )
}

function TimelineView({ plan, links, timeline }: { plan: Plan; links: Link[]; timeline: Timeline | null }) {
  const w = useChangeWords()
  return (
    <Section title={w('viewTimeline')} count={plan.steps.length}>
      <p className={css.muted}>{w('timelineLead')}</p>
      <Panel>
        <ol className={css.stepList} aria-label={w('viewTimeline')}>
          {plan.steps.map((step) => <li key={step.id}><StepRow plan={plan} step={step} links={links} timeline={timeline} /></li>)}
        </ol>
      </Panel>
      {timeline && <Panel><RowLink to="/change/timeline" icon="clock" title={w('openWaveGrid')} /></Panel>}
    </Section>
  )
}

/** The operations in order, one lane per kind (desktop) or one ordered list (phone). */
function Board({ ops, phone, plan }: { ops: Operation[]; phone: boolean; plan: Plan }) {
  const w = useChangeWords()
  const { t } = usePrefs()
  const sorted = [...ops].sort((a, b) => a.order - b.order)
  const kinds: ChangeOp[] = (['delete', 'refactor', 'rebuild', 'merge', 'new', 'retain'] as ChangeOp[]).filter((k) => sorted.some((o) => o.op === k))
  const card = (o: Operation) => (
    <Go to={`/ops/${encodeURIComponent(o.id)}`} className={css.opCard}>
      <span className={css.opOrder}><N value={o.order} /></span>
      <span className={css.opMain}>
        <Id value={o.subject} keep={2} />
        <span className={css.opMeta}>
          {o.step ? <Id value={o.step} /> : <span>{w('notPlanned')}</span>}
          <span>{w(STATE_WORD[o.state])}</span>
          {o.after.length > 0 && <span>{w('waitsFor')}: <N value={o.after.length} /></span>}
        </span>
      </span>
    </Go>
  )
  if (phone) {
    return (
      <Section title={w('viewBoard')} count={sorted.length}>
        <p className={css.muted}>{w('boardLead')}</p>
        <Panel>
          <FoldList items={sorted} first={12} label={w('viewBoard')} render={(o) => (
            <RowLink to={`/ops/${encodeURIComponent(o.id)}`} chevron={false} title={<><N value={o.order} />{'. '}<Id value={o.subject} keep={2} /></>}
              sub={<>{o.step ?? w('notPlanned')} · {w(STATE_WORD[o.state])}</>} end={<OperationChip relation={RELATION_OF[o.op]} />} />
          )} />
        </Panel>
      </Section>
    )
  }
  return (
    <Section title={w('viewBoard')} count={sorted.length}>
      <p className={css.muted}>{w('boardLead')}</p>
      <div className={css.lanes} data-plan={plan.id}>
        {kinds.map((k) => {
          const mine = sorted.filter((o) => o.op === k)
          return (
            <section key={k} className={css.lane} aria-label={`${t(OP_LABEL[k])} (${mine.length})`}>
              <h3 className={css.laneHead}><OperationChip relation={RELATION_OF[k]} /><N value={mine.length} className={css.muted} /></h3>
              <FoldList items={mine} first={8} label={t(OP_LABEL[k])} render={card} />
            </section>
          )
        })}
      </div>
    </Section>
  )
}

function PlanBody({ data, id }: { data: StudioData; id: string }) {
  const w = useChangeWords()
  const phone = usePhone()
  const navigate = useNavigate()
  const search = useSearch({ strict: false }) as { view?: string }
  const plan = data.plans?.plans.find((p) => p.id === id)
  usePageChrome(plan?.title ?? w('plansTitle'), { to: '/plans', label: w('plansTitle') }, data.manifest.project.name)
  const paths = usePaths(data)
  const timeline = paths.kind === 'ready' ? paths.paths.timeline : null
  const links = useMemo(() => stepLinks(timeline), [timeline])
  if (!plan) return <div className={page.page}><ChangeNav /><Panel><StateMessage title={w('planNotFound')} sub={<Id value={id} />} /></Panel></div>
  const ops = (data.operations?.operations ?? []).filter((o) => (o.plan ?? plan.id) === plan.id)
  const asked: View = search.view === 'graph' || search.view === 'board' ? search.view : 'timeline'
  const view: View = phone && asked === 'graph' ? 'timeline' : asked
  const options = [{ id: 'timeline' as View, label: w('viewTimeline') }, ...(phone ? [] : [{ id: 'graph' as View, label: w('viewGraph') }]), { id: 'board' as View, label: w('viewBoard') }]
  const next = nextStep(plan, links)
  const tasks = plan.steps.reduce((s, x) => s + x.tasks.length, 0)
  return (
    <div className={page.page}>
      <MissingBanner data={data} />
      <ChangeNav />
      <div className={css.head}>
        <span className={css.kicker}>{w('plansTitle')}</span>
        <h1 className={css.title}><Txt>{plan.title ?? plan.id}</Txt></h1>
        <Stepper state={plan.state} />
        <span className={css.metaLine}>
          <Progress plan={plan} /><span>{w('stepsN', { n: plan.steps.length })}</span><span>{w('tasksN', { n: tasks })}</span>
          {data.operations && <span>{w('opsN', { n: ops.length })}</span>}
        </span>
        {next && <CopyRequestButton variant="primary" tool="fix_start" label={`${w('copyStep')}: ${next.id}`} request={w('stepRequest', { id: next.id })} />}
      </div>
      <div className={css.toolbar}>
        <Segmented label={w('planView')} value={view} comfortable={phone}
          onChange={(v) => navigate({ to: `/plans/${encodeURIComponent(plan.id)}`, replace: true, search: v === 'timeline' ? {} : { view: v } })}
          options={options} />
      </div>
      {view === 'timeline' && <TimelineView plan={plan} links={links} timeline={timeline} />}
      {view === 'graph' && <StepGraph plan={plan} links={links} />}
      {view === 'board' && (data.operations ? <Board ops={ops} phone={phone} plan={plan} /> : <NotMeasured data={data} section="operations" title={w('noOps')} />)}
    </div>
  )
}

export function PlanPage() {
  const { planId } = useParams({ strict: false }) as { planId?: string }
  return <WithData>{(data) => <PlanBody data={data} id={decodeURIComponent(planId ?? '')} />}</WithData>
}
