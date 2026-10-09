// One function: a plain summary first, then its signature, size and complexity against Lizard's warning line, who calls
// it and what it calls (a two-step graph on wider screens, lists everywhere), the data it reads and writes, the
// problems on its lines and where it is. The first action opens its problem, else its most complex neighbour.
import { useMemo } from 'react'
import { SeverityGlyph } from '../../components/Chip'
import { Go } from '../../components/Go'
import { FoldList, Panel, Section, StateMessage } from '../../components/Panel'
import type { StudioData } from '../../data/types'
import { usePrefs } from '../../i18n/prefs'
import { Id, N, Txt } from '../../i18n/text'
import { usePhone } from '../SystemMap'
import { CallGraphView } from './CallGraph'
import { FnLink, Level } from './parts'
import { COMPLEX, level, riskiestNeighbour, type Fn, type FunctionsData, type Touch } from './model'
import { useFunctionWords } from './words'
import css from './Functions.module.css'

function Summary({ fn }: { fn: Fn }) {
  const w = useFunctionWords()
  const { lang } = usePrefs()
  const kind = w(`kind_${fn.kind}`)
  const k = lang === 'en' ? kind.toLowerCase() : kind
  const touch = (list: Touch[] | undefined) => (list ?? []).slice(0, 3).map((t) => t.name).join(lang === 'ar' ? '، ' : ', ') + ((list?.length ?? 0) > 3 ? '…' : '')
  const parts = [
    fn.lines.value !== null ? w('sumKind', { k, m: fn.module, l: fn.lines.value }) : w('sumKindNoSize', { k, m: fn.module }),
    fn.callers.length ? w('sumCalls', { a: fn.callers.length, b: fn.callees.length }) : w('sumNoCallers', { b: fn.callees.length }),
    fn.writes?.length ? w('sumWrites', { w: touch(fn.writes) }) : '',
    fn.reads?.length ? w('sumReads', { r: touch(fn.reads) }) : '',
    level(fn) === 'high' ? w('sumComplex', { c: fn.complexity.value ?? 0, t: COMPLEX }) : '',
  ].filter(Boolean)
  return <p className={css.summary}><Txt>{parts.join(' ')}</Txt></p>
}

function Metric({ label, value, note, src }: { label: string; value: number | null; note?: React.ReactNode; src?: string }) {
  const w = useFunctionWords()
  return (
    <div className={css.metric} title={src}>
      <dt>{label}</dt>
      <dd>{value === null ? <span className={css.muted}>{w('notMeasured')}</span> : <N value={value} className={css.metricN} />}</dd>
      {note && <dd className={css.metricNote}>{note}</dd>}
    </div>
  )
}

function Neighbours({ ids, byId, empty, title }: { ids: string[]; byId: Map<string, Fn>; empty: string; title: string }) {
  const w = useFunctionWords()
  const fns = ids.map((id) => byId.get(id)).filter((f): f is Fn => Boolean(f))
  return (
    <Section title={title} count={fns.length}>
      <Panel>
        {fns.length ? (
          <FoldList items={fns} first={6} label={title} render={(f) => (
            <FnLink id={f.id} className={css.row}>
              <span className={css.rowMain}>
                <span className={css.rowName}><Id value={f.name} /></span>
                <span className={css.rowSub}>{w(`kind_${f.kind}`)} · <Id value={f.module} keep={2} /></span>
              </span>
              <span className={css.rowEnd}><Level fn={f} /></span>
            </FnLink>
          )} />
        ) : <p className={css.empty}>{empty}</p>}
      </Panel>
    </Section>
  )
}

function Touches({ fn }: { fn: Fn }) {
  const w = useFunctionWords()
  const rows: [string, Touch[]][] = [[w('writes'), fn.writes ?? []], [w('reads'), fn.reads ?? []]]
  const any = rows.some(([, list]) => list.length)
  return (
    <Section title={w('data')}>
      <Panel pad>
        {any ? rows.filter(([, list]) => list.length).map(([label, list]) => (
          <div key={label} className={css.touchRow}>
            <span className={css.touchLabel}>{label}</span>
            <ul className={css.touchList}>
              {list.map((t) => <li key={t.kind + t.name} className={css.touch}><span className={css.touchKind}>{w(`touch_${t.kind}`)}</span><Id value={t.name} /></li>)}
            </ul>
          </div>
        )) : <p className={css.empty}>{w('noData')}</p>}
      </Panel>
    </Section>
  )
}

function Problems({ data, fn }: { data: StudioData; fn: Fn }) {
  const w = useFunctionWords()
  const cards = (fn.cards ?? []).map((id) => data.cards?.cards.find((c) => c.id === id)).filter((c): c is NonNullable<typeof c> => Boolean(c))
  return (
    <Section title={w('problems')} count={cards.length}>
      <Panel>
        {cards.length ? (
          <ul>{cards.map((c) => (
            <li key={c.id}>
              <Go to="/problems" search={{ card: c.id }} className={css.row}>
                <span className={css.rowMain}><span className={css.rowName}><Txt>{c.title}</Txt></span><span className={css.rowSub}><Id value={c.id} /></span></span>
                <span className={css.rowEnd}><SeverityGlyph severity={c.severity} /></span>
              </Go>
            </li>
          ))}</ul>
        ) : <p className={css.empty}>{w('noProblems')}</p>}
      </Panel>
    </Section>
  )
}

export function FunctionDetail({ data, fx, id }: { data: StudioData; fx: FunctionsData; id: string }) {
  const w = useFunctionWords()
  const phone = usePhone()
  const byId = useMemo(() => new Map(fx.functions.map((f) => [f.id, f])), [fx])
  const fn = byId.get(id)
  if (!fn) {
    return (
      <Panel>
        <StateMessage title={w('notFound')} sub={w('notFoundSub')} action={<div><Go to="/system/functions" className={css.inlineLink}>{w('backToList')}</Go></div>} />
      </Panel>
    )
  }
  const module = fx.modules.find((m) => m.id === fn.module)
  const firstCard = fn.cards?.[0]
  const neighbour = riskiestNeighbour(fn, byId)
  const at = level(fn)
  return (
    <article className={css.detail} aria-labelledby="fn-title">
      <div className={css.detailHead}>
        <span className={css.kicker}>{w(`kind_${fn.kind}`)}{fn.language ? <> · <Id value={fn.language} /></> : null}</span>
        <h1 id="fn-title" className={css.fnTitle}><Id value={fn.name} /></h1>
        <div className={css.crumbs}>
          <Go to="/system/functions" search={{ module: fn.module }} className={css.inlineLink}>
            <span><Id value={fn.module} />{module ? <> · {w('allInFile', { n: module.functions })}</> : null}</span>
          </Go>
          {module?.component && <Go to="/system" search={{ focus: module.component }} className={css.inlineLink}><span>{w('component')}: <Id value={module.component} /></span></Go>}
        </div>
      </div>
      <Summary fn={fn} />
      <div className={css.actions}>
        {firstCard ? <Go to="/problems" search={{ card: firstCard }} className={css.primary}>{w('openProblem')}</Go>
          : neighbour ? <FnLink id={neighbour.id} className={css.primary}>{w('openRiskiest', { f: neighbour.name })}</FnLink> : null}
      </div>
      <Panel pad>
        <dl className={css.metrics}>
          <Metric label={w('lines')} value={fn.lines.value} src={fn.lines.src} />
          <Metric label={w('complexity')} value={fn.complexity.value} src={fn.complexity.src}
            note={at === 'high' ? w('levelHigh', { t: COMPLEX }) : at === 'watch' ? w('levelWatch', { t: COMPLEX }) : at === 'ok' ? w('levelOk') : undefined} />
          <Metric label={w('calledBy')} value={fn.callers.length} />
          <Metric label={w('calls')} value={fn.callees.length} />
        </dl>
        <p className={css.src}>{w('source')}: <Id value={fn.complexity.src} /></p>
      </Panel>
      <Section title={w('signature')}>
        {fn.signature ? <pre className={css.code} dir="ltr" tabIndex={0}><code>{fn.signature}</code></pre> : <p className={css.empty}>{w('noSignature')}</p>}
      </Section>
      {!phone && (
        <Section title={w('graph')}>
          <Panel pad><CallGraphView fn={fn} byId={byId} /></Panel>
        </Section>
      )}
      <Neighbours ids={fn.callers} byId={byId} title={w('calledBy')} empty={w('nobodyCalls')} />
      <Neighbours ids={fn.callees} byId={byId} title={w('calls')} empty={w('callsNothing')} />
      <Touches fn={fn} />
      <Problems data={data} fn={fn} />
      <Section title={w('where')}>
        <Panel pad>
          <p className={css.where}>
            <Id value={fn.module} />
            {fn.line ? <> · {fn.end_line && fn.end_line !== fn.line ? w('linesOf', { a: fn.line, b: fn.end_line }) : w('lineOf', { a: fn.line })}</> : null}
            {fn.exported !== null && <> · {fn.exported ? w('exported') : w('internal')}</>}
          </p>
        </Panel>
      </Section>
    </article>
  )
}
