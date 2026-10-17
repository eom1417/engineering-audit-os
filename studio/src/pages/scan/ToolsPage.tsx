// "Preparing the tools": where EAOS opens first when it is asked to check a project (the assistant, `eaos start`, the
// Studio). Every external tool installs in the background, several at a time, in the order the check needs them, once
// for every project on the computer (eaos/toolchain.py); each shows here live: waiting, installing with its download's
// percentage, ready, or failed with why and Retry, with how far the install is and the time left. "Start the check"
// unlocks by itself once every tool the check needs on this project is ready, the rest going on behind it; a tool the
// check needs that failed keeps it locked unless the person picks "Start without it", which the report records. Once
// the check runs, the page gives way to the live map.
import { useNavigate } from '@tanstack/react-router'
import { useEffect, useRef } from 'react'
import { Button } from '../../components/Button'
import { Panel, Skeleton } from '../../components/Panel'
import { useActions, type Actions } from '../../data/actions/store'
import { useLive } from '../../data/context'
import { TOOLS, toolsOf, type AllProgress, type ToolRow, type Tools } from '../../data/scan'
import { useScan } from '../../data/ScanProvider'
import { usePrefs } from '../../i18n/prefs'
import { usePageChrome } from '../../shell/chrome'
import { layout } from '../../shell/Layout'
import { useCommand } from '../../command/command'
import { SnapshotPanel } from '../runs/RunsPage'
import { useScanWords } from './words'
import css from './scan.module.css'

const DOT: Record<ToolRow['state'], string> = { waiting: 'dot_waiting', downloading: 'dot_running', ready: 'dot_ok', failed: 'dot_failed' }

export function ToolsPage() {
  const w = useScanWords()
  const { mode } = useLive()
  const { all, skew } = useScan()
  const actions = useActions()
  usePageChrome(w('toolsTitle'), { to: '/scan', label: w('title') })
  useInstallAsked(all, actions)
  useMapOnceChecking(all)
  if (mode !== 'live') return <div className={layout.page}><Head lead={w('toolsSnapshotLead')} /><SnapshotPanel /></div>
  if (!all?.flows[TOOLS]) return <div className={layout.page}><Head /><Panel><Skeleton label={w('loading')} /></Panel></div>
  const tools = toolsOf(all.flows[TOOLS], all.tools_needed ?? [], Date.now() + skew)
  return (
    <div className={[layout.page, css.page].join(' ')} data-unlocked={tools.unlocked} data-tools-ready={tools.all.ready}>
      <Head />
      <Summary tools={tools} />
      <ToolList title={w('toolsHere')} rows={tools.rows.filter((row) => row.needed)} actions={actions} />
      <ToolList title={w('toolsLater')} rows={tools.rows.filter((row) => !row.needed)} actions={actions} />
    </div>
  )
}

function Head({ lead }: { lead?: string }) {
  const w = useScanWords()
  return (
    <div className={css.head}>
      <h1 className={css.title}>{w('toolsTitle')}</h1>
      <p className={css.lead}>{lead ?? w('toolsLead')}</p>
    </div>
  )
}

/** Opened when no install ran yet, or the last one stopped midway: the install is asked for once. */
function useInstallAsked(all: AllProgress | null, actions: Actions) {
  const asked = useRef(false)
  const state = all?.flows[TOOLS]?.state
  useEffect(() => {
    if (asked.current || !actions.client || !state || !['none', 'interrupted', 'stalled'].includes(state)) return
    asked.current = true
    void actions.client.start({ action: 'tools_check', inputs: { retry: true } }).catch(() => undefined)
  }, [actions.client, state])
}

/** The check started (here, from the terminal or by the assistant): the live map takes over. */
function useMapOnceChecking(all: AllProgress | null) {
  const navigate = useNavigate()
  const opened = useRef(Date.now())
  const check = all?.flows.check
  const started = check?.state === 'running' && Date.parse(check.started_at ?? '') > opened.current - 5000
  useEffect(() => {
    if (started) void navigate({ to: '/scan', search: { flow: 'check' } })
  }, [started, navigate])
}

function Summary({ tools }: { tools: Tools }) {
  const w = useScanWords()
  const { num } = usePrefs()
  const left = tools.left === null ? '' : 60 > tools.left ? w('leftLess') : w('toolsLeft', { m: num(Math.ceil(tools.left / 60)) })
  return (
    <Panel className={css.toolsTop}>
      <div className={css.runLine}>
        <span className={css.runFact} data-needed={`${tools.needed.ready}/${tools.needed.total}`}>{w('toolsNeeded', { n: num(tools.needed.ready), t: num(tools.needed.total) })}</span>
        <span className={css.runFact}>{w('toolsAll', { n: num(tools.all.ready), t: num(tools.all.total) })}</span>
        {left && <span className={css.runFact} data-left={Math.round(tools.left ?? 0)}>{left}</span>}
      </div>
      <Bar done={tools.all.ready} total={tools.all.total} />
      <Start tools={tools} />
    </Panel>
  )
}

function Bar({ done, total }: { done: number; total: number }) {
  return <span className={css.bar} aria-hidden="true"><span className={css.barFill} style={{ inlineSize: `${total ? (100 * done) / total : 0}%` }} /></span>
}

/** "Start the check", locked until the check's tools are ready; "Start without it" once only failures stand in the way.
 * Both open the check's preview (PreviewSheet): its paths and its mode are chosen there, wherever a check starts. */
function Start({ tools }: { tools: Tools | null }) {
  const w = useScanWords()
  const { num } = usePrefs()
  const command = useCommand()
  const unlocked = tools?.unlocked ?? true
  const failed = tools?.failed.length ?? 0
  const waiting = tools ? tools.needed.total - tools.needed.ready - failed : 0
  const start = (without: boolean) => command.open({ action: 'audit', inputs: without ? { fresh: true, without_tools: true } : { fresh: true } })
  return (
    <div className={css.toolsStart}>
      <Button variant="primary" large icon="play" isDisabled={!unlocked} onPress={() => start(false)} data-start-check="">
        {w('toolsStart')}
      </Button>
      {!unlocked && waiting > 0 && <span className={css.runFact} role="status">{w('toolsLocked', { n: num(waiting) })}</span>}
      {failed > 0 && waiting === 0 && (
        <>
          <span className={css.warn} role="alert">{w('toolsFailed')}</span>
          <Button variant="secondary" onPress={() => start(true)} data-start-without="">{w('toolsWithout')}</Button>
        </>
      )}
    </div>
  )
}

function ToolList({ title, rows, actions }: { title: string; rows: ToolRow[]; actions: Actions }) {
  const w = useScanWords()
  if (!rows.length) return null
  return (
    <Panel className={css.listPanel} as="section" label={title}>
      <h2 className={css.blockTitle}>{title}</h2>
      <ul className={[css.list, css.toolList].join(' ')}>{rows.map((row) => <Tool key={row.name} row={row} retry={() => void actions.client?.start({ action: 'tools_check', inputs: { retry: true } })} />)}</ul>
      <span className="sr" role="status">{w('toolsAll', { n: rows.filter((row) => row.state === 'ready').length, t: rows.length })}</span>
    </Panel>
  )
}

function Tool({ row, retry }: { row: ToolRow; retry: () => void }) {
  const w = useScanWords()
  const percent = row.state === 'downloading' && row.total ? Math.floor((100 * row.done) / row.total) : null
  return (
    <li className={css.toolRow} data-tool={row.name} data-tool-state={row.state}>
      <span className={[css.listDot, css[DOT[row.state]]].join(' ')} aria-hidden="true" />
      <span className={css.listMain}>
        <span className={css.listTitle}><bdi dir="ltr">{row.name}</bdi> <span className={css.muted}><bdi dir="ltr">{row.version.slice(0, 12)}</bdi></span></span>
        <span className={css.listSub}>{w(`tool_${row.state}`)}{percent !== null && <> · <bdi dir="ltr">{percent}%</bdi></>}</span>
        {percent !== null && <Bar done={row.done} total={row.total} />}
        {row.state === 'failed' && row.reason && <span className={css.reasonBad}>{w.reason(row.reasonCode, '')} <bdi dir="ltr">{row.reason}</bdi></span>}
      </span>
      {row.state === 'failed' && <Button variant="secondary" onPress={retry} data-retry={row.name}>{w('toolsRetry')}</Button>}
    </li>
  )
}

/** The Checks page before a check: the tools the check needs while they install, then one button to start it. The
 * install is asked for once, as on the tools page. */
export function StartCheck({ all }: { all: AllProgress }) {
  const w = useScanWords()
  const { skew } = useScan()
  const actions = useActions()
  useInstallAsked(all, actions)
  const flow = all.flows[TOOLS]
  const tools = flow ? toolsOf(flow, all.tools_needed ?? [], Date.now() + skew) : null
  if (tools && !tools.unlocked) {
    return (
      <>
        <Summary tools={tools} />
        <ToolList title={w('toolsHere')} rows={tools.rows.filter((row) => row.needed)} actions={actions} />
      </>
    )
  }
  return <Panel className={css.toolsTop}><p className={css.lead}>{w('startLead')}</p><Start tools={tools} /></Panel>
}

/** On the live map while tools are still installing: each tool faded until it is ready, then lit. */
export function ToolStrip({ all }: { all: AllProgress }) {
  const w = useScanWords()
  const flow = all.flows[TOOLS]
  if (!flow) return null
  const tools = toolsOf(flow, all.tools_needed ?? [], Date.now())
  if (tools.all.ready === tools.all.total) return null
  return (
    <Panel className={css.listPanel} as="section" label={w('toolsStrip')}>
      <h2 className={css.blockTitle}>{w('toolsStrip')} <span className={css.muted}>{tools.all.ready}/{tools.all.total}</span></h2>
      <ul className={css.strip}>{tools.rows.map((row) => (
        <li key={row.name} className={[css.chip, row.state !== 'ready' && css.faded, row.state === 'failed' && css.chipBad].filter(Boolean).join(' ')}
          data-strip-tool={row.name} data-tool-state={row.state}><bdi dir="ltr">{row.name}</bdi></li>
      ))}</ul>
    </Panel>
  )
}
