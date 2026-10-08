// System: the project's components ranked by what they need, each with its operation toward the target. Desktop:
// the list beside the inspector; phone: the list, and the focused component pushed as its own view. The territory
// map (DESIGN.md §6) replaces the list's lead on desktop in a later task; the list stays as its non-visual twin.
import { useNavigate, useSearch } from '@tanstack/react-router'
import { useMemo } from 'react'
import { buttonClass } from '../components/Button'
import { OperationChip, SeverityGlyph } from '../components/Chip'
import { Go } from '../components/Go'
import { Icon } from '../components/Icon'
import { FoldList, Panel, Props, RowButton, Section, StateMessage } from '../components/Panel'
import type { Card, Relation, Severity, StudioData } from '../data/types'
import { usePrefs } from '../i18n/prefs'
import { Id, N } from '../i18n/text'
import { usePageChrome } from '../shell/chrome'
import { layout, MissingBanner, PageTitle, WithData } from '../shell/Layout'
import css from './Pages.module.css'

interface Component { name: string; files: number; relation: Relation; to: string | null; cards: Card[]; weight: number; bySeverity: Record<Severity, number> }

const WEIGHT: Record<Severity, number> = { critical: 8, high: 4, medium: 2, low: 1 }

/** Components with their cards (a card belongs to the deepest component holding its first path), by severity weight. */
export function components(data: StudioData): Component[] {
  const gap = new Map((data.story?.gap ?? []).map((row) => [row.component, row]))
  const names = (data.story?.current.components ?? []).map((c) => c.name).sort((a, b) => b.length - a.length)
  const owner = (path: string) => names.find((name) => name === '(root)' ? false : path === name || path.startsWith(name + '/')) ?? '(root)'
  const cardsOf = new Map<string, Card[]>()
  for (const card of data.cards?.cards ?? []) {
    const name = card.paths[0] ? owner(card.paths[0]) : '(root)'
    cardsOf.set(name, [...(cardsOf.get(name) ?? []), card])
  }
  return (data.story?.current.components ?? []).map((c) => {
    const cards = cardsOf.get(c.name) ?? []
    const bySeverity = { critical: 0, high: 0, medium: 0, low: 0 }
    for (const card of cards) bySeverity[card.severity] += 1
    const row = gap.get(c.name)
    return { name: c.name, files: c.files, relation: row?.relation ?? 'retain', to: row?.to ?? null, cards, bySeverity,
      weight: cards.reduce((sum, card) => sum + WEIGHT[card.severity], 0) }
  }).sort((a, b) => b.weight - a.weight || b.files - a.files || a.name.localeCompare(b.name))
}

function Inspector({ component }: { component: Component }) {
  const { t } = usePrefs()
  return (
    <div className={css.inspect}>
      <div className={css.inspectHead}>
        <span className={css.kindLabel}>{t('kindComponent')}</span>
        <h2 className={css.inspectTitle}><Id value={component.name} /></h2>
        <OperationChip relation={component.relation} to={component.to} />
      </div>
      <Props rows={[
        [t('files'), <N value={component.files} />],
        [t('problems'), <N value={component.cards.length} />],
        ...(['critical', 'high', 'medium', 'low'] as const).filter((s) => component.bySeverity[s]).map((s) => [<SeverityGlyph severity={s} />, <N value={component.bySeverity[s]} />] as [React.ReactNode, React.ReactNode]),
      ]} />
      {component.cards.length > 0 && (
        <Go to="/problems" search={{ component: component.name }} className={buttonClass('secondary', { block: true })}>
          {t('openItsFindings', { n: component.cards.length })}<Icon name="chevron" />
        </Go>
      )}
    </div>
  )
}

function SystemBody({ data }: { data: StudioData }) {
  const { t } = usePrefs()
  const { focus } = useSearch({ strict: false }) as { focus?: string }
  const navigate = useNavigate()
  const all = useMemo(() => components(data), [data])
  const focused = all.find((c) => c.name === focus)
  usePageChrome(focused ? focused.name : t('system'), focused ? { to: '/system', label: t('system') } : undefined, data.manifest.project.name)

  const list = (
    <Section title={t('rankedComponents')} count={all.length}>
      <Panel>
        <FoldList items={all} first={12} label={t('rankedComponents')} render={(c) => (
          <RowButton pressed={c.name === focus} onPress={() => navigate({ to: '/system', search: { focus: c.name } })}
            title={<Id value={c.name} />} sub={<OperationChip relation={c.relation} to={c.to} />}
            end={<><N value={c.cards.length} /><span className="sr">{t('problems')}</span></>} />
        )} />
      </Panel>
    </Section>
  )

  return (
    <div className={layout.inspected}>
      <div className={[layout.page, focused && layout.phoneHidden].filter(Boolean).join(' ')}>
        <MissingBanner data={data} />
        <PageTitle title={t('systemMap')} />
        {list}
      </div>
      <aside className={layout.inspector} aria-label={t('inspector')}>
        {focused ? <Inspector component={focused} /> : <StateMessage icon="system" title={t('chooseComponent')} />}
      </aside>
      {focused && <div className={[layout.page, css.phoneOnly].join(' ')}><Inspector component={focused} /></div>}
    </div>
  )
}

export function SystemPage() {
  return <WithData>{(data) => <SystemBody data={data} />}</WithData>
}
