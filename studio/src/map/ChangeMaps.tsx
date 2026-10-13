// Change: today's architecture and the target side by side (stacked on the phone), every component coloured by its
// operation; choosing a component on one map lights its counterpart on the other (a component's target, or a target's
// sources). Below, the gap: every component that changes, with its operation and where it goes.
import { useNavigate, useSearch } from '@tanstack/react-router'
import { useMemo } from 'react'
import { OperationChip } from '../components/Chip'
import { Go } from '../components/Go'
import { Icon } from '../components/Icon'
import { FoldList, Panel } from '../components/Panel'
import type { CurrentNode, SystemMap } from '../data/system'
import { Id, N } from '../i18n/text'
import { counterpart, heaviestFirst } from './model'
import { Legend, MapCanvas } from './parts'
import { TerritoryMap } from './TerritoryMap'
import { useMapWords } from './words'
import css from './change.module.css'


function useCompare() {
  const search = useSearch({ strict: false }) as { focus?: string; side?: string }
  const navigate = useNavigate()
  const side = search.side === 'target' ? 'target' : 'current'
  const set = (id: string, on: 'current' | 'target') => navigate({
    to: '/change', replace: true,
    search: search.focus === id && side === on ? {} : { focus: id, ...(on === 'target' ? { side: 'target' } : {}) },
  })
  return { focus: search.focus, side, set }
}

export function CompareMaps({ system, phone }: { system: SystemMap; phone: boolean }) {
  const w = useMapWords()
  const { focus, side, set } = useCompare()
  if (phone) {
    return (
      <div className={css.stack}>
        {(['current', 'target'] as const).map((m) => {
          const view = m === 'target' ? system.target : system.current
          return (
            <Go key={m} to="/system" search={{ view: m === 'target' ? 'target' : 'change' }} className={css.card}
              label={m === 'target' ? w('mapAriaTarget', { c: view.nodes.length, r: view.regions.length, e: view.edges.length }) : w('mapAria', { c: view.nodes.length, r: view.regions.length, e: view.edges.length })}>
              <span className={css.cardHead}><span className={css.cardTitle}>{w(m === 'target' ? 'mapTarget' : 'mapToday')}</span>
                <span className={css.cardSub}><N value={view.nodes.length} /> {w(m === 'target' ? 'componentsInTarget' : 'componentsInCode')}</span><Icon name="chevron" /></span>
              <TerritoryMap view={view} mode={m === 'target' ? 'target' : 'change'} variant="preview" />
            </Go>
          )
        })}
        <Legend system={system} mode="change" view={system.current} inline />
        <Legend system={system} mode="target" view={system.target} inline />
      </div>
    )
  }
  const leftFocus = side === 'current' ? focus : undefined
  const rightFocus = side === 'target' ? focus : undefined
  return (
    <div className={css.compare}>
      <p className={css.hint}>{w('twoMapsHint')}</p>
      <div className={css.pair}>
        <MapCanvas system={system} mode="change" variant="compare" focus={leftFocus} lit={counterpart(system, 'target', rightFocus)}
          onFocus={(id) => set(id, 'current')} minimap={false} legend={false} className={css.pane}
          title={<h3 className={css.paneTitle}>{w('mapToday')}<span className={css.paneSub}><N value={system.current.nodes.length} /> {w('componentsInCode')}</span></h3>} />
        <MapCanvas system={system} mode="target" variant="compare" focus={rightFocus} lit={counterpart(system, 'current', leftFocus)}
          onFocus={(id) => set(id, 'target')} minimap={false} legend={false} className={css.pane}
          title={<h3 className={css.paneTitle}>{w('mapTarget')}<span className={css.paneSub}><N value={system.target.nodes.length} /> {w('componentsInTarget')}</span></h3>} />
      </div>
      <div className={css.legends}>
        <Legend system={system} mode="change" view={system.current} inline />
        <Legend system={system} mode="target" view={system.target} inline />
      </div>
    </div>
  )
}

/** Every component of today that changes, heaviest operation first, with where it goes. */
export function GapList({ system }: { system: SystemMap }) {
  const w = useMapWords()
  const rows = useMemo(() => heaviestFirst(system.current.nodes.filter((n) => n.op !== 'retain'), (n) => [n.op, n.findings.total, n.files, n.id]), [system])
  return (
    <Panel>
      <FoldList items={rows} first={8} label={w('gapList')} render={(n: CurrentNode) => (
        <Go to="/system" search={{ view: 'change', focus: n.id }} className={css.gapRow}>
          <span className={css.gapMain}>
            <Id value={n.id} keep={3} />
            <span className={css.gapSub}><OperationChip relation={n.op} to={n.target} /></span>
          </span>
          <span className={css.gapNums}>
            <span><N value={n.files} /> <span className={css.gapK}>{w('filesShort')}</span></span>
            <span><N value={n.findings.total} /> <span className={css.gapK}>{w('findingsShort')}</span></span>
          </span>
          <Icon name="chevron" className={css.chev} />
        </Go>
      )} />
    </Panel>
  )
}
