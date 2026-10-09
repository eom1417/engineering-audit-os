// #/evidence/<factId>: one fact on its own page: which engine saw what and where, the code at its line, the other
// places it names, and every problem that rests on it. Reached from a problem's evidence; the back button names the
// Problems list.
import { useParams } from '@tanstack/react-router'
import { useMemo } from 'react'
import { FindingRow } from '../../components/Finding'
import { Panel, Props, Section, StateMessage } from '../../components/Panel'
import type { StudioData } from '../../data/types'
import { Id, Txt } from '../../i18n/text'
import { usePageChrome } from '../../shell/chrome'
import { layout, MissingBanner, WithData } from '../../shell/Layout'
import { CodeExcerpt, Where } from './parts'
import { useProblemWords } from './words'
import pcss from '../Pages.module.css'
import css from './problems.module.css'

function EvidenceBody({ data, id }: { data: StudioData; id: string }) {
  const w = useProblemWords()
  const fact = (data.evidence?.facts ?? []).find((f) => f.id === id)
  const citing = useMemo(() => (data.cards?.cards ?? []).filter((c) => c.evidence.includes(id)), [data, id])
  usePageChrome(fact ? fact.id : w('evidenceTitle'), { to: '/problems', label: w('backToProblems') }, data.manifest.project.name)
  if (!fact) {
    return <div className={layout.page}><Panel><StateMessage kind="error" title={w('evidenceMissing', { id })} /></Panel></div>
  }
  const others = fact.sites.filter((s) => !(s.path === fact.path && (s.line ?? null) === fact.line))
  return (
    <div className={layout.page}>
      <MissingBanner data={data} />
      <article className={pcss.detail} aria-labelledby="fact-title">
        <div className={pcss.detailHead}>
          <span className={pcss.kindLabel}>{w('evidenceTitle')}</span>
          <h1 id="fact-title" className={pcss.detailTitle}><Txt block>{fact.summary}</Txt></h1>
          <Id value={fact.id} className={pcss.muted} />
        </div>
        <Props rows={[
          [w('kind'), <Id value={fact.kind} />],
          [w('engine'), fact.engine ? <Id value={fact.engine} /> : w('noEngine')],
          [w('place'), fact.path ? <Where path={fact.path} line={fact.line} /> : '—'],
        ]} />
        {fact.path && (
          <Section title={w('code')} id="code">
            <CodeExcerpt fact={fact} />
          </Section>
        )}
        {others.length > 0 && (
          <Section title={w('sites')} count={others.length} id="sites">
            <Panel>
              <ul className={css.sites}>{others.map((s, i) => <li key={i}><Where path={s.path} line={s.line} /></li>)}</ul>
            </Panel>
          </Section>
        )}
        <Section title={w('citedBy')} count={citing.length} id="cited-by">
          {citing.length ? (
            <Panel><ul className={css.rows}>{citing.map((card) => <li key={card.id}><FindingRow card={card} to="/problems" search={{ card: card.id }} /></li>)}</ul></Panel>
          ) : <Panel><StateMessage title={w('notCited')} /></Panel>}
        </Section>
      </article>
    </div>
  )
}

export function EvidencePage() {
  const { factId } = useParams({ strict: false }) as { factId: string }
  return <WithData>{(data) => <EvidenceBody data={data} id={factId} />}</WithData>
}
