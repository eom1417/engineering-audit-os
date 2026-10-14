// The person's assistant beside the work (eaos/studio/actions/chat.py): a button in a corner opens a panel that stays
// small, moves to any corner and keeps the conversation across pages. The assistant reads and diagnoses; what it would
// do comes back as a card: an action opens the command centre's own preview and confirmation, a run's control waits
// for the person's press. It never changes anything by itself. Any page may open it with a question and its context
// (window event `eaos-chat`: the run page's "diagnose" sends the failed run). Live Studio only.
import { useCallback, useEffect, useRef, useState, type KeyboardEvent } from 'react'
import { useRouterState } from '@tanstack/react-router'
import { Button } from '../components/Button'
import { Icon } from '../components/Icon'
import { useCommandMaybe } from '../command/command'
import { useActions } from '../data/actions/store'
import type { ChatProposal } from '../data/actions/types'
import { usePrefs } from '../i18n/prefs'
import css from './chat.module.css'

const WORDS = {
  title: ['المساعد', 'Assistant'], open: ['افتح المساعد', 'Open the assistant'], close: ['صغّر', 'Minimise'],
  move: ['انقل للزاوية الثانية', 'Move to another corner'], fresh: ['محادثة جديدة', 'New conversation'],
  placeholder: ['اكتب سؤالك أو اطلب شي…', 'Ask, or ask for something…'], send: ['أرسل', 'Send'],
  deep: ['تشخيص عميق (أبطأ وأغلى)', 'Deep diagnosis (slower, costs more)'], thinking: ['يفكر…', 'Thinking…'],
  hello: ['أقرأ حالة مشروعك وسجلاته وأشرح وأشخّص. ما أغيّر شي بنفسي: أقترح، وأنت تأكد.',
    'I read your project, its state and its logs, explain and diagnose. I change nothing myself: I propose, you confirm.'],
  run: ['نفّذ', 'Run it'], sent: ['تم: افتح التشغيل لتتابعه', 'Done: follow it in Runs'],
  control: { retry: ['أعد التشغيل', 'Retry the run'], stop: ['أوقف التشغيل', 'Stop the run'], pause: ['أوقف مؤقتًا', 'Pause the run'], resume: ['كمّل التشغيل', 'Resume the run'] },
} as const
const CORNERS = ['bottomStart', 'bottomEnd', 'topEnd', 'topStart'] as const
type Corner = typeof CORNERS[number]
interface Line { who: 'person' | 'assistant' | 'error'; text: string; proposals?: ChatProposal[] }
export interface ChatRequest { message?: string; context?: Record<string, unknown>; deep?: boolean }

/** Open the assistant from anywhere, with a question and what it is about. */
export function askAssistant(request: ChatRequest) {
  window.dispatchEvent(new CustomEvent<ChatRequest>('eaos-chat', { detail: request }))
}

function Proposal({ item }: { item: ChatProposal }) {
  const { lang } = usePrefs()
  const at = lang === 'ar' ? 0 : 1
  const command = useCommandMaybe()
  const { client, refresh } = useActions()
  const [done, setDone] = useState(false)
  const title = item.kind === 'control' ? WORDS.control[item.action as keyof typeof WORDS.control]?.[at] ?? item.action : item.action
  const go = async () => {
    if (item.kind === 'action') { command?.open({ action: item.action, inputs: item.inputs }); return }
    if (!client || !item.run) return
    await client.control(item.run, item.action as 'retry' | 'stop' | 'pause' | 'resume')
    setDone(true)
    void refresh()
  }
  return (
    <div className={css.card}>
      <span className={css.cardTitle}><bdi>{title}</bdi></span>
      {item.why && <span className={css.hint}>{item.why}</span>}
      {done ? <span className={css.hint}>{WORDS.sent[at]}</span> : <div><Button variant="secondary" icon="play" onPress={() => void go()}>{WORDS.run[at]}</Button></div>}
    </div>
  )
}

export function ChatDock() {
  const { lang } = usePrefs()
  const at = lang === 'ar' ? 0 : 1
  const { client } = useActions()
  const location = useRouterState({ select: (s) => s.location })
  const [open, setOpen] = useState(false)
  const [corner, setCorner] = useState<Corner>(() => (CORNERS as readonly string[]).includes(localStorage.getItem('eaos.chat.corner') ?? '') ? localStorage.getItem('eaos.chat.corner') as Corner : 'bottomStart')
  const [lines, setLines] = useState<Line[]>([])
  const [session, setSession] = useState<string | null>(null)
  const [text, setText] = useState('')
  const [deep, setDeep] = useState(false)
  const [busy, setBusy] = useState(false)
  const list = useRef<HTMLDivElement>(null)

  const send = useCallback(async (message: string, extra?: ChatRequest) => {
    if (!client?.chat || !message.trim() || busy) return
    setLines((old) => [...old, { who: 'person', text: message }])
    setText('')
    setBusy(true)
    const run = location.pathname.match(/^\/runs\/([^/]+)/)?.[1]
    const context = { page: location.pathname, search: location.search, ...(run ? { run } : {}), ...(extra?.context ?? {}) }
    try {
      const turn = await client.chat(message, session, context, extra?.deep ?? deep)
      setSession(turn.session)
      setLines((old) => [...old, { who: 'assistant', text: turn.answer, proposals: turn.proposals }])
    } catch (problem) {
      setLines((old) => [...old, { who: 'error', text: problem instanceof Error ? problem.message : String(problem) }])
    } finally { setBusy(false) }
  }, [client, session, deep, busy, location])

  useEffect(() => {
    const opened = (event: Event) => {
      const request = (event as CustomEvent<ChatRequest>).detail ?? {}
      setOpen(true)
      if (request.deep) setDeep(true)
      if (request.message) void send(request.message, request)
    }
    window.addEventListener('eaos-chat', opened)
    return () => window.removeEventListener('eaos-chat', opened)
  }, [send])
  useEffect(() => { list.current?.scrollTo({ top: list.current.scrollHeight }) }, [lines, busy])

  if (!client?.chat) return null
  const move = () => {
    const next = CORNERS[(CORNERS.indexOf(corner) + 1) % CORNERS.length]
    setCorner(next)
    localStorage.setItem('eaos.chat.corner', next)
  }
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
        <button type="button" className={css.tool} aria-label={WORDS.move[at]} title={WORDS.move[at]} onClick={move}><Icon name="arrow" /></button>
        <button type="button" className={css.tool} aria-label={WORDS.close[at]} title={WORDS.close[at]} onClick={() => setOpen(false)}><Icon name="x" /></button>
      </header>
      <div className={css.list} ref={list} aria-live="polite">
        {!lines.length && <span className={css.hint}>{WORDS.hello[at]}</span>}
        {lines.map((line, index) => (
          <div key={index} style={{ display: 'contents' }}>
            <div className={css[line.who]}><bdi>{line.text}</bdi></div>
            {(line.proposals ?? []).map((item, n) => <Proposal key={n} item={item} />)}
          </div>
        ))}
        {busy && <span className={css.hint}>{WORDS.thinking[at]}</span>}
      </div>
      <footer className={css.foot}>
        <label className={css.deep}><input type="checkbox" checked={deep} onChange={(e) => setDeep(e.target.checked)} />{WORDS.deep[at]}</label>
        <div className={css.row}>
          <textarea className={css.input} value={text} rows={2} placeholder={WORDS.placeholder[at]} onChange={(e) => setText(e.target.value)} onKeyDown={key} />
          <Button variant="primary" icon="up" busy={busy} onPress={() => void send(text)}>{WORDS.send[at]}</Button>
        </div>
      </footer>
    </section>
  )
}
