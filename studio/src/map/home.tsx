// The map's pieces on Home and Change: the journey Today → Change → Target in one unit (components), each number and
// each operation a link to the map that shows it; and the "Land of the project" card (the map's preview with its
// regions, each region a link to the map focused on its largest component).
import type { ReactNode } from 'react'
import { Go, type Search } from '../components/Go'
import { Icon } from '../components/Icon'
import { Panel } from '../components/Panel'
import type { Operation, SystemMap } from '../data/system'
import type { StudioData } from '../data/types'
import { usePrefs } from '../i18n/prefs'
import { N } from '../i18n/text'
import { opCount } from './model'
import { TerritoryMap } from './TerritoryMap'
import { OP_WORD, useMapWords } from './words'
import css from './home.module.css'

function OpLink({ system, op, view }: { system: SystemMap; op: Operation; view: 'change' | 'target' }) {
  const w = useMapWords()
  const n = view === 'target' ? system.target.nodes.filter((x) => x.op === op).length : opCount(system, op)
  if (!n) return null
  return (
    <Go to="/system" search={{ view, op }} className={css.opLink}>
      <span className={[css.dot, css[`op_${op}`]].join(' ')} aria-hidden="true" /><N value={n} /> {w(OP_WORD[op])}
    </Go>
  )
}

function Tile({ k, value, unit, to, search, children }: { k: string; value: number; unit: string; to: string; search?: Search; children?: ReactNode }) {
  return (
    <div className={css.tile}>
      <Go to={to} search={search} className={css.tileMain}>
        <span className={css.tileK}>{k}</span>
        <span className={css.tileN}><N value={value} /></span>
        <span className={css.tileU}>{unit}</span>
      </Go>
      {children && <div className={css.tileSub}>{children}</div>}
    </div>
  )
}

/** Today → Change → Target: components today, those that change (by operation), and the target's components. */
export function JourneyStrip({ data, system }: { data: StudioData; system: SystemMap }) {
  const w = useMapWords()
  const today = system.current.nodes.length
  const changing = system.current.nodes.filter((n) => n.op !== 'retain').length
  const waiting = (data.decisions?.decisions ?? []).some((d) => d.id === 'target-architecture' && d.state === 'waiting')
  const arrow = <span className={css.arrow} aria-hidden="true"><Icon name="arrow" /></span>
  return (
    <nav className={css.journey} aria-label={w('journey')}>
      <Tile k={w('mapToday')} value={today} unit={w('componentsInCode')} to="/system">
        <OpLink system={system} op="retain" view="change" />{opCount(system, 'retain') > 0 && <span className={css.word}>{w('stayAsIs')}</span>}
      </Tile>
      {arrow}
      <Tile k={w('mapChange')} value={changing} unit={w('componentsChange')} to="/system" search={{ view: 'change' }}>
        <OpLink system={system} op="rebuild" view="change" /><OpLink system={system} op="modify" view="change" /><OpLink system={system} op="delete" view="change" />
      </Tile>
      {arrow}
      <Tile k={w('mapTarget')} value={system.target.nodes.length} unit={w('componentsInTarget')} to="/system" search={{ view: 'target' }}>
        <OpLink system={system} op="introduce" view="target" /><OpLink system={system} op="merge" view="target" />
        {waiting ? <Go to="/decisions" className={css.opLink}>{w('targetProposed')}</Go> : null}
      </Tile>
    </nav>
  )
}

/** Desktop: the preview beside the regions table; phone: one row with a small map. */
export function LandCard({ system, compact }: { system: SystemMap; compact?: boolean }) {
  const w = useMapWords()
  const { lang } = usePrefs()
  const view = system.current
  const sub = w('landSub', { c: view.nodes.length, r: view.regions.length })
  if (compact) {
    return (
      <Panel>
        <Go to="/system" className={css.landRow}>
          <span className={css.thumb}><TerritoryMap view={view} mode="change" variant="preview" /></span>
          <span className={css.landText}>
            <span className={css.landTitle}>{w('land')}</span>
            <span className={css.landSub}>{sub} · {w('landUnit', { e: view.edges.length })}</span>
          </span>
          <Icon name="chevron" className={css.chev} />
        </Go>
      </Panel>
    )
  }
  return (
    <Panel className={css.land}>
      <Go to="/system" className={css.landMap} label={w('openMap')}>
        <TerritoryMap view={view} mode="change" variant="preview" label={w('mapAria', { c: view.nodes.length, r: view.regions.length, e: view.edges.length })} />
      </Go>
      <div className={css.landSide}>
        <table className={css.regions}>
          <thead>
            <tr><th scope="col">{w('region')}</th><th scope="col">{w('componentsShort')}</th><th scope="col">{w('filesShort')}</th><th scope="col">{w('findingsShort')}</th></tr>
          </thead>
          <tbody>
            {view.regions.map((r) => (
              <tr key={r.id}>
                <th scope="row">
                  <Go to="/system" search={{ focus: r.lead }} className={css.regLink}>
                    {r.name.ident ? <bdi dir="ltr" className="id">{r.name[lang]}</bdi> : r.name[lang]}
                  </Go>
                </th>
                <td><N value={r.components} /></td><td><N value={r.files} /></td><td className={css.strong}><N value={r.findings ?? 0} /></td>
              </tr>
            ))}
          </tbody>
        </table>
        <Go to="/system" className={css.open}>{w('openMap')}<Icon name="chevron" /></Go>
      </div>
    </Panel>
  )
}

/** Home's two map sections; on the phone they come after the decision and the next step (DESIGN.md §4). */
export function HomeMaps({ data }: { data: StudioData }) {
  const w = useMapWords()
  const system = data.system
  if (!system || system.current.nodes.length === 0) return null
  return (
    <>
      <section className={css.late} aria-labelledby="h-journey">
        <h2 className={css.secTitle} id="h-journey">{w('journey')}<span className={css.secUnit}>{w('inComponents')}</span></h2>
        <JourneyStrip data={data} system={system} />
      </section>
      <section className={css.late} aria-labelledby="h-land">
        <h2 className={css.secTitle} id="h-land">{w('land')}<span className={css.secUnit}>{w('landUnit', { e: system.current.edges.length })}</span></h2>
        <div className={css.wide}><LandCard system={system} /></div>
        <div className={css.narrow}><LandCard system={system} compact /></div>
      </section>
    </>
  )
}
