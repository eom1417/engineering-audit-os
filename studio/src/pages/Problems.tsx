// Problems: the list (filterable by who acts, severity, component and words) and a card's detail with its evidence.
// Desktop: split panes, the list stays while the detail scrolls. Phone: the list, and the card pushed as its own
// view with a back button naming the list. NS37.T3 adds the virtualised list for 5,000 cards.
import { useNavigate, useSearch } from '@tanstack/react-router'
import { useMemo } from 'react'
import { Chip, SeverityGlyph } from '../components/Chip'
import { SearchField, Segmented } from '../components/Controls'
import { EvidenceCard, FindingRow } from '../components/Finding'
import { FoldList, Panel, Props, Section, StateMessage } from '../components/Panel'
import type { Card, StudioData } from '../data/types'
import { usePrefs } from '../i18n/prefs'
import { Id, Txt } from '../i18n/text'
import { buildIndex } from '../search'
import { usePageChrome } from '../shell/chrome'
import { layout, MissingBanner } from '../shell/Layout'
import { WithData } from '../shell/Layout'
import css from './Pages.module.css'
import { ownerOf } from '../map/model'
import { ListTools, SelectableRow } from '../command/Selectable'

type Who = 'all' | 'you' | 'eaos'
interface ProblemsSearch { card?: string; who?: Who; severity?: string; component?: string; q?: string }

const STATE_WORD = { open: 'stateOpen', in_batch: 'stateInBatch', on_branch: 'stateOnBranch', done: 'stateDone', resolved: 'stateResolved', skipped: 'stateSkipped' } as const

function Detail({ card, data }: { card: Card; data: StudioData }) {
  const { t } = usePrefs()
  const facts = useMemo(() => new Map((data.evidence?.facts ?? []).map((fact) => [fact.id, fact])), [data])
  const cited = card.evidence.map((id) => facts.get(id)).filter((fact) => fact !== undefined)
  return (
    <article className={css.detail} aria-labelledby="card-title">
      <div className={css.detailHead}>
        <div className={css.chips}>
          <SeverityGlyph severity={card.severity} />
          <Chip tone={card.needs_decision ? 'accent' : 'neutral'}>{card.needs_decision ? t('needsYou') : t('eaosFixes')}</Chip>
        </div>
        <h1 id="card-title" className={css.detailTitle}><Txt block>{card.title}</Txt></h1>
        <Id value={card.id} className={css.muted} />
      </div>
      <Props rows={[
        [t('where'), <span className={css.paths}>{card.paths.map((p) => <Id key={p} value={p} />)}</span>],
        [t('state'), t(STATE_WORD[card.state])],
        ...(card.milestone ? [[t('step'), <Id value={card.milestone} />] as [React.ReactNode, React.ReactNode]] : []),
      ]} />
      <Section title={t('evidence')} count={cited.length}>
        {cited.map((fact) => <EvidenceCard key={fact.id} fact={fact} />)}
      </Section>
    </article>
  )
}

function ProblemsBody({ data }: { data: StudioData }) {
  const { t, num } = usePrefs()
  const search = useSearch({ strict: false }) as ProblemsSearch
  const navigate = useNavigate()
  const cards = data.cards?.cards ?? []
  const index = useMemo(() => buildIndex(cards.map((c) => ({ id: c.id, kind: 'card', title: c.title, keywords: [c.id, ...c.paths].join(' '), to: '' }))), [cards])
  // A component's cards are those the map counts for it (map/model.ts ownerOf): one number on every page
  const owner = useMemo(() => data.system?.current.nodes.length ? ownerOf(data.system.current.nodes.map((n) => n.id)) : null, [data.system])
  const who: Who = search.who ?? 'all'
  const shown = useMemo(() => {
    const hits = search.q ? new Set(index.search(search.q, cards.length).map((e) => e.id)) : null
    return cards.filter((c) => (!hits || hits.has(c.id))
      && (who === 'all' || (who === 'you') === c.needs_decision)
      && (!search.severity || c.severity === search.severity || (search.severity === 'high' && c.severity === 'critical'))
      && (!search.component || (owner ? c.paths.length > 0 && owner(c.paths[0]) === search.component
        : c.paths.some((p) => p === search.component || p.startsWith(search.component + '/')))))
  }, [cards, index, search.q, search.severity, search.component, who, owner])
  const order = useMemo(() => shown.map((c) => c.id), [shown])
  const selected = cards.find((c) => c.id === search.card)
  const listName = t('problems')
  usePageChrome(selected ? selected.id : listName, selected ? { to: '/problems', search: { ...search, card: undefined }, label: listName } : undefined, data.manifest.project.name)
  const set = (patch: Partial<ProblemsSearch>) => navigate({ to: '/problems', search: { ...search, ...patch }, replace: true })

  return (
    <div className={layout.split}>
      <div className={[layout.listPane, selected && layout.phoneHidden].filter(Boolean).join(' ')}>
        <div className={layout.listHead}>
          <MissingBanner data={data} />
          <h1 className={css.listTitle}>{listName} <span className={css.muted}>{num(shown.length)}</span></h1>
          <SearchField label={t('search')} placeholder={t('search')} value={search.q ?? ''} onChange={(q) => set({ q: q || undefined })} />
          <Segmented label={t('problems')} value={who} onChange={(next) => set({ who: next === 'all' ? undefined : next })}
            options={[{ id: 'all', label: t('allProblems') }, { id: 'you', label: t('needsYou') }, { id: 'eaos', label: t('eaosFixes') }]} />
          {search.component && <Chip tone="accent"><Id value={search.component} /></Chip>}
          <ListTools shown={order} />
        </div>
        {shown.length === 0 ? <StateMessage title={t('noResults')} /> : (
          <FoldList items={shown} first={40} label={listName} render={(card) => (
            <SelectableRow id={card.id} order={order}>
              <FindingRow card={card} to="/problems" search={{ ...search, card: card.id }} current={card.id === search.card} />
            </SelectableRow>
          )} />
        )}
      </div>
      <div className={[layout.detailPane, !selected && layout.phoneHidden].filter(Boolean).join(' ')}>
        <div className={layout.page}>
          {selected ? <Detail card={selected} data={data} />
            : search.card ? <Panel><StateMessage kind="error" title={t('notFoundCard')} /></Panel>
              : <Panel><StateMessage icon="problems" title={t('chooseProblem')} /></Panel>}
        </div>
      </div>
    </div>
  )
}

export function ProblemsPage() {
  return <WithData>{(data) => <ProblemsBody data={data} />}</WithData>
}
