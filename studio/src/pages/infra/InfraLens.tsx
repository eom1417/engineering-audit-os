// The System map's infrastructure lens (#/system?lens=infra; STUDIO-COMPLETE: System → Infra lens): where the project
// runs and what it depends on outside its code, today, in the target, and the change. Desktop: the context diagram
// beside a 360px inspector with the chosen item's evidence or decision; or the steps view, lane by lane. Phone: the
// steps view, the chosen item, and the diagram as a full-screen sheet with pan and pinch.
// ?lens=infra&view=current|change|target&item=<id>&show=steps
import { useNavigate, useSearch } from '@tanstack/react-router'
import { useRef, useState } from 'react'
import { Button as AriaButton, Dialog, Heading, Modal, ModalOverlay } from 'react-aria-components'
import { Button, IconButton } from '../../components/Button'
import { Chip } from '../../components/Chip'
import { Segmented } from '../../components/Controls'
import { FoldList, Panel, Section, StateMessage } from '../../components/Panel'
import type { Infra, InfraNode, Lane, TargetItem } from '../../data/dataMap'
import type { StudioData } from '../../data/types'
import { Id, N, Txt } from '../../i18n/text'
import { useZoom } from '../../map/useZoom'
import mapCss from '../../map/parts.module.css'
import { usePageChrome } from '../../shell/chrome'
import { MissingBanner, WithData } from '../../shell/Layout'
import { usePhone } from '../SystemMap'
import dataCss from '../data/Data.module.css'
import { useDataWords, type DataWord } from '../data/words'
import { InfraMap } from './InfraMap'
import { allRows, find, modeOf, nodeName, type Mode, type Row } from './model'
import css from './Infra.module.css'

interface InfraSearch { lens?: string; view?: string; item?: string; show?: string }

function NodeDetail({ node }: { node: InfraNode }) {
  const w = useDataWords()
  const facts = Object.entries(node.detail).filter(([, v]) => typeof v === 'number' && v > 0) as [string, number][]
  return (
    <div className={dataCss.inspect}>
      <div className={dataCss.inspectHead}>
        <span className={dataCss.kindWord}>{w(`lane_${node.lane}`)} · {w(`kind_${node.kind}` as DataWord)}</span>
        <h2 className={dataCss.storeName}>{node.kind === 'host' ? <Id value={node.name} /> : <Txt>{nodeName(node, w)}</Txt>}</h2>
        <div className={dataCss.chips}>
          {facts.map(([k, v]) => <Chip key={k}>{w(`detail_${k}` as DataWord, { n: v })}</Chip>)}
          {node.kind === 'host' && <Chip tone={node.detail.timeout ? 'good' : 'warning'}>{w(node.detail.timeout ? 'hasTimeout' : 'noTimeout')}</Chip>}
          {node.kind === 'host' && node.detail.retry === true && <Chip tone="good">{w('hasRetry')}</Chip>}
          {node.kind === 'sensitive_file' && <Chip tone="warning">{w('sensitiveFile')}</Chip>}
        </div>
      </div>
      {node.items.length > 0 && (
        <Section title={w('holds')} count={node.items.length}>
          <FoldList items={node.items} first={8} render={(item) => <span className={dataCss.module}><Id value={item} /></span>} />
        </Section>
      )}
      <Section title={w('evidence')} count={node.evidence}>
        <FoldList items={node.sites} first={5} render={(site) => (
          <span className={dataCss.module}><Id value={site.path} keep={3} />{site.line ? <span className={dataCss.lineNo}> {w('line', { n: site.line })}</span> : null}</span>
        )} />
      </Section>
    </div>
  )
}

function ItemDetail({ lane, item }: { lane: Lane; item: TargetItem }) {
  const w = useDataWords()
  return (
    <div className={dataCss.inspect}>
      <div className={dataCss.inspectHead}>
        <span className={dataCss.kindWord}>{w(`lane_${lane}`)} · {w('target')}</span>
        <h2 className={dataCss.storeName}>{w(`area_${item.area}` as DataWord)}</h2>
        <div className={dataCss.chips}><Chip tone={item.op === 'keep' ? 'good' : 'accent'}>{w(item.op === 'keep' ? 'opKeep' : 'opIntroduce')}</Chip>
          {item.tool && <Chip>{w('tool')}: {item.tool}</Chip>}</div>
      </div>
      <Section title={w('decision')}><p className={dataCss.declared}><Txt block>{item.decision}</Txt></p></Section>
      <Section title={w('why')}><p className={dataCss.declared}><Txt block>{item.evidence}</Txt></p></Section>
    </div>
  )
}

function RowLine({ row }: { row: Row }) {
  const w = useDataWords()
  if (row.kind === 'item') return <><span className={row.item.op === 'keep' ? css.keepMark : css.addMark} aria-hidden="true">{row.item.op === 'keep' ? '●' : '+'}</span>
    {w(`area_${row.item.area}` as DataWord)} <span className={dataCss.kindWord}>{w(row.item.op === 'keep' ? 'opKeep' : 'opIntroduce')}</span></>
  if (row.kind === 'node') return <>{row.node.kind === 'host' ? <Id value={row.node.name} /> : <Txt>{nodeName(row.node, w)}</Txt>}
    {row.node.evidence > 1 && <span className={dataCss.kindWord}> · {w('sites', { n: row.node.evidence })}</span>}</>
  return <>{w('moreN', { n: row.more })}</>
}

/** Lane by lane, every row of the diagram: the lens's linear twin for the phone and screen readers. */
function InfraSteps({ infra, mode, focus, onFocus }: { infra: Infra; mode: Mode; focus?: string; onFocus: (id: string) => void }) {
  const w = useDataWords()
  return (
    <ol className={css.steps}>
      {infra.lanes.map((lane) => {
        const rows = allRows(infra, lane.id, mode)
        const target = infra.target?.lanes.find((l) => l.id === lane.id)
        return (
          <li key={lane.id}>
            <Panel>
              <h2 className={css.stepLane}>{w(`lane_${lane.id}`)} <span className={dataCss.kindWord}>{w(`rel_${lane.relation}` as DataWord)}</span>
                <N value={lane.count.value ?? 0} className={css.stepN} /></h2>
              {rows.length === 0
                ? <p className={css.stepEmpty}>{mode === 'target' ? w('silent') : w(`empty_${lane.reason}` as DataWord)}</p>
                : <FoldList items={rows} first={6} render={(row) => {
                    const id = row.kind === 'node' ? row.node.id : row.kind === 'item' ? `target:${lane.id}:${row.item.area}` : ''
                    return (
                      <AriaButton className={dataCss.stepRow} onPress={() => id && onFocus(id)} aria-pressed={focus === id}>
                        <span className={dataCss.stepMain}><span className={dataCss.stepTitle}><RowLine row={row} /></span></span>
                      </AriaButton>
                    )
                  }} />}
              {mode !== 'current' && (!target || target.state === 'not_measured') && rows.length > 0 && <p className={css.stepEmpty}>{w('silent')}</p>}
            </Panel>
          </li>
        )
      })}
    </ol>
  )
}

/** Every lane in a table: what was found today, and what the target decides for it (or that it is silent). */
function LaneTable({ infra }: { infra: Infra }) {
  const w = useDataWords()
  return (
    <table className={css.lanes}>
      <thead><tr><th scope="col">{w('lensInfra')}</th><th scope="col">{w('today')}</th><th scope="col">{w('target')}</th></tr></thead>
      <tbody>
        {infra.lanes.map((lane) => {
          const items = infra.target?.lanes.find((l) => l.id === lane.id)?.items ?? []
          const keep = items.filter((i) => i.op === 'keep').length
          const add = items.length - keep
          return (
            <tr key={lane.id}>
              <th scope="row">{w(`lane_${lane.id}`)}</th>
              <td><N value={lane.count.value ?? 0} /></td>
              <td>{!infra.target ? '—' : items.length ? [keep && w('keepN', { n: keep }), add && w('introduceN', { n: add })].filter(Boolean).join(' · ')
                : <span className={css.silentCell}>{w('silent')}</span>}</td>
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}

function InfraBody({ data, infra }: { data: StudioData; infra: Infra }) {
  const w = useDataWords()
  const phone = usePhone()
  const navigate = useNavigate()
  const search = useSearch({ strict: false }) as InfraSearch
  const mode = modeOf(search.view, infra)
  const found = search.item ? find(infra, search.item) : null
  const focus = found ? search.item : undefined
  const steps = search.show === 'steps'
  const [explore, setExplore] = useState(false)
  const svg = useRef<SVGSVGElement>(null)
  const zoom = useZoom(svg, explore)
  usePageChrome(w('infraTitle'), { to: '/system', label: w('lensMap') }, data.manifest.project.name)

  const go = (patch: Partial<InfraSearch>) => navigate({
    to: '/system', search: (prev: InfraSearch) => Object.fromEntries(Object.entries({ ...prev, lens: 'infra', ...patch })
      .filter(([, v]) => v !== undefined && v !== '')) as InfraSearch,
  })
  const pick = (id: string) => { if (!id.startsWith('more:')) go({ item: id === focus ? undefined : id }) }
  const setMode = (m: Mode) => go({ view: m === 'current' ? undefined : m, item: undefined })
  const counts = w('infraCounts', { n: infra.counts.nodes?.value ?? 0, l: infra.counts.lanes_found?.value ?? 0 })
  const plan = infra.target ? [w('keepN', { n: infra.counts.keep?.value ?? 0 }), w('introduceN', { n: infra.counts.introduce?.value ?? 0 }),
    w('silentN', { n: infra.counts.target_silent?.value ?? 0 })].join(' · ') : w('noTarget')
  const detail = found?.node ? <NodeDetail node={found.node} /> : found?.item ? <ItemDetail lane={found.lane} item={found.item} /> : null
  const modes = infra.target && (
    <Segmented label={w('view')} value={mode} onChange={setMode} comfortable={phone}
      options={[{ id: 'current', label: w('today') }, { id: 'change', label: w('change') }, { id: 'target', label: w('target') }]} />
  )

  if (phone) {
    return (
      <div className={dataCss.phone}>
        <MissingBanner data={data} />
        <h1 className={dataCss.largeTitle}>{w('infraTitle')}</h1>
        <p className={dataCss.lead}>{counts}<br />{plan}</p>
        {modes}
        <Button variant="secondary" onPress={() => setExplore(true)}>{w('exploreMap')}</Button>
        {detail && <Panel pad>{detail}</Panel>}
        <InfraSteps infra={infra} mode={mode} focus={focus} onFocus={pick} />
        <ModalOverlay isOpen={explore} onOpenChange={setExplore} isDismissable className={dataCss.exploreOverlay}>
          <Modal className={dataCss.exploreModal}>
            <Dialog className={dataCss.exploreDialog} aria-label={w('infraTitle')}>
              {({ close }) => (
                <>
                  <div className={dataCss.exploreHead}>
                    <IconButton icon="x" label={w('closeMap')} onPress={close} />
                    <Heading slot="title" className={dataCss.exploreTitle}>{w('infraTitle')}</Heading>
                    <span className={dataCss.spacer} />
                    <div className={mapCss.zoom} role="group" aria-label={w('zoomFit')}>
                      <AriaButton className={mapCss.zoomBtn} onPress={() => zoom.zoomBy(1.4)} aria-label={w('zoomIn')}>+</AriaButton>
                      <AriaButton className={mapCss.zoomBtn} onPress={() => zoom.zoomBy(1 / 1.4)} aria-label={w('zoomOut')}>−</AriaButton>
                      <AriaButton className={mapCss.zoomBtn} onPress={zoom.fit} aria-label={w('zoomFit')}>⤢</AriaButton>
                    </div>
                  </div>
                  <div className={dataCss.exploreCanvas}>
                    <InfraMap infra={infra} mode={mode} focus={focus} onFocus={pick} svgRef={svg}
                      transform={`translate(${zoom.t.x},${zoom.t.y}) scale(${zoom.t.k})`} className={dataCss.exploreSvg} />
                  </div>
                  {found && (
                    <div className={dataCss.exploreBar} role="status">
                      <span className={dataCss.exploreName}>{found.node ? nodeName(found.node, w) : w(`area_${found.item!.area}` as DataWord)}</span>
                      <Button variant="primary" onPress={close}>{w('seeChain')}</Button>
                    </div>
                  )}
                </>
              )}
            </Dialog>
          </Modal>
        </ModalOverlay>
      </div>
    )
  }

  return (
    <div className={dataCss.sys}>
      <section className={dataCss.canvasCol} aria-labelledby="h-infra">
        <MissingBanner data={data} />
        <div className={dataCss.toolbar}>
          <h1 className={dataCss.title} id="h-infra">{w('infraTitle')}<span className={dataCss.level}>{counts}</span></h1>
          <div className={dataCss.toolRow}>
            {modes}
            <Segmented label={w('showAs')} value={steps ? 'steps' : 'map'} onChange={(v) => go({ show: v === 'steps' ? 'steps' : undefined })}
              options={[{ id: 'map', label: w('asMap') }, { id: 'steps', label: w('asSteps') }]} />
            <span className={dataCss.spacer} />
            <span className={dataCss.level}>{plan}</span>
          </div>
        </div>
        <div className={dataCss.scroll} data-scroll-y="">
          {steps
            ? <div className={dataCss.stepsPage}><InfraSteps infra={infra} mode={mode} focus={focus} onFocus={pick} /></div>
            : <InfraMap infra={infra} mode={mode} focus={focus} onFocus={pick} className={css.fitSvg} />}
        </div>
      </section>
      <aside className={dataCss.inspector} aria-label={w('evidence')} tabIndex={0}>
        {detail ?? <div className={dataCss.overview}><p className={dataCss.hint}>{w('infraLead')} {w('chooseNode')}</p><LaneTable infra={infra} /></div>}
      </aside>
    </div>
  )
}

export function InfraLensPage() {
  const w = useDataWords()
  return (
    <WithData>{(data) => data.infra
      ? <InfraBody data={data} infra={data.infra} />
      : <div className={dataCss.page}><Panel><StateMessage title={w('noInfra')} sub={w('noDataSub')} /></Panel></div>}
    </WithData>
  )
}
