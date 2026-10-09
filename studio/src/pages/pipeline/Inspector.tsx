import { pipelineTitle, stageTitle } from './names'
// The details beside the pipeline map. With a stage chosen: its evidence (entry file:line, function, the code line),
// what it takes and gives, its tools and side effects, a router's branches, its failure routes, the hidden channels
// and the calls EAOS could not follow on it, its links with how each is known, the gap entries about it, its ideal,
// and the ways on: its own pipeline, its code path, its cards and plan steps, following its data. Without one: the
// pipeline's verdict and the view's story (the ideal's changes, the gap's entries, the rules).
import type { ReactNode } from 'react'
import { Button as AriaButton } from 'react-aria-components'
import { OperationChip } from '../../components/Chip'
import { Go, type Search } from '../../components/Go'
import { Icon } from '../../components/Icon'
import type { Relation } from '../../data/types'
import { Id, N, Txt } from '../../i18n/text'
import { gapsAbout, ordered, where, type GapEntry, type Op, type PipelineData, type Scope, type Site, type View } from './model'
import { KIND_WORD, usePipelineWords } from './words'
import { useNodeRuns } from './aiNodes'
import { usePrefs } from '../../i18n/prefs'
import frame from '../paths/paths.module.css'
import css from './panels.module.css'

/** The pipeline's operations on the shared chip's words (refactor is the map's modify, new its introduce). */
export const RELATION: Record<Op, Relation> = { retain: 'retain', refactor: 'modify', rebuild: 'rebuild', merge: 'merge', delete: 'delete', new: 'introduce' }

export function LinkRow({ to, search, children }: { to: string; search?: Search; children: ReactNode }) {
  return <Go to={to} search={search} className={frame.linkRow}><span>{children}</span><Icon name="chevron" /></Go>
}

function PickRow({ onPress, children }: { onPress: () => void; children: ReactNode }) {
  return <AriaButton onPress={onPress} className={[frame.linkRow, css.pick].join(' ')}><span>{children}</span><Icon name="chevron" /></AriaButton>
}

/** A piece of evidence: file and line, and the code line when EAOS kept it. */
export function Evidence({ site, label }: { site: Site; label?: string }) {
  const w = usePipelineWords()
  const at = where(site)
  if (!at && !site.fact) return null
  return (
    <dl className={frame.evid}>
      {at && <><dt>{label ?? w('file')}</dt><dd><Id value={at} /></dd></>}
      {site.fact && <><dt>{w('fact')}</dt><dd><Id value={site.fact} /></dd></>}
      {site.text && <><dt className={css.vh}>{w('evidence')}</dt><dd className={css.code}><code dir="ltr">{site.text}</code></dd></>}
    </dl>
  )
}

function Sec({ title, children }: { title: ReactNode; children: ReactNode }) {
  return <section className={frame.insSec}><h3 className={frame.insH}>{title}</h3>{children}</section>
}

export function GapItem({ g, n, onSubject }: { g: GapEntry; n: number; onSubject?: () => void }) {
  const w = usePipelineWords()
  return (
    <li className={css.gapItem}>
      <div className={css.gapHead}>
        <span className={css.gapNo}>{n}</span>
        <span className={css.rule}><Id value={g.rule} /></span>
        <OperationChip relation={RELATION[g.operation]} />
      </div>
      <p className={css.gapDetail}><Txt block>{g.detail}</Txt></p>
      <Evidence site={g.evidence} />
      <div className={css.gapLinks}>
        {onSubject && <AriaButton onPress={onSubject} className={css.inline}><Id value={g.subject} /></AriaButton>}
        {g.card ? <Go to="/problems" search={{ card: g.card }} className={css.inline}>{w('card')} <Id value={g.card} /></Go> : <span className={css.muted}>{w('noCard')}</span>}
        {g.step && <Go to="/change/timeline" search={{ step: g.step }} className={css.inline}>{w('step')} <Id value={g.step} /></Go>}
      </div>
    </li>
  )
}

/** An AI node's last run (studio/nodes.json): who decided it, how, and how many subjects each branch took. */
function AiNodeRun({ label }: { label: string }) {
  const w = usePipelineWords()
  const { lang } = usePrefs()
  const { state, nodes } = useNodeRuns(true)
  if (state === 'absent') return null
  if (!nodes) return <Sec title={w('aiNode')}><p className={frame.insP}>{w('aiLoading')}</p></Sec>
  const run = nodes.runs.get(label)
  if (!run) return null
  const pick = (words: { en: string; ar: string }) => (lang === 'ar' ? words.ar : words.en)
  if (run.state === 'not_run') return <Sec title={w('aiNode')}><p className={frame.insP}>{w('aiNotRun')}</p></Sec>
  const questions = run.decisions.reduce((n, d) => n + (d.open_questions?.length ?? 0), 0)
  return (
    <Sec title={w('aiNode')}>
      <p className={frame.insP}>
        {run.method === 'model' ? w('aiByModel', { who: run.assistant ?? '?', model: run.model ?? '?' }) : w('aiByRules')}
        {run.cached && <> · {w('aiCached')}</>}
        {run.at && <> · <Id value={w('aiAt', { at: run.at.slice(0, 16).replace('T', ' ') })} /></>}
        {run.seconds != null && <> · {w('aiCost', { s: Math.round(run.seconds), c: run.cost_usd != null ? run.cost_usd.toFixed(2) : '—' })}</>}
      </p>
      {run.method === 'rules' && run.why && <p className={frame.insP}><Txt>{run.why}</Txt></p>}
      <h4 className={css.aiRoutesH}>{w('aiRoutes')}</h4>
      <ul className={css.aiRoutes}>
        {run.routes.map((r) => (
          <li key={r.decision}>
            <span className={css.aiRouteHead}>
              <span className={css.cond}><Id value={r.decision} /></span>
              <span><N value={r.subjects} /> → {nodes.sinks.has(r.to) ? pick(nodes.sinks.get(r.to)!) : <Id value={r.to} />}</span>
            </span>
            <span className={css.muted}>{pick(r.when)}</span>
          </li>
        ))}
      </ul>
      {run.dropped.length > 0 && <p className={frame.insP}>{w('aiDropped', { n: run.dropped.length })}</p>}
      {questions > 0 && <><p className={frame.insP}>{w('aiQuestions', { n: questions })}</p><Go to="/decisions" className={css.aiInbox}>{w('aiToInbox')}</Go></>}
    </Sec>
  )
}

export function StageInspector({ data, scope, id, view, onSelect, onEnter, onFollow }:
  { data: PipelineData; scope: Scope; id: string; view: View; onSelect: (id: string) => void; onEnter: (pipeline: string) => void; onFollow: (name: string) => void }) {
  const w = usePipelineWords()
  const { lang } = usePrefs()
  const s = scope.stage.get(id)
  const ideal = scope.ideal.get(id)
  if (!s) {
    if (!ideal) return null
    return (
      <div className={frame.inspect}>
        <div className={frame.insHead}>
          <span className={frame.insK}>{w('addedByIdeal')}</span>
          <span className={frame.insTitle}><Id value={ideal.label} /></span>
          <OperationChip relation={RELATION[ideal.op]} />
        </div>
        {ideal.why && <p className={frame.insP}><Txt>{ideal.why}</Txt></p>}
        {ideal.rule && <p className={frame.insP}>{w('rule')} <Id value={ideal.rule} /></p>}
        <Contract ideal={ideal} />
      </div>
    )
  }
  const router = scope.routerOf.get(id)
  const fan = scope.fans.find((f) => f.fork === id || f.join === id || f.branches.includes(id))
  const control = scope.control.filter((c) => c.stage === id)
  const errors = scope.errors.filter((e) => e.from === id || e.from === '*')
  const hidden = scope.hidden.filter((h) => h.stages.includes(id))
  const unresolved = scope.unresolved.filter((u) => u.stage === id)
  const into = scope.edges.filter((e) => e.to === id)
  const out = scope.edges.filter((e) => e.from === id)
  const gaps = gapsAbout(scope, [id, ...(router ? [router.id] : []), ...hidden.map((h) => h.id), ...(fan ? [fan.id] : []), ...unresolved.map((u) => u.id)])
  const sub = s.sub_pipeline ? data.pipelines.find((p) => p.id === s.sub_pipeline) : undefined
  const label = (other: string) => scope.stage.get(other)?.label ?? other
  return (
    <div className={frame.inspect}>
      <div className={frame.insHead}>
        <span className={frame.insK}>{w(KIND_WORD[s.kind])}{s.optional && <> · {w('optional')}</>}{(s.marks ?? []).map((m) => <span key={m}> · {w.known('mark_', m)}</span>)}</span>
        <span className={frame.insTitle}>{stageTitle(s, lang)}</span><Id value={s.label} />
        {view !== 'current' && ideal && <OperationChip relation={RELATION[ideal.op]} />}
      </div>
      {gaps.length > 0 && (
        <Sec title={w('gap')}>
          <ol className={css.gapList}>{gaps.map((g) => <GapItem key={g.id} g={g} n={scope.gap.indexOf(g) + 1} />)}</ol>
        </Sec>
      )}
      {s.kind === 'ai' && <AiNodeRun label={s.label} />}
      <Sec title={w('evidence')}>
        <Evidence site={s.entry} label={w('entry')} />
        {s.symbol && <dl className={frame.evid}><dt>{w('symbol')}</dt><dd><Id value={s.symbol} /></dd></dl>}
      </Sec>
      <div className={css.ports}>
        <Ports title={w('takes')} rows={s.inputs} />
        <Ports title={w('gives')} rows={s.outputs} onFollow={onFollow} />
      </div>
      {s.tools.length > 0 && <Sec title={w('tools')}><div className={frame.chips}>{s.tools.map((t) => <span key={t} className={css.tool}><Id value={t} /></span>)}</div></Sec>}
      {s.side_effects.length > 0 && (
        <Sec title={w('sideEffects')}>
          <ul className={css.stack}>{s.side_effects.map((e, i) => <li key={i}><span>{w.known('', e.kind)} · <Id value={e.name} /></span><Id value={where(e) ?? ''} keep={1} /></li>)}</ul>
        </Sec>
      )}
      {router && (
        <Sec title={<>{w('branches')} <N value={router.branches.length} /></>}>
          <p className={frame.insP}>{w('routesOn')} <Id value={router.on} /> · {router.total === true ? w('totalYes') : router.total === false || router.unhandled.length ? w('totalNo', { v: router.unhandled.join(', ') || '…' }) : w('totalUnknown')}</p>
          <Evidence site={router.entry} />
          <ul className={css.branches}>
            {router.branches.map((b, i) => (
              <li key={i}>
                <span className={css.cond}><Id value={b.condition} /></span>
                {b.to ? <AriaButton className={css.inline} onPress={() => onSelect(b.to!)}><Id value={label(b.to)} /></AriaButton> : <span className={css.muted}>{w('noTarget')}</span>}
                <span className={css.muted}><Id value={where(b.evidence) ?? ''} keep={1} /></span>
              </li>
            ))}
          </ul>
          {router.default && <p className={frame.insP}>{w('defaultBranch')}: <Id value={router.default} /></p>}
        </Sec>
      )}
      {fan && (
        <Sec title={w('lgFork')}>
          <p className={frame.insP}>{w('fanOut', { n: fan.branches.length })} · {fan.join ? w('fanIn', { s: label(fan.join) }) : w('fanNoJoin')}</p>
          <Evidence site={fan.evidence} />
        </Sec>
      )}
      {control.length > 0 && (
        <Sec title={w('control')}>
          <ul className={css.stack}>{control.map((c) => <li key={c.id}><span>{w.known('control_', c.kind)}{c.condition && <> · <Id value={c.condition} /></>}</span><Id value={where(c.evidence) ?? ''} keep={1} /></li>)}</ul>
        </Sec>
      )}
      {errors.length > 0 && (
        <Sec title={w('failureRoutes')}>
          <ul className={css.stack}>{errors.map((e) => <li key={e.id}><span>{w.known('err_', e.kind)} → <Id value={e.to} />{e.condition && <> · <Id value={e.condition} /></>}{e.from === '*' && <> · {w('fromAny')}</>}</span><Id value={where(e.evidence) ?? ''} keep={1} /></li>)}</ul>
        </Sec>
      )}
      {hidden.length > 0 && (
        <Sec title={w('hidden')}>
          <ul className={css.stack}>{hidden.map((h) => <li key={h.id}><span>{w.known('hidden_', h.kind)} · <Id value={h.name} /></span><Id value={where(h.evidence) ?? ''} keep={1} /></li>)}</ul>
        </Sec>
      )}
      {unresolved.length > 0 && (
        <div className={frame.gapBox} role="note">
          <span className={frame.gapTitle}>{w('unresolved')}</span>
          {unresolved.map((u) => <span key={u.id}><Id value={u.call} /> · <Txt>{u.reason}</Txt> · <Id value={where(u.evidence) ?? ''} keep={2} /></span>)}
        </div>
      )}
      {(into.length > 0 || out.length > 0) && (
        <Sec title={w('links')}>
          <ul className={css.linkTable}>
            {[...into.map((e) => [e, 'in'] as const), ...out.map((e) => [e, 'out'] as const)].map(([e, dir]) => (
              <li key={e.id}>
                <AriaButton className={css.inline} onPress={() => onSelect(dir === 'in' ? e.from : e.to)}>
                  {dir === 'in' ? w('comesFrom') : w('goesTo')} <Id value={label(dir === 'in' ? e.from : e.to)} />
                </AriaButton>
                <span className={css.muted}>{w.known('matched_', e.matched_by)}{(e.data.shape || e.data.names[0]) && <> · <Id value={e.data.shape ?? e.data.names[0]} /></>} · <Id value={where(e.evidence) ?? ''} keep={1} /></span>
              </li>
            ))}
          </ul>
        </Sec>
      )}
      {view !== 'current' && ideal && (ideal.op !== 'retain' || ideal.why) && (
        <Sec title={w('ideal')}>
          {ideal.why && <p className={frame.insP}><Txt>{ideal.why}</Txt>{ideal.rule && <> · <Id value={ideal.rule} /></>}</p>}
          <Contract ideal={ideal} />
        </Sec>
      )}
      <div className={frame.linkList}>
        {sub && <PickRow onPress={() => onEnter(sub.id)}>{w('enter', { n: sub.stages.length })} · <Id value={sub.title} /></PickRow>}
        {s.entry.path && <LinkRow to="/system/paths" search={{ file: s.entry.path }}>{w('openCodePath')}</LinkRow>}
        {s.cards.map((c) => <LinkRow key={c} to="/problems" search={{ card: c }}>{w('card')} <Id value={c} /></LinkRow>)}
        {s.steps.map((st) => <LinkRow key={st} to="/change/timeline" search={{ step: st }}>{w('step')} <Id value={st} /></LinkRow>)}
      </div>
    </div>
  )
}

function Contract({ ideal }: { ideal: { contract?: { inputs: string[]; outputs: string[] } } }) {
  const w = usePipelineWords()
  if (!ideal.contract || (!ideal.contract.inputs.length && !ideal.contract.outputs.length)) return null
  return (
    <dl className={frame.evid}>
      <dt>{w('takes')}</dt><dd>{ideal.contract.inputs.length ? ideal.contract.inputs.map((n, i) => <span key={n}>{i > 0 && ' · '}<Id value={n} /></span>) : w('nothingDeclared')}</dd>
      <dt>{w('gives')}</dt><dd>{ideal.contract.outputs.length ? ideal.contract.outputs.map((n, i) => <span key={n}>{i > 0 && ' · '}<Id value={n} /></span>) : w('nothingDeclared')}</dd>
    </dl>
  )
}

function Ports({ title, rows, onFollow }: { title: string; rows: { name: string; kind: string; shape?: string | null }[]; onFollow?: (name: string) => void }) {
  const w = usePipelineWords()
  return (
    <section className={css.portCol}>
      <h3 className={frame.insH}>{title}</h3>
      {rows.length === 0 ? <span className={css.muted}>{w('nothingDeclared')}</span> : (
        <ul className={css.portList}>
          {rows.slice(0, 8).map((p) => (
            <li key={p.name}>
              {onFollow ? <AriaButton className={css.inline} onPress={() => onFollow(p.name)} aria-label={`${w('followFrom')}: ${p.name}`}><Id value={p.name} /></AriaButton> : <Id value={p.name} />}
              <span className={css.muted}>{w.known('', p.kind)}{p.shape && <> · <Id value={p.shape} /></>}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

/** The inspector before a stage is chosen: the verdict and what the view says. */
export function PipelineSummary({ data, scope, view, onSelect, onEnter }:
  { data: PipelineData; scope: Scope; view: View; onSelect: (id: string) => void; onEnter: (pipeline: string) => void }) {
  const w = usePipelineWords()
  const changed = ordered(scope.stages).filter((s) => { const op = scope.ideal.get(s.id)?.op; return op && op !== 'retain' })
  return (
    <div className={frame.inspect}>
      {view === 'current' && (
        <>
          <p className={frame.lead}>{w('chooseStage')}</p>
          {scope.unresolved.length > 0 && (
            <Sec title={<>{w('unresolved')} <N value={scope.unresolved.length} /></>}>
              <p className={frame.insP}>{w('unresolvedLead')}</p>
              <ul className={css.stack}>{scope.unresolved.map((u) => <li key={u.id}><AriaButton className={css.inline} onPress={() => onSelect(u.stage)}><Id value={u.call} /></AriaButton><Id value={where(u.evidence) ?? ''} keep={1} /></li>)}</ul>
            </Sec>
          )}
          {scope.hidden.length > 0 && (
            <Sec title={<>{w('hidden')} <N value={scope.hidden.length} /></>}>
              <p className={frame.insP}>{w('hiddenWhy')}</p>
              <ul className={css.stack}>{scope.hidden.map((h) => <li key={h.id}><span>{w.known('hidden_', h.kind)} · <Id value={h.name} /></span><Id value={where(h.evidence) ?? ''} keep={1} /></li>)}</ul>
            </Sec>
          )}
        </>
      )}
      {view === 'ideal' && (
        <>
          <p className={frame.lead}>{w('idealLead')}</p>
          <p className={css.muted}>{w.known('idealBy_', data.views.ideal.made_by)}</p>
          {changed.length > 0 && (
            <ul className={css.linkTable}>
              {changed.map((s) => { const i = scope.ideal.get(s.id)!; return (
                <li key={s.id}>
                  <AriaButton className={css.inline} onPress={() => onSelect(s.id)}><Id value={i.label} /></AriaButton>
                  <span className={css.opLine}><OperationChip relation={RELATION[i.op]} />{i.rule && <Id value={i.rule} />}</span>
                </li>
              ) })}
            </ul>
          )}
          {scope.added.length > 0 && (
            <Sec title={w('addedByIdeal')}>
              <p className={frame.insP}>{w('addedNote')}</p>
              <ul className={css.linkTable}>{scope.added.map((s) => <li key={s.id}><AriaButton className={css.inline} onPress={() => onSelect(s.id)}><Id value={s.label} /></AriaButton><span className={css.muted}>{s.why && <Txt>{s.why}</Txt>}</span></li>)}</ul>
            </Sec>
          )}
        </>
      )}
      {view === 'gap' && <GapPanel data={data} scope={scope} onSelect={onSelect} />}
      <PipelineTree data={data} current={scope.pipeline.id} onEnter={onEnter} />
    </div>
  )
}

/** The gap's entries, then the rules with how many times each is broken here and its source. */
export function GapPanel({ data, scope, onSelect }: { data: PipelineData; scope: Scope; onSelect: (id: string) => void }) {
  const w = usePipelineWords()
  const subjectStage = (g: GapEntry) => {
    const h = scope.hidden.find((x) => x.id === g.subject)
    const r = scope.routers.find((x) => x.id === g.subject)
    const f = scope.fans.find((x) => x.id === g.subject)
    const u = scope.unresolved.find((x) => x.id === g.subject)
    return h?.stages[0] ?? r?.stage ?? f?.fork ?? u?.stage ?? (scope.stage.has(g.subject) ? g.subject : undefined)
  }
  return (
    <>
      <p className={frame.lead}>{w('gapLead')}</p>
      {scope.gap.length === 0 ? <p className={frame.insP}>{w('gapEmpty')}</p> : (
        <ol className={css.gapList}>
          {scope.gap.map((g, i) => { const at = subjectStage(g); return <GapItem key={g.id} g={g} n={i + 1} onSubject={at ? () => onSelect(at) : undefined} /> })}
        </ol>
      )}
      <Sec title={w('rules')}>
        <ul className={css.rules}>
          {data.rules.map((r) => (
            <li key={r.id}>
              <div className={css.ruleHead}><Id value={r.id} /><span className={css.ruleTitle}><Txt>{r.title}</Txt></span>
                <span className={r.broken ? css.broken : css.holds}>{r.broken ? w('brokenN', { n: r.broken }) : w('holds')}</span></div>
              <span className={css.muted}><Txt>{r.source}</Txt></span>
            </li>
          ))}
        </ul>
      </Sec>
    </>
  )
}

/** Every pipeline EAOS found, nested under the stage it runs inside; the current one marked. */
export function PipelineTree({ data, current, onEnter }: { data: PipelineData; current: string; onEnter: (pipeline: string) => void }) {
  const w = usePipelineWords()
  const { lang } = usePrefs()
  if (data.pipelines.length < 2) return null
  const parentOf = (p: { parent: string | null }) => (p.parent ? data.stages.find((s) => s.id === p.parent)?.pipeline ?? null : null)
  const row = (id: string | null, depth: number): ReactNode[] => data.pipelines.filter((p) => parentOf(p) === id).flatMap((p) => [
    <li key={p.id} style={{ paddingInlineStart: depth * 14 }}>
      <AriaButton className={[css.treeRow, p.id === current && css.treeOn].filter(Boolean).join(' ')} onPress={() => onEnter(p.id)} aria-current={p.id === current ? 'true' : undefined}>
        <span>{pipelineTitle(p, lang)}</span>
        <span className={css.muted}>{w('stagesN', { n: p.stages.length })} · {w(p.role === 'product' ? 'role_product' : 'role_tooling')}</span>
      </AriaButton>
    </li>,
    ...(depth < 4 ? row(p.id, depth + 1) : []),
  ])
  return <Sec title={w('pipelines')}><ul className={css.tree}>{row(null, 0)}</ul></Sec>
}

/** What EAOS looked for, and how many of each it found. */
export function LookedFor({ data }: { data: PipelineData }) {
  const w = usePipelineWords()
  return (
    <ul className={css.looked}>
      {data.looked_for.map((l) => (
        <li key={l.kind}>
          <span>{w.known('pk_', l.kind)}</span>
          <span className={l.found ? css.foundYes : css.muted}>{l.found ? <>{w('found')} <N value={l.found} /></> : w('notFound')}</span>
        </li>
      ))}
    </ul>
  )
}
