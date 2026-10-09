// A card's detail: what it is, why it matters, where it is (file, component, map), how sure the check is, its
// evidence with the code at its line, its place in the plan (step, task, what happens to its component) and the other
// problems in the same file. The primary action is a request copied for the assistant.
import { useSearch } from '@tanstack/react-router'
import { useMemo } from 'react'
import { DirectAction } from '../../command/Direct'
import { Chip, OperationChip, SeverityGlyph } from '../../components/Chip'
import { FindingRow } from '../../components/Finding'
import { Go } from '../../components/Go'
import { FoldList, Panel, Props, Section, StateMessage } from '../../components/Panel'
import { componentOwner } from '../../command/groups'
import type { Card, StudioData } from '../../data/types'
import { usePrefs } from '../../i18n/prefs'
import { Id, Txt } from '../../i18n/text'
import { STATE_WORD, useValueLabel } from './labels'
import { Confidence, Evidence } from './parts'
import { useProblemWords } from './words'
import pcss from '../Pages.module.css'
import css from './problems.module.css'

function PlanPlace({ card, data }: { card: Card; data: StudioData }) {
  const w = useProblemWords()
  const step = (data.plans?.plans[0]?.steps ?? []).find((s) => s.id === card.milestone)
  const gap = (data.story?.gap ?? []).find((row) => row.cards.includes(card.id))
  if (!card.milestone) return <p className={css.muted}>{w('notInPlan')}</p>
  const index = step ? step.tasks.findIndex((task) => task.id === card.id) : -1
  return (
    <Panel pad className={css.plan}>
      <div className={css.planHead}>
        <span className={css.planStep}>{w('stepOf', { step: card.milestone })}</span>
        {step?.title && <span><Txt>{step.title}</Txt></span>}
        {index >= 0 && <span className={css.muted}>{w('taskOf', { k: index + 1, n: step!.tasks.length })}</span>}
      </div>
      {step?.gate && <p className={css.planGate}><span className={css.muted}>{w('stepGate')}</span> <Txt>{step.gate}</Txt></p>}
      {gap && (
        <div className={css.planOp}>
          <span className={css.muted}>{w('operation')}</span>
          <Id value={gap.component} keep={3} />
          <OperationChip relation={gap.relation} to={gap.to} />
        </div>
      )}
      <div><Go to="/change/timeline" search={{ step: card.milestone }} className={css.inlineLink}>{w('openTimeline')}</Go></div>
    </Panel>
  )
}

export function Detail({ card, data }: { card: Card; data: StudioData }) {
  const { t, lang } = usePrefs()
  const search = useSearch({ strict: false }) as Record<string, string | undefined>
  const w = useProblemWords()
  const label = useValueLabel()
  const facts = useMemo(() => new Map((data.evidence?.facts ?? []).map((fact) => [fact.id, fact])), [data])
  const owner = useMemo(() => componentOwner(data), [data])
  const cited = card.evidence.map((id) => facts.get(id)).filter((fact) => fact !== undefined)
  const component = card.paths[0] ? owner(card.paths[0]) : undefined
  const sameFile = useMemo(() => card.paths[0] ? (data.cards?.cards ?? []).filter((c) => c.id !== card.id && c.paths[0] === card.paths[0]) : [],
    [data, card])
  const why = card.why?.[lang]
  return (
    <article className={pcss.detail} aria-labelledby="card-title">
      <div className={pcss.detailHead}>
        <div className={pcss.chips}>
          <SeverityGlyph severity={card.severity} />
          <Chip tone={card.needs_decision ? 'accent' : 'neutral'}>{card.needs_decision ? t('needsYou') : t('eaosFixes')}</Chip>
          <Chip>{t(STATE_WORD[card.state])}</Chip>
        </div>
        <h1 id="card-title" className={pcss.detailTitle}><Txt block>{card.title}</Txt></h1>
        <Id value={card.id} className={pcss.muted} />
      </div>
      {why && (
        <Section title={w('whyItMatters')} id="why">
          <p className={css.why}><Txt block>{why}</Txt></p>
        </Section>
      )}
      <Props rows={[
        [w('place'), <span className={pcss.paths}>{card.paths.length ? card.paths.map((p) => <Id key={p} value={p} />) : '—'}</span>],
        ...(component ? [[w('component'), <Go to="/system" search={{ focus: component }} className={css.inlineLink}><Id value={component} keep={3} /></Go>] as [React.ReactNode, React.ReactNode]] : []),
        [w('area'), label('area', card.category)],
        [w('kind'), <Id value={card.kind} />],
        [w('confidence'), <Confidence value={card.confidence} />],
      ]} />
      <Section title={t('evidence')} count={cited.length} id="evidence">
        {cited.length ? cited.map((fact) => <Evidence key={fact.id} fact={fact} />) : <Panel><StateMessage title={w('noEvidence')} /></Panel>}
      </Section>
      <Section title={w('inThePlan')} id="plan">
        <PlanPlace card={card} data={data} />
      </Section>
      {sameFile.length > 0 && (
        <Section title={w('sameFile')} count={sameFile.length} id="same-file">
          <Panel>
            <FoldList items={sameFile} first={3} label={w('sameFile')} render={(other) => <FindingRow card={other} to="/problems" search={{ ...search, card: other.id }} />} />
          </Panel>
        </Section>
      )}
      <div>
        <DirectAction request={{ verb: 'explain', selection: { kind: 'card', cards: [card.id] } }} label={w('askAbout')} variant="secondary" icon="explain"
          copy={{ request: w('askRequest', { id: card.id }), tool: 'finding' }} />
      </div>
    </article>
  )
}
