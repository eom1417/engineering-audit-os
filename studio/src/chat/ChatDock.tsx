// The person's assistant beside the work (eaos/studio/actions/chat.py): a button in a corner opens a panel that stays
// small, moves to any corner and keeps the conversation across pages. The answer shows as it is written, with what the
// assistant reads now. The assistant reads and diagnoses; what it would do comes back as a card: an action opens the
// command centre's own preview and confirmation, a run's control waits for the person's press. Direct control (the
// person turns it on, for an hour, kept by the server) lets the Studio run a few of its proposals at once, said in the
// conversation. The person picks the model: quick, balanced, or deep. Any page may open it with a question and its
// context (window event `eaos-chat`: the run page's "diagnose" sends the failed run). Live Studio only.
import { useCallback, useEffect, useRef, useState, type KeyboardEvent } from 'react'
import { useRouterState } from '@tanstack/react-router'
import { Button } from '../components/Button'
import { Icon } from '../components/Icon'
import { useCommandMaybe } from '../command/command'
import { actionOf } from '../data/actions/contract'
import { useActions } from '../data/actions/store'
import { useStudio } from '../data/context'
import type { ChatControl, ChatModel, ChatProposal, ChatTurn } from '../data/actions/types'
import { usePrefs } from '../i18n/prefs'
import { PlanForm } from './PlanForm'
import css from './chat.module.css'

const WORDS = {
  title: ['المساعد', 'Assistant'], open: ['افتح المساعد', 'Open the assistant'], close: ['صغّر', 'Minimise'],
  move: ['انقل للزاوية الثانية', 'Move to another corner'], fresh: ['محادثة جديدة', 'New conversation'],
  plan: ['ابنِ من خطة', 'Build from a plan'],
  extend: ['وسّع المشروع', 'Extend the project'],
  placeholder: ['اكتب سؤالك أو اطلب شي…', 'Ask, or ask for something…'], send: ['أرسل', 'Send'],
  thinking: ['يفكر…', 'Thinking…'], reading: ['يقرأ', 'Reading'],
  models: { quick: ['سريع', 'Quick'], balanced: ['متوازن', 'Balanced'], deep: ['عميق', 'Deep'] },
  model: ['النموذج', 'Model'],
  control: ['تحكم مباشر', 'Direct control'], controlOn: ['مفعّل لين', 'On until'],
  controlWhy: ['ينفذ بعض اقتراحاته بنفسه (فحص، تشغيل التطبيق، إعادة أو إيقاف تشغيل) لمدة ساعة. القبول والتراجع واختيار الفرع وتعديل الكود تبقى لك.',
    'Runs some of its proposals itself (a check, running the app, retrying or stopping a run) for an hour. Accepting, undoing, choosing a branch and editing code stay yours.'],
  ran: ['شغّلته', 'Set going'], couldNot: ['ما قدرت أشغّله', 'Could not start'],
  hello: ['أقرأ حالة مشروعك وسجلاته وأشرح وأشخّص. ما أغيّر شي بنفسي: أقترح، وأنت تأكد.',
    'I read your project, its state and its logs, explain and diagnose. I change nothing myself: I propose, you confirm.'],
  run: ['نفّذ', 'Run it'], sent: ['تم: افتح التشغيل لتتابعه', 'Done: follow it in Runs'],
  controls: { retry: ['أعد التشغيل', 'Retry the run'], stop: ['أوقف التشغيل', 'Stop the run'], pause: ['أوقف مؤقتًا', 'Pause the run'], resume: ['كمّل التشغيل', 'Resume the run'] },
} as const
// the end side first: the sidebar holds the start side on a computer
const CORNERS = ['bottomEnd', 'topEnd', 'topStart', 'bottomStart'] as const
type Corner = typeof CORNERS[number]
type Planning = '' | 'new' | 'extend'
type Live = { reading: string[]; partial: string }
interface Line { who: 'person' | 'assistant' | 'error'; text: string; proposals?: ChatProposal[]; done?: ChatTurn['done']; cost?: number | null }
export interface ChatRequest { message?: string; context?: Record<string, unknown>; model?: ChatModel }
const pause = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms))

/** Open the assistant from anywhere, with a question and what it is about. */
export function askAssistant(request: ChatRequest) {
  window.dispatchEvent(new CustomEvent<ChatRequest>('eaos-chat', { detail: request }))
}

const savedCorner = (): Corner => {
  const saved = localStorage.getItem('eaos.chat.corner') ?? ''
  return (CORNERS as readonly string[]).includes(saved) ? saved as Corner : 'bottomEnd'
}

/** Follows a turn until it is over, handing what the assistant reads and writes meanwhile to `onLive`: its result, or
 * the error it ended on. */
async function follow<R>(poll: () => Promise<Live & { done: boolean; error?: string | null; result?: R | null }>, onLive: (live: Live) => void): Promise<R> {
  for (;;) {
    await pause(900)
    const now = await poll()
    onLive({ reading: now.reading, partial: now.partial })
    if (!now.done) continue
    if (now.error || !now.result) throw new Error(now.error ?? 'no answer')
    return now.result
  }
}

function Proposal({ item }: { item: ChatProposal }) {
  const { lang } = usePrefs()
  const at = lang === 'ar' ? 0 : 1
  const command = useCommandMaybe()
  const { client, refresh } = useActions()
  const [done, setDone] = useState(false)
  const title = item.kind === 'control' ? WORDS.controls[item.action as keyof typeof WORDS.controls]?.[at] ?? item.action
    : actionOf(item.action)?.label[lang === 'ar' ? 'ar' : 'en'] ?? item.action
  const go = () => {
    if (item.kind === 'action') { command?.open({ action: item.action, inputs: item.inputs }); return }
    if (!client || !item.run) return
    void client.control(item.run, item.action as 'retry' | 'stop' | 'pause' | 'resume').then(() => { setDone(true); void refresh() })
  }
  return (
    <div className={css.card}>
      <span className={css.cardTitle}><bdi>{title}</bdi></span>
      {item.why && <span className={css.hint}>{item.why}</span>}
      {done ? <span className={css.hint}>{WORDS.sent[at]}</span> : <div><Button variant="secondary" icon="play" onPress={go}>{WORDS.run[at]}</Button></div>}
    </div>
  )
}

/** One turn of the conversation: its words, what the Studio ran of it, the proposals left to the person, its cost. */
function ChatLine({ line, at }: { line: Line; at: 0 | 1 }) {
  const done = line.done ?? []
  return (
    <div style={{ display: 'contents' }}>
      <div className={css[line.who]}><bdi>{line.text}</bdi></div>
      {done.map((d, n) => <span key={`d${n}`} className={css.hint}>{d.run ? WORDS.ran[at] : WORDS.couldNot[at]}: <bdi>{d.proposal.action}</bdi>{d.error ? ` (${d.error})` : ''}</span>)}
      {(line.proposals ?? []).filter((item) => !done.some((d) => d.proposal.action === item.action && d.run)).map((item, n) => <Proposal key={n} item={item} />)}
      {typeof line.cost === 'number' && <span className={css.cost}><bdi dir="ltr">${line.cost.toFixed(3)}</bdi></span>}
    </div>
  )
}

/** The answer as it is written, and what the assistant reads now. */
function Writing({ live, at }: { live: Live; at: 0 | 1 }) {
  return (
    <>
      {live.partial ? <div className={css.assistant}><bdi>{live.partial}</bdi></div> : null}
      <span className={css.hint}>{live.reading.length ? `${WORDS.reading[at]}: ${live.reading.join('، ')}` : WORDS.thinking[at]}</span>
    </>
  )
}

/** Opens (or closes) the form that builds a project from its plan, or extends this one. */
function PlanToggle({ way, planning, onPick, at }: { way: 'new' | 'extend'; planning: Planning; onPick: (way: Planning) => void; at: 0 | 1 }) {
  return <button type="button" className={css.tool} aria-pressed={planning === way} onClick={() => onPick(planning === way ? '' : way)}>{WORDS[way === 'new' ? 'plan' : 'extend'][at]}</button>
}

export function ChatDock() {
  const { lang, date } = usePrefs()
  const at = lang === 'ar' ? 0 : 1
  const { client } = useActions()
  const location = useRouterState({ select: (s) => s.location })
  const [open, setOpen] = useState(false)
  const [corner, setCorner] = useState<Corner>(savedCorner)
  const [lines, setLines] = useState<Line[]>([])
  const [session, setSession] = useState<string | null>(null)
  const [text, setText] = useState('')
  const [model, setModel] = useState<ChatModel>('quick')
  const [busy, setBusy] = useState(false)
  const [live, setLive] = useState<Live>({ reading: [], partial: '' })
  const [control, setControl] = useState<ChatControl | null>(null)
  const [planning, setPlanning] = useState<Planning>('')
  const checked = useStudio() !== null     // extending reads the check: offered once there is one
  const list = useRef<HTMLDivElement>(null)

  useEffect(() => { if (open && client?.chatControl) void client.chatControl().then(setControl).catch(() => undefined) }, [open, client])

  const send = useCallback(async (message: string, extra?: ChatRequest) => {
    if (!client?.chat || !client.chatProgress || !message.trim() || busy) return
    setLines((old) => [...old, { who: 'person', text: message }])
    setText('')
    setBusy(true)
    setLive({ reading: [], partial: '' })
    const run = location.pathname.match(/^\/runs\/([^/]+)/)?.[1]
    const context = { page: location.pathname, search: location.search, ...(run ? { run } : {}), ...(extra?.context ?? {}) }
    try {
      const { turn } = await client.chat(message, session, context, extra?.model ?? model)
      const result = await follow(() => client.chatProgress!(turn), setLive)
      setSession(result.session)
      setLines((old) => [...old, { who: 'assistant', text: result.answer, proposals: result.proposals, done: result.done, cost: result.usage?.cost_usd }])
    } catch (problem) {
      setLines((old) => [...old, { who: 'error', text: problem instanceof Error ? problem.message : String(problem) }])
    } finally { setBusy(false); setLive({ reading: [], partial: '' }) }
  }, [client, session, model, busy, location])

  useEffect(() => {
    const opened = (event: Event) => {
      const request = (event as CustomEvent<ChatRequest>).detail ?? {}
      setOpen(true)
      if (request.model) setModel(request.model)
      if (request.message) void send(request.message, request)
    }
    window.addEventListener('eaos-chat', opened)
    return () => window.removeEventListener('eaos-chat', opened)
  }, [send])
  useEffect(() => { list.current?.scrollTo(0, list.current.scrollHeight) }, [lines, live])

  if (!client?.chat) return null
  const move = () => {
    const next = CORNERS[(CORNERS.indexOf(corner) + 1) % CORNERS.length]
    setCorner(next)
    localStorage.setItem('eaos.chat.corner', next)
  }
  const toggle = () => { if (client.chatControl) void client.chatControl(!control?.on).then(setControl) }
  const key = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); void send(text) }
  }
  if (!open) {
    return <button type="button" className={[css.fab, css[corner]].join(' ')} aria-label={WORDS.open[at]} title={WORDS.open[at]} onClick={() => setOpen(true)}><Icon name="say" /></button>
  }
  return (
    <section className={[css.panel, css[corner]].join(' ')} aria-label={WORDS.title[at]}>
      <header className={css.head}>
        <Icon name="assistant" />
        <span className={css.title}>{WORDS.title[at]}</span>
        <button type="button" className={css.tool} onClick={() => { setLines([]); setSession(null) }}>{WORDS.fresh[at]}</button>
        {client.plan && (checked ? ['new', 'extend'] as const : ['new'] as const).map((way) => <PlanToggle key={way} way={way} planning={planning} onPick={setPlanning} at={at} />)}
        <button type="button" className={css.tool} aria-label={WORDS.move[at]} title={WORDS.move[at]} onClick={move}><Icon name="arrow" /></button>
        <button type="button" className={css.tool} aria-label={WORDS.close[at]} title={WORDS.close[at]} onClick={() => setOpen(false)}><Icon name="x" /></button>
      </header>
      <div className={css.settings}>
        <label className={css.setting}>{WORDS.model[at]}
          <select value={model} onChange={(e) => setModel(e.target.value as ChatModel)}>
            {(['quick', 'balanced', 'deep'] as const).map((m) => <option key={m} value={m}>{WORDS.models[m][at]}</option>)}
          </select>
        </label>
        <label className={css.setting} title={WORDS.controlWhy[at]}>
          <input type="checkbox" checked={!!control?.on} onChange={toggle} />{WORDS.control[at]}
          {control?.on && control.until && <span className={css.hint}>· {WORDS.controlOn[at]} {date(control.until, true)}</span>}
        </label>
      </div>
      {control?.on && <p className={css.warn}>{WORDS.controlWhy[at]}</p>}
      <div className={css.list} ref={list} aria-live="polite">
        {planning && <PlanForm key={planning} extend={planning === 'extend'} />}
        {!lines.length && !planning && <span className={css.hint}>{WORDS.hello[at]}</span>}
        {lines.map((line, index) => <ChatLine key={index} line={line} at={at} />)}
        {busy && <Writing live={live} at={at} />}
      </div>
      <footer className={css.foot}>
        <div className={css.row}>
          <textarea className={css.input} value={text} rows={2} placeholder={WORDS.placeholder[at]} onChange={(e) => setText(e.target.value)} onKeyDown={key} />
          <Button variant="primary" icon="up" busy={busy} onPress={() => void send(text)}>{WORDS.send[at]}</Button>
        </div>
      </footer>
    </section>
  )
}
