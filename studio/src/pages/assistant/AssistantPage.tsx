// #/assistant: who does the work and what it used. The assistants on this computer (installed, signed in, model), the
// last check's use stage by stage, every run's use, and the measures to improve it (cost per kept card, the share of
// the conversation read again, the share of thinking). The numbers come from the live server (/api/assistants,
// /api/usage, eaos/usage.py); a snapshot has none. The cost is the API's price for the same tokens: a measure, not a bill.
import { useCallback, useEffect, useState, type ReactNode } from 'react'
import { Button } from '../../components/Button'
import { Chip } from '../../components/Chip'
import { Panel, Section, StateMessage } from '../../components/Panel'
import { labelOf } from '../../data/actions/derive'
import { useActions } from '../../data/actions/store'
import type { Assistant, Usage, UsageReport, UsageRun } from '../../data/actions/types'
import { useStudio } from '../../data/context'
import { usePrefs } from '../../i18n/prefs'
import { N } from '../../i18n/text'
import { usePageChrome } from '../../shell/chrome'
import { layout, PageTitle } from '../../shell/Layout'
import { SnapshotPanel } from '../runs/RunsPage'
import css from './assistant.module.css'

const WORDS = {
  title: ['المساعد', 'Assistant'],
  lead: ['مين يشتغل على مشروعك، وكم استهلك كل فحص وكل دفعة إصلاح.', 'Who works on your project, and what each check and each fix batch used.'],
  connection: ['الاتصال', 'Connection'],
  ready: ['جاهز', 'Ready'], notSignedIn: ['غير مسجّل الدخول', 'Not signed in'], notInstalled: ['غير مثبّت', 'Not installed'],
  model: ['النموذج', 'Model'], defaultModel: ['الافتراضي', 'its default'],
  measures: ['مؤشرات التحسين', 'What to improve'],
  perCard: ['تكلفة البطاقة المُصلحة', 'Cost per fixed card'], checkCost: ['تكلفة الفحص الأخير', 'Cost of the last check'],
  reread: ['إعادة قراءة السياق', 'Context read again'], thinkingShare: ['نسبة التفكير من الكتابة', 'Thinking in the output'],
  chatCost: ['المحادثات مع المساعد', 'Conversations with the assistant'],
  lastCheck: ['الفحص الأخير، مرحلة مرحلة', 'The last check, stage by stage'],
  runs: ['التشغيلات', 'Runs'],
  stage: ['المرحلة', 'Stage'], run: ['التشغيل', 'Run'], cost: ['التكلفة (API)', 'Cost (API)'], written: ['كتابة', 'Written'],
  read: ['قراءة السياق', 'Context read'], time: ['الوقت', 'Time'], turns: ['خطوات', 'Turns'], calls: ['طلبات', 'Calls'], cards: ['بطاقات', 'Cards'],
  total: ['المجموع', 'Total'], refresh: ['حدّث', 'Refresh'],
  note: ['اشتراكك ما يُحسب بالتوكن: التكلفة هنا سعر الـ API لنفس التوكنز، للمقارنة بين فحص وفحص ودفعة ودفعة.',
    'Your plan is not billed by the token: the cost is the API price of the same tokens, to compare one run with another.'],
  live: ['التشغيل ما زال شغال: التكلفة تظهر لما يخلص.', 'Still running: its cost shows once it ends.'],
  snapshot: ['الأرقام تظهر مع الاستوديو الشغّال على جهازك فقط.', 'The numbers show with the live Studio only.'],
  none: ['ما فيه استهلاك مسجّل بعد.', 'No use recorded yet.'],
} as const
type WordKey = keyof typeof WORDS

const STAGES: Record<string, [string, string]> = {
  card_triage: ['فرز البطاقات', 'Card triage'], visual_reviewer: ['مراجعة الشاشات', 'Screen review'],
  ideal_planner: ['تخطيط البنية', 'Target planning'], pipeline_gap_planner: ['فجوات المسارات', 'Pipeline gaps'],
  plan_orderer: ['ترتيب الخطة', 'Plan order'], semantic: ['القراءة الدلالية', 'Semantic reading'],
  translate: ['الترجمة', 'Translation'], setup: ['تشغيل التطبيق', 'Running the app'], other: ['أخرى', 'Other'],
}

function useWords() {
  const { lang } = usePrefs()
  return (key: WordKey) => WORDS[key][lang === 'ar' ? 0 : 1]
}

const tokens = (n: number) => (n >= 1e6 ? `${(n / 1e6).toFixed(1)}M` : n >= 1e3 ? `${Math.round(n / 1e3)}K` : String(n))
const dollars = (n: number | null | undefined) => (typeof n === 'number' ? `$${n < 10 ? n.toFixed(2) : n.toFixed(0)}` : '—')
const minutes = (ms: number) => (ms >= 60000 ? `${Math.round(ms / 60000)} min` : `${Math.round(ms / 1000)} s`)
const share = (part: number, whole: number) => (whole ? `${Math.round((100 * part) / whole)}%` : '—')
const read = (u: Usage) => u.input + u.cache_write + u.cache_read

function Tile({ label, children }: { label: string; children: ReactNode }) {
  return <Panel className={css.tile}><span className={css.tileLabel}>{label}</span><span className={css.tileValue}><bdi dir="ltr">{children}</bdi></span></Panel>
}

function Agent({ agent }: { agent: Assistant }) {
  const w = useWords()
  const state = !agent.installed ? ['critical', w('notInstalled')] : !agent.logged_in ? ['warning', w('notSignedIn')] : ['good', w('ready')]
  return (
    <div className={css.agent}>
      <span className={css.agentName}>{agent.name}</span>
      <Chip tone={state[0] as 'good' | 'warning' | 'critical'}>{state[1]}</Chip>
      <span className={css.muted}>{w('model')}: <bdi dir="ltr">{agent.model || w('defaultModel')}</bdi></span>
      {agent.version && <span className={css.muted}><bdi dir="ltr">{agent.version}</bdi></span>}
    </div>
  )
}

function Row({ name, use, cards }: { name: ReactNode; use: Usage | null; cards?: number }) {
  if (!use) return <tr><td>{name}</td><td colSpan={6}>—</td></tr>
  return (
    <tr>
      <td>{name}</td>
      <td><bdi dir="ltr">{dollars(use.cost_usd)}</bdi></td>
      <td><bdi dir="ltr">{tokens(use.output)}</bdi></td>
      <td><bdi dir="ltr">{tokens(use.cache_read)}</bdi></td>
      <td><bdi dir="ltr">{minutes(use.duration_ms)}</bdi></td>
      <td><N value={use.turns || use.calls} /></td>
      {cards !== undefined && <td>{cards ? <N value={cards} /> : '—'}</td>}
    </tr>
  )
}

function Head({ first, cards }: { first: string; cards?: boolean }) {
  const w = useWords()
  return <thead><tr><th>{first}</th><th>{w('cost')}</th><th>{w('written')}</th><th>{w('read')}</th><th>{w('time')}</th><th>{w('turns')}</th>{cards && <th>{w('cards')}</th>}</tr></thead>
}

function Measures({ report }: { report: UsageReport }) {
  const w = useWords()
  const fixed = report.runs.find((r) => r.verb === 'fix' && r.cards > 0 && typeof r.usage?.cost_usd === 'number')
  const all = [report.check?.total, report.chat, ...report.runs.map((r) => r.usage)].filter((u): u is Usage => !!u)
  const sum = (field: keyof Usage) => all.reduce((n, u) => n + (u[field] as number), 0)
  return (
    <div className={css.tiles}>
      <Tile label={w('perCard')}>{fixed ? dollars((fixed.usage!.cost_usd as number) / fixed.cards) : '—'}</Tile>
      <Tile label={w('checkCost')}>{dollars(report.check?.total?.cost_usd)}</Tile>
      <Tile label={w('reread')}>{share(sum('cache_read'), all.reduce((n, u) => n + read(u), 0))}</Tile>
      <Tile label={w('thinkingShare')}>{share(sum('thinking'), sum('output'))}</Tile>
      <Tile label={w('chatCost')}>{dollars(report.chat?.cost_usd)}</Tile>
    </div>
  )
}

/** The assistants on this computer and what they cost: the Assistant page's body, and a part of Settings. */
export function AssistantBody() {
  const w = useWords()
  const { lang } = usePrefs()
  const { client } = useActions()
  const [agents, setAgents] = useState<Assistant[] | null>(null)
  const [report, setReport] = useState<UsageReport | null>(null)
  const load = useCallback(() => {
    if (!client?.assistants || !client.usage) return
    void client.assistants().then(setAgents).catch(() => setAgents([]))
    void client.usage().then(setReport).catch(() => setReport({ check: null, runs: [] }))
  }, [client])
  useEffect(load, [load])
  if (!client?.usage) return <><Panel><StateMessage icon="assistant" title={w('snapshot')} /></Panel><SnapshotPanel /></>
  const stages = Object.entries(report?.check?.stages ?? {})
  const runs = (report?.runs ?? []).filter((r: UsageRun) => r.usage)
  return (
    <>
      <Section title={w('connection')}>
        <Panel><div className={css.agents}>{(agents ?? []).map((agent) => <Agent key={agent.id} agent={agent} />)}</div></Panel>
      </Section>
      {report && <Section title={w('measures')}><Measures report={report} /><p className={css.note}>{w('note')}</p></Section>}
      <Section title={w('lastCheck')}>
        <Panel>{stages.length ? (
          <div className={css.wide}><table className={css.table}><Head first={w('stage')} /><tbody>
            {stages.map(([name, use]) => <Row key={name} name={(STAGES[name] ?? [name, name])[lang === 'ar' ? 0 : 1]} use={use} />)}
            <Row name={<strong>{w('total')}</strong>} use={report?.check?.total ?? null} />
          </tbody></table></div>) : <StateMessage title={w('none')} />}
        </Panel>
      </Section>
      <Section title={w('runs')} count={runs.length}>
        <Panel>{runs.length ? (
          <div className={css.wide}><table className={css.table}><Head first={w('run')} cards /><tbody>
            {runs.map((r) => <Row key={r.id} name={<>{r.label ? labelOf(r.label, lang) : r.id}{r.state === 'running' && <> · {w('live')}</>}</>} use={r.usage} cards={r.cards} />)}
          </tbody></table></div>) : <StateMessage title={w('none')} />}
        </Panel>
      </Section>
      <div><Button variant="secondary" icon="retry" onPress={load}>{w('refresh')}</Button></div>
    </>
  )
}

export function AssistantPage() {
  const w = useWords()
  const data = useStudio()
  usePageChrome(w('title'), undefined, data?.manifest.project.name)
  return (
    <div className={layout.page}>
      <PageTitle title={w('title')} lead={w('lead')} />
      <AssistantBody />
    </div>
  )
}
