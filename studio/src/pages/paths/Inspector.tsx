// The details of what is chosen on a diagram: a step's evidence (fact, file and line, how the link to it is known),
// its part of today with the operation and the target it goes to, its cards and plan steps, the paths through it;
// a gap's reason and the calls the trace could not resolve; a cluster's steps and paths.
import { OperationChip } from '../../components/Chip'
import { Go } from '../../components/Go'
import { Icon } from '../../components/Icon'
import type { Relation } from '../../data/types'
import { Id, N } from '../../i18n/text'
import { opOf, targetOf, where, type CodePath, type Index, type PathOp, type PathsData } from './model'
import { GAP_WORD, HOW_WORD, LANE_WORD, usePathWords } from './words'
import css from './paths.module.css'

/** The paths' operations on the shared chip's words (refactor is the map's modify). */
export const RELATION: Record<PathOp, Relation> = { retain: 'retain', refactor: 'modify', rebuild: 'rebuild', merge: 'merge', delete: 'delete' }

function LinkRow({ to, search, children }: { to: string; search?: Record<string, string | undefined>; children: React.ReactNode }) {
  return <Go to={to} search={search} className={css.linkRow}><span>{children}</span><Icon name="chevron" /></Go>
}

export function PathLinks({ paths, current }: { paths: CodePath[]; current?: string }) {
  return (
    <div className={css.linkList}>
      {paths.slice(0, 12).map((p) => p.id === current ? null : (
        <LinkRow key={p.id} to={`/flows/${p.id}`}><Id value={p.title} /></LinkRow>
      ))}
    </div>
  )
}

export function NodeInspector({ data, index, id, path }: { data: PathsData; index: Index; id: string; path?: CodePath }) {
  const w = usePathWords()
  const n = index.node.get(id)
  if (!n) return null
  const op = opOf(data, n)
  const to = targetOf(data, n)
  const into = path?.steps.map((i) => data.edges[i]).find((e) => e.to === id)
  const on = (index.on.get(id) ?? []).map((p) => index.path.get(p)).filter(Boolean) as CodePath[]
  const at = where(n.path, n.line)
  return (
    <div className={css.inspect}>
      <div className={css.insHead}>
        <span className={css.insK}>{w(LANE_WORD[n.lane])}</span>
        <span className={css.insTitle}><Id value={n.label} /></span>
        {op && <OperationChip relation={RELATION[op]} to={to?.target} />}
      </div>
      {n.kind === 'gap' && n.reason && (
        <div className={css.gapBox} role="note">
          <span className={css.gapTitle}>{w(GAP_WORD[n.reason].title)}</span>
          <span>{w(GAP_WORD[n.reason].why)}</span>
        </div>
      )}
      {n.items.length > 0 && (
        <section className={css.insSec}>
          <h3 className={css.insH}>{w('unresolvedCalls')} <N value={Number(n.detail) || n.items.length} /></h3>
          <ul className={css.items}>
            {n.items.map((item, i) => <li key={i}><Id value={item.callee} /><Id value={where(item.path, item.line) ?? ''} keep={1} /></li>)}
          </ul>
        </section>
      )}
      {(at || n.fact || into) && (
        <section className={css.insSec}>
          <h3 className={css.insH}>{w('evidence')}</h3>
          <dl className={css.evid}>
            {at && <><dt>{w('file')}</dt><dd><Id value={at} /></dd></>}
            {n.fact && <><dt>{w('fact')}</dt><dd><Id value={n.fact} /></dd></>}
            {into && <><dt>{w('howKnown')}</dt><dd>{w(HOW_WORD[into.how])}{into.path && <> · <Id value={where(into.path, into.line) ?? ''} keep={2} /></>}</dd></>}
          </dl>
        </section>
      )}
      {n.kind !== 'gap' && (
        <section className={css.insSec}>
          <h3 className={css.insH}>{w('partToday')}</h3>
          {n.component ? (
            <dl className={css.evid}>
              <dt>{w('partToday')}</dt><dd><Id value={n.component} /></dd>
              <dt>{w('goesTo')}</dt><dd>{op === 'delete' ? w('removed') : to?.target ? <Id value={to.target} /> : w('noTarget')}</dd>
              {to?.layer && <><dt>{w('layer')}</dt><dd><Id value={to.layer} /></dd></>}
            </dl>
          ) : <p className={css.insP}>{w('noPart')}</p>}
          {n.component && (
            <div className={css.linkList}>
              <LinkRow to="/system" search={{ focus: n.component, view: 'change' }}>{w('openOnMap')}</LinkRow>
              <LinkRow to="/change" search={{ focus: n.component }}>{w('openGap')}</LinkRow>
              {n.cards.length > 0 && <LinkRow to="/problems" search={{ component: n.component }}>{w('itsCards', { n: n.cards.length })}</LinkRow>}
            </div>
          )}
        </section>
      )}
      {n.steps.length > 0 && (
        <section className={css.insSec}>
          <h3 className={css.insH}>{w('planSteps')}</h3>
          <div className={css.linkList}>
            {n.steps.map((s) => <LinkRow key={s} to="/change/timeline" search={{ step: s }}><Id value={s} /></LinkRow>)}
          </div>
        </section>
      )}
      {on.length > 0 && (
        <section className={css.insSec}>
          <h3 className={css.insH}>{w('onPaths', { n: n.paths })}</h3>
          <PathLinks paths={on} current={path?.id} />
        </section>
      )}
    </div>
  )
}

export function ClusterInspector({ data, index, id }: { data: PathsData; index: Index; id: string }) {
  const w = usePathWords()
  const c = data.overview.clusters.find((x) => x.id === id)
  if (!c) return null
  const paths = [...new Set(c.nodes.flatMap((n) => index.on.get(n) ?? []))].map((p) => index.path.get(p)).filter(Boolean) as CodePath[]
  const part = c.component ? data.components[c.component] : undefined
  return (
    <div className={css.inspect}>
      <div className={css.insHead}>
        <span className={css.insK}>{w(LANE_WORD[c.lane])} · {w('nodesN', { n: c.size })}</span>
        <span className={css.insTitle}><Id value={c.label} /></span>
        {part && <OperationChip relation={RELATION[part.op]} to={part.target} />}
      </div>
      {c.reason && (
        <div className={css.gapBox} role="note">
          <span className={css.gapTitle}>{w(GAP_WORD[c.reason].title)}</span>
          <span>{w(GAP_WORD[c.reason].why)}</span>
        </div>
      )}
      <section className={css.insSec}>
        <h3 className={css.insH}>{w('nodesN', { n: c.size })}</h3>
        <ul className={css.items}>
          {c.nodes.slice(0, 12).map((nid) => {
            const n = index.node.get(nid)
            return n ? <li key={nid}><Id value={n.label} /><span>{n.paths}</span></li> : null
          })}
        </ul>
      </section>
      <section className={css.insSec}>
        <h3 className={css.insH}>{w('onPaths', { n: paths.length })}</h3>
        <PathLinks paths={paths} />
      </section>
    </div>
  )
}
