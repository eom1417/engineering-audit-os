// Change -> Rules target against the planned ideal (#/change/ideal?view=<view>; docs/STUDIO.md D10, NS46.T16): for each
// view (structure, change, journeys, code paths, data, infrastructure, pipeline, plan order) the rules' target beside
// the ideal the person's assistant planned on top of it, every planned element with its evidence and its difference
// from the rules, then where the plan departs from the rules and why, and the questions waiting for the person.
// Desktop: the two sides as columns. Phone: the planned side first, then the rules, one column.
import { useNavigate, useSearch } from '@tanstack/react-router'
import { Chip, OperationChip } from '../../components/Chip'
import { Go } from '../../components/Go'
import { FoldList, Panel, Section, StateMessage } from '../../components/Panel'
import type { StudioData } from '../../data/types'
import { usePrefs } from '../../i18n/prefs'
import { Id, N, Txt } from '../../i18n/text'
import { usePageChrome } from '../../shell/chrome'
import { layout, MissingBanner, PageTitle, WithData } from '../../shell/Layout'
import { asIdeal, counts, differenceOf, RELATION, VIEWS, viewOf, type Element, type Ideal, type View, type ViewName } from './model'
import { useIdealWords, type IdealWord } from './words'
import css from './Ideal.module.css'

interface IdealSearch { view?: string }

function ElementRow({ element, view, planned }: { element: Element; view: View; planned: boolean }) {
  const w = useIdealWords()
  const diff = planned ? differenceOf(view, element) : undefined
  return (
    <div className={css.element}>
      <div className={css.elementHead}>
        <OperationChip relation={RELATION[element.operation]} />
        {diff && <span className={[css.diff, css[diff.kind]].join(' ')}>{w(diff.kind)}</span>}
      </div>
      <div className={css.elementTitle}><Txt>{element.title}</Txt></div>
      {planned && element.detail && <p className={css.detail}><Txt block>{element.detail}</Txt></p>}
      {diff?.kind === 'changed' && diff.rules && <p className={css.muted}>{w('rulesSaid', { o: w(`op_${diff.rules}` as IdealWord) })}</p>}
      {planned && element.cites.length > 0 && (
        <p className={css.cites}><span className={css.citesWord}>{w('cites')}:</span> {element.cites.slice(0, 4).map((c) => <Id key={c} value={c} className={css.cite} />)}
          {element.cites.length > 4 && <span className={css.muted}> +{element.cites.length - 4}</span>}</p>
      )}
      {!planned && <p className={css.muted}><Id value={element.id} keep={2} /></p>}
    </div>
  )
}

function Side({ title, summary, elements, view, planned, empty }:
  { title: string; summary: string; elements: Element[]; view: View; planned: boolean; empty: string }) {
  return (
    <Panel pad className={planned ? css.plannedSide : css.rulesSide} label={title}>
      <Section title={title} count={elements.length}>
        {summary && <p className={css.summary}><Txt block>{summary}</Txt></p>}
        {elements.length
          ? <FoldList items={elements} first={8} render={(e) => <ElementRow element={e} view={view} planned={planned} />} />
          : <p className={css.muted}>{empty}</p>}
      </Section>
    </Panel>
  )
}

function Provenance({ ideal }: { ideal: Ideal }) {
  const w = useIdealWords()
  const { lang } = usePrefs()
  const p = ideal.provenance
  const share = ideal.evidence.share.value
  return (
    <div className={css.provenance}>
      <p className={css.lead}><Txt block>{lang === 'ar' ? ideal.message.ar : ideal.message.en}</Txt></p>
      <div className={css.chips}>
        <Chip tone={p.method === 'planned' ? 'accent' : 'warning'}>{p.method === 'planned' ? w('planned') : w('rulesOnlyMethod')}</Chip>
        {p.assistant && <Chip dot={false}>{w('by', { a: p.assistant, m: p.model ?? '?' })}</Chip>}
        {p.at && <Chip dot={false}>{w('on', { d: p.at.slice(0, 10) })}</Chip>}
        {share !== null && <Chip tone={share === 1 ? 'good' : 'warning'}>{w('share', { p: Math.round(share * 100) })}</Chip>}
        {ideal.evidence.elements.value !== null && <Chip dot={false}>{w('elements', { n: ideal.evidence.elements.value })}</Chip>}
        {ideal.evidence.dropped.length > 0 && <Chip tone="warning">{w('dropped', { n: ideal.evidence.dropped.length })}</Chip>}
      </div>
    </div>
  )
}

function ViewPicker({ ideal, current, onPick }: { ideal: Ideal; current: ViewName; onPick: (v: ViewName) => void }) {
  const w = useIdealWords()
  return (
    <nav className={css.picker} aria-label={w('view')}>
      {VIEWS.map((name) => {
        const v = ideal.views[name]
        return (
          <button key={name} type="button" className={css.pick} aria-pressed={name === current} onClick={() => onPick(name)}>
            <span>{w(`view_${name}` as IdealWord)}</span>
            <span className={v.provenance.method === 'planned' ? css.markPlanned : css.markRules} aria-hidden="true" />
            <N value={v.planned?.count.value ?? 0} className={css.pickN} />
          </button>
        )
      })}
    </nav>
  )
}

function Counts({ view }: { view: View }) {
  const w = useIdealWords()
  const c = counts(view)
  const rows: [IdealWord, number][] = [['same', c.same], ['changed', c.changed], ['added', c.added], ['rulesOnly', c.rulesOnly]]
  return (
    <dl className={css.counts}>
      {rows.map(([k, n]) => <div key={k} className={[css.count, css[k]].join(' ')}><dt>{w(k)}</dt><dd><N value={n} /></dd></div>)}
    </dl>
  )
}

function IdealBody({ data, ideal }: { data: StudioData; ideal: Ideal }) {
  const w = useIdealWords()
  const { lang, t } = usePrefs()
  const search = useSearch({ strict: false }) as IdealSearch
  const navigate = useNavigate()
  const name = viewOf(search.view)
  const view = ideal.views[name]
  usePageChrome(w('short'), { to: '/change', label: t('journeyAndPlan') }, data.manifest.project.name)
  const pick = (v: ViewName) => navigate({ to: '/change/ideal', replace: true, search: { view: v === 'system' ? undefined : v } })
  const p = view.provenance
  const questions = ideal.questions.filter((q) => q.view === name)
  const message = lang === 'ar' ? p.message.ar : p.message.en
  return (
    <div className={layout.page}>
      <MissingBanner data={data} />
      <PageTitle title={w('title')} />
      <Provenance ideal={ideal} />
      <ViewPicker ideal={ideal} current={name} onPick={pick} />
      <div className={css.viewHead}>
        <h2 className={css.viewTitle}>{w(`view_${name}` as IdealWord)}</h2>
        {p.method === 'planned' && p.confidence !== null && <Chip dot={false}>{w('confidence', { p: Math.round(p.confidence * 100) })}</Chip>}
      </div>
      {view.planned ? <Counts view={view} /> : <Panel pad><StateMessage title={w('notPlanned')} sub={message} /></Panel>}
      <div className={css.sides}>
        {view.planned && <Side title={w('plannedSide')} summary={view.planned.summary} elements={view.planned.elements} view={view} planned empty={w('nothing')} />}
        <Side title={w('rulesSide')} summary={view.rules.summary} elements={view.rules.elements} view={view} planned={false} empty={w('nothing')} />
      </div>
      {p.departures.length > 0 && (
        <Section title={w('departures')} count={p.departures.length}>
          <div className={css.cards}>
            {p.departures.map((d, i) => (
              <Panel pad key={i}>
                <dl className={css.departure}>
                  <dt>{w('ruleSays')}</dt><dd><Txt block>{d.rule_says}</Txt></dd>
                  <dt>{w('planChose')}</dt><dd><Txt block>{d.plan_chose}</Txt></dd>
                  <dt>{w('because')}</dt><dd><Txt block>{d.because}</Txt></dd>
                </dl>
              </Panel>
            ))}
          </div>
        </Section>
      )}
      {questions.length > 0 && (
        <Section title={w('questions')} count={questions.length}>
          <div className={css.cards}>
            {questions.map((q) => (
              <Panel pad key={q.id}>
                <p className={css.question}><Txt block>{q.question}</Txt></p>
                {q.recommendation && <p className={css.muted}>{w('recommendation')}: <Txt>{q.recommendation}</Txt></p>}
              </Panel>
            ))}
          </div>
        </Section>
      )}
    </div>
  )
}

export function IdealPage() {
  const w = useIdealWords()
  return (
    <WithData>{(data) => {
      const ideal = asIdeal((data as unknown as { ideal?: unknown }).ideal)
      if (!ideal) return <div className={layout.page}><PageTitle title={w('title')} /><Panel><StateMessage title={w('noSection')} sub={w('noSectionSub')} /></Panel></div>
      return <IdealBody data={data} ideal={ideal} />
    }}</WithData>
  )
}

/** The way in from the Change page: the planned ideal's state and a link to compare it with the rules' target. */
export function IdealEntry({ data }: { data: StudioData }) {
  const w = useIdealWords()
  const { lang } = usePrefs()
  const ideal = asIdeal((data as unknown as { ideal?: unknown }).ideal)
  if (!ideal) return null
  const planned = VIEWS.filter((v) => ideal.views[v].provenance.method === 'planned').length
  return (
    <Panel pad className={css.entry}>
      <div className={css.chips}>
        <Chip tone={ideal.state === 'planned' ? 'accent' : 'warning'}>{ideal.state === 'planned' ? w('planned') : w('rulesOnlyMethod')}</Chip>
        <Chip dot={false}><N value={planned} /> / <N value={VIEWS.length} /></Chip>
      </div>
      <p className={css.lead}><Txt block>{lang === 'ar' ? ideal.message.ar : ideal.message.en}</Txt></p>
      <Go to="/change/ideal" className={css.entryLink}>{w('open')}</Go>
    </Panel>
  )
}
