// System -> Visible and hidden (#/system/hidden): what the user sees (screens by area, with their dialogs and forms)
// against what runs unseen (jobs and triggers, routes that are not pages, server routes, writes, outside services,
// configuration and secrets, build steps, dead code), with the screens that set each in motion. Desktop: the diagram
// beside the inspector of an area or a group (every item with its file, line, fact and card). Phone: the summary, the
// diagram's preview opening a full-screen sheet, then the groups as lists. The URL holds ?focus=&only=1&hidden=0.
import { useNavigate, useSearch } from '@tanstack/react-router'
import { useRef, useState } from 'react'
import { Dialog, Heading, Modal, ModalOverlay } from 'react-aria-components'
import { Button, IconButton } from '../../../components/Button'
import { Go } from '../../../components/Go'
import { FoldList, Panel, StateMessage } from '../../../components/Panel'
import type { Hidden, HiddenGroupId, HiddenItem } from '../../../data/journeys'
import type { StudioData } from '../../../data/types'
import { usePrefs } from '../../../i18n/prefs'
import { Id, N } from '../../../i18n/text'
import { CanvasFrame, canvasClass } from '../../../map/parts'
import { useZoom } from '../../../map/useZoom'
import { usePageChrome } from '../../../shell/chrome'
import { MissingBanner, WithData } from '../../../shell/Layout'
import { usePhone } from '../../SystemMap'
import { Missing, Site } from '../journeys/parts'
import { HiddenSwitch, SystemViews } from '../SystemViews'
import { useJourneyWords } from '../words'
import { HiddenMap } from './HiddenMap'
import jcss from '../journeys/Journeys.module.css'
import css from './Hidden.module.css'

interface HiddenSearch { focus?: string; only?: string; hidden?: string }

function ItemRow({ item }: { item: HiddenItem }) {
  const w = useJourneyWords()
  return (
    <div className={jcss.item}>
      <span className={jcss.itemName}><Id value={item.name} />{item.no_screen && <span className={css.aloneTag}> · {w('noScreen')}</span>}</span>
      <span className={jcss.itemSub}>
        <span>{item.kind}</span>
        <Site site={item} />
        {item.detail && <Id value={item.detail} />}
        {item.card && <Go to="/problems" search={{ card: item.card }} className={jcss.link}>{w('card')}: <Id value={item.card} /></Go>}
      </span>
    </div>
  )
}

function GroupPanel({ h, id, only }: { h: Hidden; id: HiddenGroupId; only: boolean }) {
  const w = useJourneyWords()
  const g = h.groups.find((x) => x.id === id)!
  const byId = new Map(h.items.map((i) => [i.id, i]))
  const items = g.items.map((i) => byId.get(i)).filter((i): i is HiddenItem => Boolean(i) && (!only || i!.no_screen))
  const from = h.links.filter((l) => l.to === id)
  return (
    <div className={jcss.panel}>
      <div className={jcss.kicker}>{w('unseenSide')}</div>
      <h2 className={jcss.panelTitle}>{w(`group_${id}`)} <N value={g.count.value ?? 0} className={jcss.n} /></h2>
      <p className={jcss.src}><Id value={g.count.src} /></p>
      {g.no_screen > 0 && <p className={jcss.warn}>{w('noScreenWhy')} <N value={g.no_screen} /></p>}
      {from.length > 0 && (
        <div className={jcss.block}>
          <div className={jcss.blockTitle}>{w('setsInMotion')}</div>
          <p className={jcss.muted}>{from.map((l) => `${l.from.replace(/^area:/, '')} (${l.count})`).join(' · ')}</p>
        </div>
      )}
      <div className={jcss.block}>
        <div className={jcss.blockTitle}>{w('itemsOf', { g: w(`group_${id}`) })} <N value={items.length} className={jcss.n} /></div>
        {items.length ? <FoldList items={items} first={8} render={(i) => <ItemRow item={i} />} /> : <p className={jcss.muted}>{w('groupNone')}</p>}
        {(g.capped ?? 0) > 0 && <p className={jcss.muted}>{w('more', { n: g.capped ?? 0 })}</p>}
      </div>
    </div>
  )
}

function AreaPanel({ h, id }: { h: Hidden; id: string }) {
  const w = useJourneyWords()
  const a = h.seen.find((x) => x.id === id)!
  const byId = new Map(h.items.map((i) => [i.id, i]))
  const links = h.links.filter((l) => l.from === id)
  return (
    <div className={jcss.panel}>
      <div className={jcss.kicker}>{w('seenSide')}</div>
      <h2 className={jcss.panelTitle}>{a.name === '/' ? w('startArea') : a.name === 'public' ? w('public') : <Id value={a.name} />}</h2>
      <p className={jcss.note}>{w('areaSub', { s: a.screens.length, d: a.dialog_count })}</p>
      <ul className={jcss.list}>{a.screens.map((s) => <li key={s}><Go to="/system/journeys" search={{ focus: s }} className={jcss.inline}><Id value={s} /></Go></li>)}</ul>
      {a.dialogs.length > 0 && <p className={jcss.muted}>{a.dialogs.join(' · ')}</p>}
      <div className={jcss.block}>
        <div className={jcss.blockTitle}>{w('linksFromArea')}</div>
        {links.length ? links.map((l) => (
          <div key={l.to} className={jcss.block}>
            <div className={jcss.kicker}>{w(`group_${l.to}`)} <N value={l.count} className={jcss.n} /></div>
            <FoldList items={l.items.map((i) => byId.get(i)).filter((i): i is HiddenItem => Boolean(i))} first={4} render={(i) => <ItemRow item={i} />} />
          </div>
        )) : <p className={jcss.muted}>{w('groupNone')}</p>}
      </div>
    </div>
  )
}

function Legend({ inline }: { inline?: boolean }) {
  const w = useJourneyWords()
  return (
    <ul className={inline ? css.legendInline : css.legend} aria-label={w('legend')}>
      <li className={css.lg}><span className={css.swSeen} />{w('seenSide')}</li>
      <li className={css.lg}><span className={css.swUnseen} />{w('lgHidden')}</li>
      <li className={css.lg}><span className={css.swAlone} />{w('noScreen')}</li>
    </ul>
  )
}

function HiddenCanvas({ h, focus, only, showHidden, onFocus, title, head, className }:
  { h: Hidden; focus?: string; only: boolean; showHidden: boolean; onFocus: (id: string) => void; title?: React.ReactNode; head?: React.ReactNode; className?: string }) {
  const w = useJourneyWords()
  const svg = useRef<SVGSVGElement>(null)
  const zoom = useZoom(svg)
  return (
    <CanvasFrame title={title} head={head} zoom={zoom} className={className}>
      <div className={canvasClass.canvas}>
        <HiddenMap hidden={h} variant="full" focus={focus} onlyNoScreen={only} showHidden={showHidden} onFocus={onFocus}
          transform={zoom.t} dragging={zoom.dragging} svgRef={svg} className={canvasClass.svg}
          label={w('hiddenAria', { a: h.seen.length, g: h.groups.length })} />
        <Legend />
      </div>
    </CanvasFrame>
  )
}

function HiddenBody({ data, h }: { data: StudioData; h: Hidden }) {
  const { t } = usePrefs()
  const w = useJourneyWords()
  const phone = usePhone()
  const search = useSearch({ strict: false }) as HiddenSearch
  const navigate = useNavigate()
  const [explore, setExplore] = useState(false)
  const only = search.only === '1'
  const showHidden = search.hidden !== '0'
  const ids = new Set([...h.seen.map((a) => a.id), ...h.groups.map((g) => g.id as string)])
  const focus = search.focus && ids.has(search.focus) ? search.focus : undefined
  usePageChrome(w('hidden'), undefined, data.manifest.project.name)
  const go = (patch: Partial<HiddenSearch>) => navigate({
    to: '/system/hidden', search: (prev: HiddenSearch) => {
      const next = { ...prev, ...patch }
      return Object.fromEntries(Object.entries(next).filter(([, v]) => v !== undefined && v !== '')) as HiddenSearch
    },
  })
  const setFocus = (id: string) => go({ focus: id === focus ? undefined : id })
  const lead = w('hiddenLead', { s: h.counts.seen?.value ?? 0, u: h.counts.unseen?.value ?? 0, n: h.counts.no_screen?.value ?? 0 })
  const onlySwitch = (
    <button type="button" className={jcss.flagBtn} aria-pressed={only} onClick={() => go({ only: only ? undefined : '1' })}>
      <N value={h.counts.no_screen?.value ?? 0} className={jcss.flagN} /><span>{w('onlyNoScreen')}</span>
    </button>
  )
  const hiddenSwitch = <HiddenSwitch on={showHidden} onChange={(on) => go({ hidden: on ? undefined : '0' })} />
  const inspector = focus?.startsWith('area:') ? <AreaPanel h={h} id={focus} />
    : focus ? <GroupPanel h={h} id={focus as HiddenGroupId} only={only} />
    : (
      <div className={jcss.panel}>
        <p className={jcss.note}>{w('chooseSide')}</p>
        {h.groups.map((g) => (
          <button key={g.id} type="button" className={jcss.inline} onClick={() => setFocus(g.id)}>
            {w(`group_${g.id}`)} <N value={g.count.value ?? 0} />{g.no_screen ? <span className={css.aloneTag}> · {w('noScreen')} {g.no_screen}</span> : null}
          </button>
        ))}
        <Missing j={h} />
      </div>
    )

  if (phone) {
    const byId = new Map(h.items.map((i) => [i.id, i]))
    return (
      <div className={jcss.phone}>
        <MissingBanner data={data} />
        <SystemViews current="hidden" />
        <h1 className={jcss.largeTitle}>{w('hidden')}</h1>
        <p className={jcss.lead}>{lead}</p>
        <figure className={jcss.preview}>
          <button type="button" className={jcss.previewBtn} onClick={() => setExplore(true)} aria-label={w('exploreMap')}>
            <HiddenMap hidden={h} variant="preview" focus={focus} onlyNoScreen={only} showHidden={showHidden} className={css.previewSvg} />
          </button>
          <figcaption className={jcss.cap}><span>{w('hiddenAria', { a: h.seen.length, g: h.groups.length })}</span>
            <Button variant="ghost" onPress={() => setExplore(true)}>{w('exploreMap')}</Button></figcaption>
        </figure>
        {hiddenSwitch}
        <Legend inline />
        <div className={jcss.flags}>{onlySwitch}</div>
        {focus && <Panel pad>{inspector}</Panel>}
        {showHidden && h.groups.map((g) => {
          const items = g.items.map((i) => byId.get(i)).filter((i): i is HiddenItem => Boolean(i) && (!only || i!.no_screen))
          return (
            <Panel pad key={g.id}>
              <section className={css.groupCard} aria-label={w(`group_${g.id}`)}>
                <div className={css.groupHead}><span className={css.groupName}>{w(`group_${g.id}`)}</span><N value={only ? g.no_screen : g.count.value ?? 0} /></div>
                {g.no_screen > 0 && <span className={css.aloneTag}>{w('noScreen')}: {g.no_screen}</span>}
                {items.length ? <FoldList items={items} first={2} render={(i) => <ItemRow item={i} />} /> : null}
              </section>
            </Panel>
          )
        })}
        <Missing j={h} />
        <ModalOverlay isOpen={explore} onOpenChange={setExplore} isDismissable className={jcss.exploreOverlay}>
          <Modal className={jcss.exploreModal}>
            <Dialog className={jcss.exploreDialog} aria-label={w('hidden')}>
              {({ close }) => (
                <HiddenCanvas h={h} focus={focus} only={only} showHidden={showHidden} onFocus={setFocus} className={jcss.exploreCanvas}
                  head={<><IconButton icon="x" label={w('closeMap')} onPress={close} /><Heading slot="title" className={jcss.exploreTitle}>{w('hidden')}</Heading></>} />
              )}
            </Dialog>
          </Modal>
        </ModalOverlay>
      </div>
    )
  }

  const title = <h1 className={jcss.title} id="h-hidden">{w('hidden')}<span className={jcss.level}>{w('hiddenAria', { a: h.seen.length, g: h.groups.length })}</span></h1>
  return (
    <div className={jcss.page}>
      <section className={jcss.canvasCol} aria-labelledby="h-hidden">
        <MissingBanner data={data} />
        <div className={css.lens}><SystemViews current="hidden" /><p className={css.leadLine}>{lead}</p></div>
        <HiddenCanvas h={h} focus={focus} only={only} showHidden={showHidden} onFocus={setFocus} title={title}
          head={<>{hiddenSwitch}{onlySwitch}</>} className={jcss.canvasBox} />
      </section>
      <aside className={jcss.inspector} aria-label={t('inspector')}>{inspector}</aside>
    </div>
  )
}

export function HiddenPage() {
  const w = useJourneyWords()
  return (
    <WithData>{(data) => data.hidden
      ? <HiddenBody data={data} h={data.hidden} />
      : <div className={jcss.emptyPage}><SystemViews current="hidden" /><Panel><StateMessage title={w('noHidden')} sub={w('noJourneysSub')} /></Panel></div>}</WithData>
  )
}
