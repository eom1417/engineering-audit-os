// The pieces around the journeys map: the canvas (shared map frame, pan and zoom, legend), the legend, the inspector
// of a screen, of the menu and of a task, the overview, and the linear "steps" view that serves the phone and screen
// readers. Every element shows its evidence: the file and line that writes it, and the fact's id.
import { useEffect, useLayoutEffect, useRef, type ReactNode } from 'react'
import { Chip, OperationChip } from '../../../components/Chip'
import { Go } from '../../../components/Go'
import { FoldList, RowButton } from '../../../components/Panel'
import type { Hidden, JourneyEdge, Journeys, LinkSite, Screen, ScreenFlag, Task } from '../../../data/journeys'
import { usePrefs } from '../../../i18n/prefs'
import { Id, N } from '../../../i18n/text'
import { CanvasFrame, canvasClass } from '../../../map/parts'
import { useZoom } from '../../../map/useZoom'
import { useJourneyWords, type JourneyWord } from '../words'
import { JourneyMap } from './JourneyMap'
import { byDepth, FLAGS, linksOf, stepsOf, type JourneyMode } from './model'
import css from './Journeys.module.css'

const LINKABLE = new Set(['triggers', 'server', 'writes', 'outside', 'config'])

// ---------------------------------------------------------------- the canvas

export interface CanvasProps {
  journeys: Journeys
  mode: JourneyMode
  focus?: string
  task?: Task
  flag?: ScreenFlag
  showHidden: boolean
  unseen?: Map<string, number>
  onFocus: (id: string) => void
  title?: ReactNode
  head?: ReactNode
  className?: string
  legend?: boolean
  replace?: ReactNode
}

/** The map in the shared frame; it opens at a readable zoom on the start, and centres on a screen chosen elsewhere. */
export function JourneyCanvas({ journeys: j, mode, focus, task, flag, showHidden, unseen, onFocus, title, head, className, legend = true, replace }: CanvasProps) {
  const w = useJourneyWords()
  const svg = useRef<SVGSVGElement>(null)
  const zoom = useZoom(svg)
  const { setT } = zoom
  // a large map opens at a readable zoom on the start (top start corner of the geometry), once its box has a size;
  // before the first paint, so the map does not visibly slide there
  useLayoutEffect(() => {
    const el = svg.current
    if (!el || replace) return
    let done = false
    const apply = () => {
      const box = el.getBoundingClientRect()
      const vb = el.viewBox.baseVal
      if (done || !box.width || !box.height || !vb.width) return
      done = true
      const fit = Math.min(box.width / vb.width, box.height / vb.height)
      if (fit >= 0.8) return
      const k = Math.min(0.8 / fit, 8)
      const left = vb.x + vb.width / 2 - box.width / (2 * fit)
      const top = vb.y + vb.height / 2 - box.height / (2 * fit)
      setT({ k, x: left + 12 / fit - vb.x * k, y: top + 8 / fit - vb.y * k })
    }
    apply()
    const watch = new ResizeObserver(apply)
    watch.observe(el)
    return () => watch.disconnect()
  }, [setT, replace, j])
  const { centreOn } = zoom
  useEffect(() => {
    const s = focus ? j.screens.find((x) => x.id === focus) ?? j.menus.find((x) => x.id === focus) : undefined
    if (s) centreOn(s.x + j.grid.box_w / 2, s.y + j.grid.box_h / 2, 1)
  }, [focus, j, centreOn])
  const label = w('mapAria', { s: j.counts.screens.value ?? 0, l: j.counts.links.value ?? 0 })
  return (
    <CanvasFrame title={title} head={head} zoom={replace ? undefined : zoom} className={className}>
      {replace ?? (
        <div className={canvasClass.canvas}>
          <JourneyMap journeys={j} mode={mode} variant="full" focus={focus} task={task} flag={flag} showHidden={showHidden} unseen={unseen}
            onFocus={onFocus} transform={zoom.t} dragging={zoom.dragging} svgRef={svg} label={label} className={canvasClass.svg} />
          {legend && <Legend mode={mode} showHidden={showHidden} floating />}
        </div>
      )}
    </CanvasFrame>
  )
}

// ---------------------------------------------------------------- legend

function Swatch({ kind }: { kind: string }) {
  return (
    <svg width="26" height="14" viewBox="0 0 26 14" aria-hidden="true" className={[css.sw, css[`sw_${kind}`]].join(' ')}>
      {kind === 'screen' || kind === 'hidden' || kind.startsWith('op_') ? <rect x="1.5" y="1.5" width="23" height="11" rx="3" />
        : kind === 'undecided' ? <><circle cx="13" cy="7" r="5.5" /><text x="13" y="10" textAnchor="middle">?</text></>
        : <path d="M1 7h24" />}
    </svg>
  )
}

export function Legend({ mode, showHidden, floating }: { mode: JourneyMode; showHidden: boolean; floating?: boolean }) {
  const w = useJourneyWords()
  const rows: [string, JourneyWord][] = [['screen', 'lgScreen'], ['link', 'lgLink'], ['redirect', 'lgRedirect'], ['broken', 'lgBroken'], ['path', 'lgPath']]
  if (showHidden) rows.splice(1, 0, ['hidden', 'lgHidden'])
  if (mode === 'target') rows.push(['undecided', 'lgUndecided'])
  return (
    <div className={[css.legend, floating && css.legendFloat].filter(Boolean).join(' ')} role="group" aria-label={w('legend')}>
      <ul className={css.lgRows}>
        {rows.map(([kind, word]) => <li key={kind}><Swatch kind={kind} />{w(word)}</li>)}
      </ul>
      {mode !== 'current' && (
        <div className={css.lgOps}>
          <span className={css.lgCap}>{w('lgOpFolder')}</span>
          {(['retain', 'modify', 'rebuild', 'delete'] as const).map((op) => <OperationChip key={op} relation={op} />)}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------- evidence

export function Site({ site }: { site: { file: string | null; line?: number | null; fact?: string | null } }) {
  if (!site.file) return null
  return (
    <span className={css.site}>
      <Id value={site.line ? `${site.file}:${site.line}` : site.file} keep={3} />
      {site.fact && <Id value={site.fact} className={css.fact} />}
    </span>
  )
}

export function FlagChips({ flags }: { flags: ScreenFlag[] }) {
  const w = useJourneyWords()
  if (!flags.length) return null
  return <div className={css.chips}>{flags.map((f) => <Chip key={f} tone={f === 'broken_link' ? 'critical' : 'warning'}>{w(`flag_${f}`)}</Chip>)}</div>
}

function EdgeRow({ edge, other, j, onFocus }: { edge: JourneyEdge; other: string; j: Journeys; onFocus: (id: string) => void }) {
  const w = useJourneyWords()
  const screen = j.screens.find((s) => s.id === other)
  return (
    <RowButton onPress={() => onFocus(other)} chevron={false}
      title={other.startsWith('menu:') ? w('menu') : <Id value={screen?.route ?? other} />}
      sub={<>{edge.evidence.slice(0, 2).map((e, i) => <Site key={i} site={e} />)}{edge.count > 2 ? ` ${w('more', { n: edge.count - 2 })}` : ''}</>} />
  )
}

// ---------------------------------------------------------------- inspectors

export function ScreenPanel({ j, hidden, id, onFocus, onTask }: { j: Journeys; hidden?: Hidden; id: string; onFocus: (id: string) => void; onTask: (id: string) => void }) {
  const w = useJourneyWords()
  const { lang } = usePrefs()
  const s = j.screens.find((x) => x.id === id) as Screen
  const links = linksOf(j, id)
  const broken = j.broken.filter((b) => b.from === id)
  const tasks = j.tasks.filter((t) => t.screen === id || t.path.includes(id))
  const unseen = (hidden?.items ?? []).filter((i) => LINKABLE.has(i.group) && i.areas.includes(`area:${s.group}`))
  const viaMenu = s.menu && j.menus.some((m) => m.id === s.menu)
  return (
    <div className={css.panel}>
      <div className={css.kicker}>{w(`kind_${s.kind}`)}</div>
      <h2 className={css.panelTitle}><Id value={s.title} /></h2>
      <FlagChips flags={s.flags} />
      {s.flags.map((f) => <p key={f} className={css.why}>{w(`flagWhy_${f}`)}</p>)}
      <dl className={css.props}>
        <div><dt>{w('route')}</dt><dd><Id value={s.route} /></dd></div>
        {s.file && <div><dt>{w('file')}</dt><dd><Id value={s.file} keep={3} /></dd></div>}
        <div><dt>{w('declaredAt')}</dt><dd>{(s.declared ?? [{ file: s.router, line: s.line, fact: s.fact }]).map((d, i) => <Site key={i} site={d} />)}</dd></div>
        {s.twins && s.twins.length > 0 && <div><dt>{w('sameFile')}</dt><dd>{s.twins.map((t) => <button key={t} type="button" className={css.inline} onClick={() => onFocus(t)}><Id value={t} /></button>)}</dd></div>}
        {s.component && <div><dt>{w('folder')}</dt><dd><Id value={s.component} /></dd></div>}
      </dl>
      {s.op && (
        <div className={css.block}>
          <div className={css.blockTitle}>{w('folderOp')}</div>
          <OperationChip relation={s.op} to={s.target} />
          {!s.decided && <p className={css.note}>{w('noScreenDecision')}</p>}
          {s.component && <Go to="/problems" search={{ component: s.component }} className={css.link}>{w('openFindings')}</Go>}
        </div>
      )}
      <div className={css.block}>
        <div className={css.blockTitle}>{w('linksOut')} <N value={links.out.length} className={css.n} />{viaMenu ? <span className={css.muted}> · {w('viaMenu')}</span> : null}</div>
        {links.out.length ? <FoldList items={links.out} first={5} render={(e) => <EdgeRow edge={e} other={e.to} j={j} onFocus={onFocus} />} /> : <p className={css.muted}>{w('noLinksOut')}</p>}
      </div>
      {broken.length > 0 && (
        <div className={css.block}>
          <div className={css.blockTitle}>{w('brokenOut')} <N value={broken.length} className={css.n} /></div>
          <ul className={css.list}>{broken.map((b, i) => <li key={i}><Id value={b.target} className={css.bad} /> <Site site={b} /></li>)}</ul>
        </div>
      )}
      <div className={css.block}>
        <div className={css.blockTitle}>{w('linksIn')} <N value={links.in.length} className={css.n} /></div>
        {links.in.length ? <FoldList items={links.in} first={5} render={(e) => <EdgeRow edge={e} other={e.from} j={j} onFocus={onFocus} />} /> : <p className={css.muted}>{w('noLinksIn')}</p>}
      </div>
      {tasks.length > 0 && (
        <div className={css.block}>
          <div className={css.blockTitle}>{w('tasksHere')}</div>
          <ul className={css.list}>{tasks.map((t) => <li key={t.id}><button type="button" className={css.inline} onClick={() => onTask(t.id)}>{t.name[lang]}</button></li>)}</ul>
        </div>
      )}
      <div className={css.block}>
        <div className={css.blockTitle}>{w('shots')}</div>
        {s.shots && s.shots.length ? <img className={css.shot} src={`../${s.shots[0]}`} alt={s.route} /> : <p className={css.muted}>{w('noShot')}</p>}
      </div>
      {unseen.length > 0 && (
        <div className={css.block}>
          <div className={css.blockTitle}>{w('unseenHere')} <N value={unseen.length} className={css.n} /></div>
          <FoldList items={unseen} first={5} render={(i) => (
            <div className={css.item}><span className={css.itemName}><Id value={i.name} /></span><span className={css.itemSub}>{w(`group_${i.group}`)} · <Site site={i} /></span></div>
          )} />
        </div>
      )}
    </div>
  )
}

export function MenuPanel({ j, id, onFocus }: { j: Journeys; id: string; onFocus: (id: string) => void }) {
  const w = useJourneyWords()
  const m = j.menus.find((x) => x.id === id)!
  const links = linksOf(j, id)
  return (
    <div className={css.panel}>
      <div className={css.kicker}>{w('menu')}</div>
      <h2 className={css.panelTitle}><Id value={m.router} /></h2>
      <p className={css.note}>{w('menuSub', { n: m.links, s: m.scope.length })}</p>
      {m.files && m.files.length > 0 && <ul className={css.list}>{m.files.map((f) => <li key={f}><Id value={f} keep={3} /></li>)}</ul>}
      <div className={css.block}>
        <div className={css.blockTitle}>{w('linksOut')} <N value={links.out.length} className={css.n} /></div>
        <FoldList items={links.out} first={8} render={(e) => <EdgeRow edge={e} other={e.to} j={j} onFocus={onFocus} />} />
      </div>
    </div>
  )
}

/** A task's path, one step per row: the screen, and the file and line of the link that leads to it. */
export function TaskSteps({ j, task, onFocus }: { j: Journeys; task: Task; onFocus: (id: string) => void }) {
  const w = useJourneyWords()
  const steps = stepsOf(j, task)
  return (
    <ol className={css.steps} aria-label={w('steps')}>
      {steps.map((s) => {
        const screen = j.screens.find((x) => x.id === s.node)
        const site: LinkSite | undefined = s.via?.evidence[0]
        const text = s.index === 0 ? w('stepStart', { r: screen?.route ?? s.node }) : s.node.startsWith('menu:') ? w('stepMenu') : w('stepGo', { r: screen?.route ?? s.node })
        return (
          <li key={s.node} className={css.stepRow}>
            <span className={css.stepN} aria-hidden="true">{s.index + 1}</span>
            <button type="button" className={css.stepMain} onClick={() => onFocus(s.node)}>
              <span className={css.stepText}>{text}</span>
              {site && <span className={css.stepVia}>{w('stepVia')} <Site site={site} /></span>}
            </button>
          </li>
        )
      })}
      {task.kind === 'dialog' && task.file && (
        <li className={css.stepRow}>
          <span className={css.stepN} aria-hidden="true">{steps.length + 1}</span>
          <span className={css.stepMain}><span className={css.stepText}>{w('stepDialog', { f: task.file.split('/').pop() ?? task.file })}</span>
            <span className={css.stepVia}><Id value={task.file} keep={3} /></span></span>
        </li>
      )}
    </ol>
  )
}

export function TaskPanel({ j, task, onFocus }: { j: Journeys; task: Task; onFocus: (id: string) => void }) {
  const w = useJourneyWords()
  const { lang } = usePrefs()
  return (
    <div className={css.panel}>
      <div className={css.kicker}>{w('task')}</div>
      <h2 className={css.panelTitle}>{task.name[lang]}</h2>
      <p className={css.src}><Id value={task.src} /></p>
      {task.dead ? <p className={css.warn}>{w('taskDead')}</p> : !task.path.length ? <p className={css.warn}>{w('taskNoPath')}</p> : null}
      {task.path.length > 0 && <TaskSteps j={j} task={task} onFocus={onFocus} />}
      {task.dead && task.file && <p className={css.note}><Id value={task.file} keep={3} /></p>}
    </div>
  )
}

/** Nothing chosen: the counts (each a highlight), the tasks, and what is not measured yet. */
export function Overview({ j, onFlag, onTask, flag }: { j: Journeys; onFlag: (f: ScreenFlag | undefined) => void; onTask: (id: string) => void; flag?: ScreenFlag }) {
  const w = useJourneyWords()
  const { lang } = usePrefs()
  const count: Record<ScreenFlag, number> = {
    broken_link: j.counts.broken.value ?? 0, no_way_in: j.counts.no_way_in.value ?? 0, dead_end: j.counts.dead_ends.value ?? 0, duplicate: j.counts.duplicates.value ?? 0,
  }
  const live = j.tasks.filter((t) => !t.dead)
  const dead = j.tasks.filter((t) => t.dead)
  return (
    <div className={css.panel}>
      <p className={css.note}>{w('chooseScreen')}</p>
      <FlagFilter count={count} flag={flag} onFlag={onFlag} />
      <div className={css.block}>
        <div className={css.blockTitle}>{w('tasks')} <N value={live.length} className={css.n} /></div>
        <ul className={css.taskList}>
          {live.map((t) => (
            <li key={t.id}><RowButton onPress={() => onTask(t.id)} chevron={false} title={t.name[lang]}
              sub={t.path.length ? <Id value={j.screens.find((s) => s.id === t.screen)?.route ?? t.screen ?? ''} /> : w('taskNoPath')}
              end={t.path.length ? <N value={t.path.length + (t.kind === 'dialog' ? 1 : 0)} /> : undefined} /></li>
          ))}
        </ul>
      </div>
      {dead.length > 0 && (
        <div className={css.block}>
          <div className={css.blockTitle}>{w('deadTasks')} <N value={dead.length} className={css.n} /></div>
          <p className={css.muted}>{dead.map((t) => t.name[lang]).join(lang === 'ar' ? '، ' : ', ')}</p>
        </div>
      )}
      <Missing j={j} />
    </div>
  )
}

export function FlagFilter({ count, flag, onFlag }: { count: Record<ScreenFlag, number>; flag?: ScreenFlag; onFlag: (f: ScreenFlag | undefined) => void }) {
  const w = useJourneyWords()
  return (
    <div className={css.flags} role="group" aria-label={w('problemsFilter')}>
      {FLAGS.map((f) => (
        <button key={f} type="button" className={[css.flagBtn, css[`flag_${f}`]].join(' ')} aria-pressed={flag === f}
          onClick={() => onFlag(flag === f ? undefined : f)} disabled={!count[f]}>
          <N value={count[f]} className={css.flagN} /><span>{w(`flag_${f}`)}</span>
        </button>
      ))}
    </div>
  )
}

export function Missing({ j }: { j: { missing: Journeys['missing']; counts?: Partial<Record<string, { value: number | null }>> } }) {
  const w = useJourneyWords()
  const { lang } = usePrefs()
  const unowned = j.counts?.unowned_links?.value ?? 0
  if (!j.missing.length && !unowned) return null
  return (
    <div className={css.block}>
      <div className={css.blockTitle}>{w('gaps')}</div>
      <ul className={css.gaps}>
        {j.missing.map((g) => (
          <li key={g.id}>
            <span>{g.detail[lang]}</span>
            <span className={css.gapMeta}>{g.count.value !== null ? <><N value={g.count.value} /> · </> : null}{w('stepWord')} <Id value={g.step} /></span>
          </li>
        ))}
        {unowned > 0 && (
          <li><span>{w('unowned')}: <N value={unowned} /></span>
            {(j.counts?.unowned_dead?.value ?? 0) > 0 && <span className={css.gapMeta}>{w('unownedDead', { n: j.counts?.unowned_dead?.value ?? 0 })}</span>}</li>
        )}
      </ul>
    </div>
  )
}

/** The linear view: a task's steps, or every page by clicks from the start, each a button that focuses it. */
export function StepsView({ j, task, focus, onFocus }: { j: Journeys; task?: Task; focus?: string; onFocus: (id: string) => void }) {
  const w = useJourneyWords()
  if (task) return task.path.length ? <TaskSteps j={j} task={task} onFocus={onFocus} /> : <p className={css.warn}>{task.dead ? w('taskDead') : w('taskNoPath')}</p>
  return (
    <div className={css.depths} aria-label={w('byDepth')}>
      {byDepth(j).map(({ depth, screens }) => (
        <section key={String(depth)} className={css.depth} aria-label={depth === null ? w('noWayInCol') : depth === 0 ? w('start') : w('clicks', { n: depth })}>
          <h3 className={css.depthTitle}>{depth === null ? w('noWayInCol') : depth === 0 ? w('start') : depth === 1 ? w('oneClick') : w('clicks', { n: depth })}
            <N value={screens.length} className={css.n} /></h3>
          <FoldList items={screens} first={4} render={(s) => (
            <RowButton onPress={() => onFocus(s.id)} pressed={focus === s.id} chevron={false} title={<Id value={s.route} />}
              sub={<><Id value={s.title} />{s.flags.length ? ' · ' + s.flags.map((f) => w(`flag_${f}`)).join(' · ') : ''}</>} />
          )} />
        </section>
      ))}
    </div>
  )
}
