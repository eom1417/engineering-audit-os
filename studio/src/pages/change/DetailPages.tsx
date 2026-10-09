// The plan's detail pages. #/plans/<planId>/<stepId>: a step with its exit gate, task states, waves, the steps it waits
// for and comes before, its operations and its tasks (selectable for the command centre), and the request that starts
// it. #/tasks/<taskId>: a task (a card) in its plan: step, wave, what it waits for, its operations and gap.
// #/ops/<opId>: an operation: on what, to what, why, its place in the order, what it waits for and comes before, its
// cards and its gap.
import { useParams } from '@tanstack/react-router'
import { useMemo, type ReactNode } from 'react'
import { buttonClass } from '../../components/Button'
import { DirectAction } from '../../command/Direct'
import { useBranchWords } from '../../branches/words'
import { OperationChip, SeverityGlyph } from '../../components/Chip'
import { Go } from '../../components/Go'
import { FoldList, Panel, Props, RowLink, Section, StateMessage } from '../../components/Panel'
import { ListTools, SelectableRow } from '../../command/Selectable'
import type { StudioData } from '../../data/types'
import { Id, N, Txt } from '../../i18n/text'
import { usePageChrome } from '../../shell/chrome'
import { layout as page, MissingBanner, WithData } from '../../shell/Layout'
import { usePaths } from '../paths/model'
import { byId, cardState, comesBefore, RELATION_OF, stateCounts, stepLinks } from './model'
import { ChangeNav, GapLink, LinkList, NotMeasured, OpLink, StateBar, StepLink } from './parts'
import { STATE_WORD, useChangeWords } from './words'
import css from './change.module.css'

type Row = [ReactNode, ReactNode]

function Missing({ title, id }: { title: string; id: string }) {
  return <div className={page.page}><ChangeNav /><Panel><StateMessage title={title} sub={<Id value={id} />} /></Panel></div>
}

function useTimeline(data: StudioData) {
  const paths = usePaths(data)
  return paths.kind === 'ready' ? paths.paths.timeline : null
}

function StepBody({ data, planId, stepId }: { data: StudioData; planId: string; stepId: string }) {
  const w = useChangeWords()
  const b = useBranchWords()
  const plan = data.plans?.plans.find((p) => p.id === planId)
  const step = plan?.steps.find((s) => s.id === stepId)
  usePageChrome(w('stepKicker', { id: stepId }), { to: `/plans/${encodeURIComponent(planId)}`, label: plan?.title ?? w('plansTitle') }, data.manifest.project.name)
  const timeline = useTimeline(data)
  const links = useMemo(() => stepLinks(timeline), [timeline])
  if (!plan || !step) return <Missing title={w('stepNotFound')} id={stepId} />
  const ops = (data.operations?.operations ?? []).filter((o) => o.step === step.id).sort((a, b) => a.order - b.order)
  const span = timeline?.steps.find((s) => s.id === step.id)
  const ids = step.tasks.map((t) => t.id)
  const waits = links.filter((l) => l.to === step.id)
  const before = links.filter((l) => l.from === step.id)
  return (
    <div className={page.page}>
      <MissingBanner data={data} />
      <ChangeNav />
      <div className={css.head}>
        <span className={css.kicker}>{w('stepKicker', { id: step.id })}</span>
        <h1 className={css.title}><Txt>{step.title ?? step.id}</Txt></h1>
        <StateBar counts={stateCounts(step)} />
        {ids.length > 0 && <DirectAction request={{ verb: 'fix', selection: { kind: 'step', step: step.id } }} label={b('startStep')}
          copy={{ request: w('stepRequest', { id: step.id }), tool: 'fix_start' }} />}
      </div>
      <div className={page.columns}>
        <div className={page.col}>
          <Section title={w('stepTasks')} count={ids.length}>
            <ListTools shown={ids} />
            <Panel>
              <FoldList items={step.tasks} first={12} label={w('stepTasks')} render={(task) => (
                <SelectableRow id={task.id} order={ids}>
                  <RowLink to={`/tasks/${encodeURIComponent(task.id)}`} title={<Txt>{task.title}</Txt>} sub={<Id value={task.id} />}
                    end={<span className={css.muted}>{w(STATE_WORD[cardState(task.state)])}</span>} />
                </SelectableRow>
              )} />
            </Panel>
          </Section>
        </div>
        <div className={page.col}>
          <Panel pad>
            <Props rows={[
              [w('gate'), <Txt key="g">{step.gate}</Txt>],
              ...(span && span.first !== null ? [[w('wave'), span.first === span.last ? <N key="w" value={span.first} /> : w('wavesSpan', { a: span.first, b: span.last ?? span.first })] as Row] : []),
              [w('waitsFor'), waits.length ? <LinkList key="a">{waits.map((l) => <StepLink key={l.from} plan={plan.id} step={l.from} />)}</LinkList> : w('waitsNone')],
              ...(before.length ? [[w('comesBefore'), <LinkList key="b">{before.map((l) => <StepLink key={l.to} plan={plan.id} step={l.to} />)}</LinkList>] as Row] : []),
            ]} />
          </Panel>
          {data.operations ? (
            <Section title={w('stepOps')} count={ops.length}>
              {ops.length > 0 && (
                <Panel>
                  <FoldList items={ops} first={8} label={w('stepOps')} render={(o) => (
                    <RowLink to={`/ops/${encodeURIComponent(o.id)}`} chevron={false} title={<Id value={o.subject} keep={3} />}
                      sub={<OperationChip relation={RELATION_OF[o.op]} to={o.target} />} end={<N value={o.order} className={css.muted} />} />
                  )} />
                </Panel>
              )}
            </Section>
          ) : <NotMeasured data={data} section="operations" title={w('stepOps')} />}
        </div>
      </div>
    </div>
  )
}

export function StepPage() {
  const { planId, stepId } = useParams({ strict: false }) as { planId?: string; stepId?: string }
  return <WithData>{(data) => <StepBody data={data} planId={decodeURIComponent(planId ?? '')} stepId={decodeURIComponent(stepId ?? '')} />}</WithData>
}

function TaskBody({ data, id }: { data: StudioData; id: string }) {
  const w = useChangeWords()
  const card = data.cards?.cards.find((c) => c.id === id)
  const plan = data.plans?.plans.find((p) => p.steps.some((s) => s.tasks.some((t) => t.id === id))) ?? data.plans?.plans[0]
  const step = plan?.steps.find((s) => s.tasks.some((t) => t.id === id))
  usePageChrome(id, step && plan ? { to: `/plans/${encodeURIComponent(plan.id)}/${encodeURIComponent(step.id)}`, label: w('stepKicker', { id: step.id }) } : { to: '/plans', label: w('plansTitle') }, data.manifest.project.name)
  const timeline = useTimeline(data)
  const row = timeline?.tasks.find((t) => t.id === id)
  if (!card) return <Missing title={w('taskNotFound')} id={id} />
  const ops = (data.operations?.operations ?? []).filter((o) => o.op !== 'merge' && o.cards?.includes(id))
  const gaps = (data.gaps?.gaps ?? []).filter((g) => !g.id.startsWith('target:') && g.cards.includes(id))
  return (
    <div className={page.page}>
      <MissingBanner data={data} />
      <ChangeNav />
      <div className={css.head}>
        <span className={css.kicker}>{w('taskKicker')} · <Id value={id} /></span>
        <h1 className={css.title}><Txt>{card.title}</Txt></h1>
        <span className={css.chips}><SeverityGlyph severity={card.severity} /><span className={css.muted}>{w(STATE_WORD[cardState(card.state)])}</span></span>
        <Go to="/problems" search={{ card: id }} className={buttonClass('primary')}>{w('openProblem')}</Go>
      </div>
      <div className={page.columns}>
        <div className={page.col}>
          <Section title={w('taskWaits')} count={row ? row.waits.length + row.more : undefined}>
            <Panel>
              {row && row.waits.length ? (
                <ul aria-label={w('taskWaits')}>
                  {row.waits.map((wait) => (
                    <li key={wait.task}>
                      <RowLink to={`/tasks/${encodeURIComponent(wait.task)}`} title={<Id value={wait.task} />}
                        sub={<>{w(wait.why === 'prerequisite' ? 'why_prerequisite' : 'why_same_file')}{wait.why === 'same_file' && wait.detail ? <> · <Id value={wait.detail} keep={2} /></> : null}</>} />
                    </li>
                  ))}
                </ul>
              ) : <StateMessage title={row ? w('taskWaitsNone') : w('notMeasured')} />}
            </Panel>
          </Section>
        </div>
        <div className={page.col}>
          <Panel pad>
            <Props rows={[
              [w('inStep'), step && plan ? <StepLink key="s" plan={plan.id} step={step.id} /> : w('notPlanned')],
              ...(row ? [[w('wave'), <N key="w" value={row.wave} />] as Row] : []),
              [w('partOf'), ops.length ? <LinkList key="o">{ops.map((o) => <OpLink key={o.id} id={o.id} />)}</LinkList> : '—'],
              [w('itsGap'), gaps.length ? <LinkList key="g">{gaps.map((g) => <GapLink key={g.id} id={g.id} />)}</LinkList> : '—'],
            ]} />
          </Panel>
        </div>
      </div>
    </div>
  )
}

export function TaskPage() {
  const { taskId } = useParams({ strict: false }) as { taskId?: string }
  return <WithData>{(data) => <TaskBody data={data} id={decodeURIComponent(taskId ?? '')} />}</WithData>
}

function OpBody({ data, id }: { data: StudioData; id: string }) {
  const w = useChangeWords()
  const all = useMemo(() => [...(data.operations?.operations ?? [])].sort((a, b) => a.order - b.order), [data.operations])
  const op = all.find((o) => o.id === id)
  usePageChrome(op?.subject ?? w('operations'), { to: `/plans/${encodeURIComponent(op?.plan ?? 'fix')}`, search: { view: 'board' }, label: w('viewBoard') }, data.manifest.project.name)
  const cards = useMemo(() => byId(data.cards?.cards), [data.cards])
  if (!data.operations) return <div className={page.page}><ChangeNav /><NotMeasured data={data} section="operations" title={w('noOps')} /></div>
  if (!op) return <Missing title={w('opNotFound')} id={id} />
  const before = comesBefore(op, all)
  const own = op.cards ?? []
  return (
    <div className={page.page}>
      <MissingBanner data={data} />
      <ChangeNav />
      <div className={css.head}>
        <span className={css.kicker}>{w('opKicker', { n: op.order, t: all.length })}</span>
        <h1 className={css.title}><Id value={op.subject} /></h1>
        <span className={css.chips}><OperationChip relation={RELATION_OF[op.op]} to={op.op === 'merge' || op.op === 'new' ? null : op.target} /><span className={css.muted}>{w(STATE_WORD[op.state])}</span></span>
      </div>
      <div className={page.columns}>
        <div className={page.col}>
          <Section title={w('why')}><Panel pad><Txt block>{op.reason}</Txt></Panel></Section>
          <Section title={w('itsCards')} count={own.length}>
            <Panel>
              {own.length ? (
                <FoldList items={own} first={8} label={w('itsCards')} render={(cid) => (
                  <RowLink to={`/tasks/${encodeURIComponent(cid)}`} title={<Txt>{cards.get(cid)?.title ?? cid}</Txt>} sub={<Id value={cid} />} />
                )} />
              ) : <StateMessage title={w('noCards')} />}
            </Panel>
          </Section>
          {(op.sources ?? []).length > 0 && (
            <Section title={w('sources')} count={op.sources!.length}>
              <Panel><FoldList items={op.sources!} first={8} label={w('sources')} render={(s) => <RowLink to={`/change/gaps/${encodeURIComponent(s)}`} title={<Id value={s} keep={3} />} />} /></Panel>
            </Section>
          )}
        </div>
        <div className={page.col}>
          <Panel pad>
            <Props rows={[
              [w('subject'), <Id key="s" value={op.subject} keep={3} />],
              ...(op.target && op.target !== op.subject ? [[w('colTo'), <Id key="t" value={op.target} />] as Row] : []),
              ...(typeof op.files === 'number' ? [[w('files'), <N key="f" value={op.files} />] as Row] : []),
              [w('inStep'), op.step ? <StepLink key="st" plan={op.plan ?? 'fix'} step={op.step} /> : w('notPlanned')],
              [w('itsGap'), op.gap ? <GapLink key="g" id={op.gap} /> : '—'],
            ]} />
          </Panel>
          <Section title={w('after')} count={op.after.length}>
            <Panel pad>
              {op.after.length ? <><LinkList>{op.after.map((a) => <OpLink key={a} id={a} />)}</LinkList><p className={css.muted}>{w('afterHow')}</p></> : <span className={css.muted}>{w('afterNone')}</span>}
            </Panel>
          </Section>
          {before.length > 0 && (
            <Section title={w('before')} count={before.length}>
              <Panel pad><LinkList>{before.map((b) => <OpLink key={b.id} id={b.id} />)}</LinkList></Panel>
            </Section>
          )}
        </div>
      </div>
    </div>
  )
}

export function OpPage() {
  const { opId } = useParams({ strict: false }) as { opId?: string }
  return <WithData>{(data) => <OpBody data={data} id={decodeURIComponent(opId ?? '')} />}</WithData>
}
