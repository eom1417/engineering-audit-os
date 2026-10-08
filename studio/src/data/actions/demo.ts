// The demo command centre: the same client as the live one, over runs replayed from a recording (recording.ts) on the
// cards of the report that is open. It keeps the contract's rules (one run at a time, the queue in the person's order,
// a question pauses the run until it is answered, confirm tokens for what changes code or cannot be undone), so the
// pages are built, tested and gated without a server. Nothing it does reaches the project.
import { actionOf, STATE_WORDS, verbOf } from './contract'
import { DEMO_BATCH, recordingFor, type CardLike, type Step } from './recording'
import { ActionError, ACTIVE, TERMINAL, type ActionsClient, type Bi, type Control, type Preview, type PreviewBody, type Question,
  type Run, type RunEvent, type RunState, type Selection, type StartBody, type StreamStatus, type VerbId } from './types'

/** A card of the open report, as the demo resolves selections over it. */
export interface DemoCard extends CardLike { state?: string; category?: string; milestone?: string | null; severity?: string | null }

interface Replay {
  run: Run
  events: RunEvent[]
  before: Step[]
  after: Step[]
  question: Question | null
  cursor: number
  asked: boolean
  timer?: ReturnType<typeof setTimeout>
}

const CONFIRM = 'demo-confirm'
const bi = (en: string, ar: string): Bi => ({ en, ar })
const iso = (ms: number) => new Date(ms).toISOString()

export const DEMO_ASSISTANTS = [
  { id: 'claude', name: 'Claude Code', installed: true, logged_in: true, version: '2.1 (example)' },
  { id: 'codex', name: 'Codex', installed: false, logged_in: false, version: null },
]

/** The cards a selection names, and the ones left out because they are not open (contract `selection.rules`). */
export function resolveSelection(selection: Selection | undefined, cards: DemoCard[]): { chosen: DemoCard[]; left: { id: string; why: string }[] } {
  if (!selection) return { chosen: [], left: [] }
  const byId = new Map(cards.map((card) => [card.id, card]))
  let named: DemoCard[]
  if (selection.kind === 'card' || selection.kind === 'cards') named = (selection.cards ?? []).map((id) => byId.get(id) ?? { id })
  else if (selection.kind === 'step') named = cards.filter((card) => card.milestone === selection.step)
  else if (selection.group?.by === 'area') named = cards.filter((card) => card.category === selection.group!.value)
  else if (selection.group?.by === 'severity') named = cards.filter((card) => card.severity === selection.group!.value)
  else named = []
  const chosen = named.filter((card) => !card.state || card.state === 'open')
  const left = named.filter((card) => card.state && card.state !== 'open').map((card) => ({ id: card.id, why: `already ${card.state?.replace('_', ' ')}` }))
  return { chosen, left }
}

export function demoClient(cardsOf: () => DemoCard[], speed = 1): ActionsClient & { seed(): void } {
  const replays = new Map<string, Replay>()
  let queue: string[] = []
  let counter = 0
  let wave = 3
  const listeners = new Set<() => void>()
  const followers = new Map<string, Set<(event: RunEvent) => void>>()
  const changed = () => listeners.forEach((listener) => listener())
  // A page opened straight on a run (#/runs/demo-5) asks before the report is there to seed from: it waits for the seed
  let seeded = false
  let markSeeded = () => {}
  const ready = new Promise<void>((resolve) => { markSeeded = resolve })

  function emit(replay: Replay, kind: RunEvent['kind'], text: Bi, data: Record<string, unknown>, detail?: string | null, at = Date.now()) {
    const seq = replay.events.length + 1
    const event: RunEvent = { seq, id: `${replay.run.id}-${seq}`, run: replay.run.id, at: iso(at), kind, text, data, detail: detail ?? null }
    replay.events.push(event)
    followers.get(replay.run.id)?.forEach((follower) => follower(event))
    return event
  }

  function setState(replay: Replay, to: RunState, why: string, at = Date.now()) {
    const from = replay.run.state
    if (from === to) return
    replay.run = { ...replay.run, state: to }
    if (to === 'running' && !replay.run.started) replay.run.started = iso(at)
    if (TERMINAL.includes(to)) replay.run.ended = iso(at)
    emit(replay, 'state', STATE_WORDS[to], { from, to, why }, null, at)
  }

  function slotTaken() {
    return [...replays.values()].some((replay) => ACTIVE.includes(replay.run.state))
  }

  /** The next queued run takes the slot when it is free. */
  function advance() {
    if (slotTaken()) return
    const next = queue.map((id) => replays.get(id)).find((replay) => replay?.run.state === 'queued')
    if (!next) return
    queue = queue.filter((id) => id !== next.run.id)
    setState(next, 'running', 'its turn came')
    schedule(next)
  }

  function step(replay: Replay, recorded: Step, at?: number) {
    emit(replay, recorded.kind, recorded.text, recorded.data, recorded.detail, at)
    if (recorded.kind === 'result') replay.run = { ...replay.run, result: recorded.data as unknown as Run['result'] }
  }

  function schedule(replay: Replay) {
    clearTimeout(replay.timer)
    if (replay.run.state !== 'running') return
    const script = [...replay.before, ...replay.after]
    if (replay.cursor === replay.before.length && replay.question && !replay.asked) {
      replay.asked = true
      replay.timer = setTimeout(() => ask(replay), 500 / speed)
      return
    }
    const next = script[replay.cursor]
    if (!next) {
      setState(replay, 'done', 'the result came')
      changed()
      advance()
      return
    }
    replay.timer = setTimeout(() => {
      replay.cursor += 1
      step(replay, next)
      changed()
      schedule(replay)
    }, next.after / speed)
  }

  function ask(replay: Replay, at?: number) {
    const question = replay.question!
    emit(replay, 'question', question.text, question as unknown as Record<string, unknown>, null, at)
    replay.run = { ...replay.run, question }
    setState(replay, 'waiting_for_person', 'a question', at)
    changed()
  }

  function create(verb: VerbId | null, action: string, cards: DemoCard[], left: { id: string; why: string }[], selection: Selection | null, created = Date.now()): Replay {
    counter += 1
    const id = `demo-${counter}`
    const label: Bi = verb
      ? (() => { const word = verbOf(verb).label; const ids = cards.slice(0, 3).map((c) => c.id); const more = cards.length > 3 ? ' …' : ''; return bi(`${word.en}: ${ids.join(', ')}${more}`, `${word.ar}: ${ids.join('، ')}${more}`) })()
      : actionOf(action)?.label ?? bi(action, action)
    const branch = `eaos/wave-${wave++}`
    const recorded = recordingFor(verb, cards, id, branch, label)
    const run: Run = {
      id, action, verb, label, selection, cards: cards.map((c) => c.id),
      cards_detail: cards.map((c) => ({ id: c.id, title: c.title ?? null, paths: c.paths ?? [] })), left_out: left,
      assistant: verb || actionOf(action)?.needs_assistant ? 'claude' : null, mode: verb || actionOf(action)?.needs_assistant ? 'assistant' : 'direct',
      state: 'queued', attempt: 1, created: iso(created), queued_at: iso(created), started: null, ended: null, result: null, question: null, outcome: null,
    }
    const replay: Replay = { run, events: [], before: recorded.before, after: recorded.after, question: recorded.question, cursor: 0, asked: false }
    replays.set(id, replay)
    emit(replay, 'action', bi(`You asked: ${label.en}`, `طلبت: ${label.ar}`), { action, by: 'person', arguments: { cards: run.cards } }, null, created)
    return replay
  }

  /** Plays a replay to its end at once (the history the demo opens with), with times spaced from `start`. */
  function playOut(replay: Replay, start: number, finish: RunState = 'done') {
    let at = start
    setState(replay, 'running', 'its turn came', at)
    const script = [...replay.before, ...replay.after]
    for (const [index, recorded] of script.entries()) {
      if (index === replay.before.length && replay.question) {
        at += 4000
        ask(replay, at)
        const answer = replay.question.options[0]
        emit(replay, 'answer', bi(`You answered: ${answer.label.en}`, `جاوبت: ${answer.label.ar}`), { question: replay.question.id, option: answer.id, text: null, by: 'person' }, null, at + 20000)
        replay.run = { ...replay.run, question: null }
        setState(replay, 'running', 'the answer', at + 20000)
        at += 20000
      }
      if (finish === 'failed' && recorded.kind === 'check' && recorded.data.passed === false) {
        at += 9000
        replay.cursor = index
        emit(replay, 'error', bi('The assistant stopped answering: the run cannot go on', 'المساعد توقف عن الرد: التشغيل ما يقدر يكمل'),
          { reason: 'the assistant process ended without a result', recoverable: true, what_now: bi('Press Retry: the run starts again from the same selection. Nothing reached your branch.', 'اضغط «أعد المحاولة»: يبدأ التشغيل من جديد بنفس الاختيار. ما وصل شي لفرعك.') },
          'claude exited with code 1 after 9 m 12 s', at)
        setState(replay, 'failed', 'the process ended', at)
        return
      }
      if (finish === 'stopped' && index === Math.floor(script.length / 2)) {
        at += 3000
        emit(replay, 'action', bi('You pressed stop', 'ضغطت إيقاف'), { action: 'stop', by: 'person', arguments: {} }, null, at)
        setState(replay, 'stopped', 'stop', at)
        return
      }
      at += recorded.after * 30
      replay.cursor = index + 1
      step(replay, recorded, at)
    }
    setState(replay, 'done', 'the result came', at + 1000)
  }

  function preview(id: string, body: PreviewBody): Preview {
    const verb = (body.verb ?? (['fix', 'verify', 'explain', 'plan'].includes(id) ? id : null)) as VerbId | null
    if (verb) {
      const { chosen, left } = resolveSelection(body.selection, cardsOf())
      if (!chosen.length) throw new ActionError(400, left.length ? 'every selected card is already handled' : 'nothing is selected')
      const files = [...new Set(chosen.flatMap((card) => card.paths ?? []))].sort()
      const n = chosen.length
      const serious = chosen.some((card) => card.severity === 'critical' || card.severity === 'high')
      const level = verb !== 'fix' ? 'low' : n > 10 || (serious && n > 3) ? 'high' : n > 3 || serious ? 'medium' : 'low'
      const batches = verb === 'fix' ? Array.from({ length: Math.ceil(n / DEMO_BATCH) }, (_, i) => ({ number: i + 1, cards: chosen.slice(i * DEMO_BATCH, (i + 1) * DEMO_BATCH).map((c) => c.id) })) : []
      return {
        action: verb, verb, selection: body.selection ?? null,
        cards: chosen.map((card) => ({ id: card.id, title: card.title ?? null, severity: card.severity ?? null, paths: card.paths ?? [] })),
        left_out: left, files, batches,
        estimate: verb === 'fix'
          ? { minutes_low: 2 + 2 * n, minutes_high: 5 + 4 * n, basis: bi('a rough rule: 2 to 4 minutes a card, plus starting your app', 'تقدير تقريبي: من دقيقتين إلى أربع لكل بطاقة، وتشغيل تطبيقك') }
          : { minutes_low: 1, minutes_high: 2 + n, basis: bi('reading only: about a minute a card', 'قراءة فقط: دقيقة تقريبًا لكل بطاقة') },
        risk: verb === 'fix'
          ? { level, why: level === 'low' ? bi('A few small changes, each checked before it is kept', 'تغييرات قليلة وصغيرة، كل واحد يُفحص قبل ما يُقبل') : level === 'medium' ? bi('Several changes in shared places: each is checked, and the batch waits for you', 'عدة تغييرات في أماكن مشتركة: كل واحد يُفحص، والدفعة تنتظرك') : bi('Many or serious changes: read the batches before you start', 'تغييرات كثيرة أو حساسة: اقرأ الدفعات قبل ما تبدأ') }
          : { level: 'low', why: bi('Nothing in your code changes', 'ما يتغير شي في كودك') },
        on_failure: verb === 'fix'
          ? bi('Nothing reaches your branch: a change that fails a check is left out with its reason, and the kept ones wait as a new branch.', 'ما يوصل شي لفرعك: التغيير اللي يفشل في فحص يُترك مع سببه، والمقبول ينتظر كفرع جديد.')
          : bi('Nothing changes: you see what was found up to that point, and can try again.', 'ما يتغير شي: تشوف اللي انوجد لين ذاك الوقت، وتقدر تعيد.'),
        assistant: DEMO_ASSISTANTS[0], assistants: DEMO_ASSISTANTS,
        handoff: { available: true, request: bi(`EAOS: ${verbOf(verb).label.en} ${chosen.map((c) => c.id).join(', ')}, the EAOS way (status first).`, `EAOS: ${verbOf(verb).label.ar} ${chosen.map((c) => c.id).join('، ')} بطريقة EAOS (ابدأ بـ status).`) },
        irreversible: false, needs_consent: verb === 'fix', confirm: verbOf(verb).changes_code ? { token: CONFIRM } : null,
      }
    }
    const action = actionOf(id)
    if (!action) throw new ActionError(404, `no action named ${id}`)
    return {
      action: id, verb: null, selection: null, cards: [], left_out: [], files: [], batches: [],
      estimate: { minutes_low: id === 'audit' ? 5 : 0, minutes_high: id === 'audit' ? 30 : 1, basis: bi('a rough rule for this step', 'تقدير تقريبي لهذه الخطوة') },
      risk: { level: action.irreversible ? 'high' : action.changes_code ? 'medium' : 'low', why: action.description },
      on_failure: action.changes_code || action.irreversible
        ? bi('Nothing reaches your branch until you confirm it.', 'ما يوصل شي لفرعك إلا بتأكيدك.')
        : bi('Nothing changes: you can try again.', 'ما يتغير شي: تقدر تعيد.'),
      assistant: action.needs_assistant ? DEMO_ASSISTANTS[0] : null, assistants: action.needs_assistant ? DEMO_ASSISTANTS : [],
      handoff: { available: action.needs_assistant, request: action.needs_assistant ? bi(`EAOS: ${action.label.en}`, `EAOS: ${action.label.ar}`) : null },
      irreversible: action.irreversible, needs_consent: action.needs_consent,
      confirm: action.irreversible || action.changes_code ? { token: CONFIRM } : null,
    }
  }

  function get(id: string): Replay {
    const replay = replays.get(id)
    if (!replay) throw new ActionError(404, `not found: ${id}`)
    return replay
  }

  const view = (replay: Replay): Run => ({ ...replay.run, position: queue.includes(replay.run.id) ? queue.indexOf(replay.run.id) + 1 : undefined })
  const later = <T>(value: () => T) => new Promise<T>((resolve, reject) => setTimeout(() => { try { resolve(value()) } catch (error) { reject(error) } }, 120 / speed))

  const client = {
    mode: 'demo' as const,
    /** The runs the demo opens with: a done Fix waiting for Accept or Undo, a Fix waiting for an answer, two queued, and a history. */
    seed() {
      if (seeded) return
      seeded = true
      const cards = cardsOf().filter((card) => !card.state || card.state === 'open')
      const pick = (from: number, n: number) => {
        const out = cards.slice(from, from + n)
        return out.length ? out : Array.from({ length: n }, (_, i) => ({ id: `TASK-${String(from + i + 1).padStart(3, '0')}`, title: 'Example finding', paths: [`src/example-${from + i}.ts`] }))
      }
      const now = Date.now()
      const hour = 3600_000
      const older = create('fix', 'fix', pick(10, 2), [], { kind: 'cards', cards: pick(10, 2).map((c) => c.id) }, now - 50 * hour)
      playOut(older, now - 50 * hour + 2000)
      older.run.outcome = 'accepted'
      emit(older, 'action', bi(`You chose to accept ${older.run.result?.branch}`, `اخترت اعتماد ${older.run.result?.branch}`), { action: 'accept', by: 'person', arguments: { branch: older.run.result?.branch } }, null, now - 49 * hour)
      const explained = create('explain', 'explain', pick(12, 1), [], { kind: 'card', cards: pick(12, 1).map((c) => c.id) }, now - 30 * hour)
      playOut(explained, now - 30 * hour + 1000)
      const failed = create('fix', 'fix', pick(13, 3), [], { kind: 'cards', cards: pick(13, 3).map((c) => c.id) }, now - 26 * hour)
      playOut(failed, now - 26 * hour + 1000, 'failed')
      const stopped = create('verify', 'verify', pick(16, 2), [], { kind: 'cards', cards: pick(16, 2).map((c) => c.id) }, now - 20 * hour)
      playOut(stopped, now - 20 * hour + 1000, 'stopped')
      const done = create('fix', 'fix', pick(0, 4), [], { kind: 'cards', cards: pick(0, 4).map((c) => c.id) }, now - 2 * hour)
      playOut(done, now - 2 * hour + 1000)
      const asking = create('fix', 'fix', pick(4, 3), [], { kind: 'cards', cards: pick(4, 3).map((c) => c.id) }, now - 6 * 60_000)
      setState(asking, 'running', 'its turn came', now - 6 * 60_000 + 800)
      for (const recorded of asking.before) { asking.cursor += 1; step(asking, recorded, now - 5 * 60_000) }
      asking.asked = true
      ask(asking, now - 5 * 60_000 + 1500)
      const verify = create('verify', 'verify', pick(7, 2), [], { kind: 'cards', cards: pick(7, 2).map((c) => c.id) }, now - 4 * 60_000)
      const plan = create('plan', 'plan', pick(9, 3), [], { kind: 'cards', cards: pick(9, 3).map((c) => c.id) }, now - 3 * 60_000)
      queue = [verify.run.id, plan.run.id]
      markSeeded()
    },
    preview: (id: string, body: PreviewBody) => later(() => preview(id, body)),
    start: (body: StartBody) => later(() => {
      const verb = (body.verb ?? null) as VerbId | null
      const action = verb ?? body.action
      const shown = preview(action, body)
      if (shown.confirm && body.confirm !== CONFIRM) throw new ActionError(403, 'this needs your explicit confirmation: open its preview and confirm', 'confirm')
      const cards = verb ? resolveSelection(body.selection, cardsOf()).chosen : []
      const replay = create(verb, action, cards, shown.left_out, verb ? body.selection ?? null : null)
      queue = [...queue, replay.run.id]
      advance()
      changed()
      return view(replay)
    }),
    runs: () => later(() => ({ runs: [...replays.values()].map(view).sort((a, b) => b.created.localeCompare(a.created)), queue: [...queue] })),
    run: (id: string) => ready.then(() => later(() => view(get(id)))),
    follow(id: string, after: number, onEvent: (event: RunEvent) => void, onStatus: (status: StreamStatus) => void) {
      let on = true
      const listener = (event: RunEvent) => { if (on) onEvent(event) }
      onStatus('connecting')
      void ready.then(() => {
        const replay = replays.get(id)
        if (!on) return
        if (!replay) { onStatus('closed'); return }
        onStatus('open')
        replay.events.filter((event) => event.seq > after).forEach(listener)
        if (!followers.has(id)) followers.set(id, new Set())
        followers.get(id)!.add(listener)
      })
      return () => { on = false; followers.get(id)?.delete(listener) }
    },
    control: (id: string, op: Control) => later(() => {
      const replay = get(id)
      const state = replay.run.state
      emit(replay, 'action', op === 'pause' ? bi('You pressed pause', 'ضغطت إيقاف مؤقت') : op === 'resume' ? bi('You pressed resume', 'ضغطت استئناف')
        : op === 'stop' ? bi('You pressed stop', 'ضغطت إيقاف') : bi('You pressed retry', 'ضغطت إعادة المحاولة'), { action: op, by: 'person', arguments: {} })
      if (op === 'pause') {
        if (state !== 'running') throw new ActionError(409, 'only a running run can be paused')
        clearTimeout(replay.timer)
        setState(replay, 'paused', 'pause')
      } else if (op === 'resume') {
        if (state !== 'paused') throw new ActionError(409, 'only a paused run can be resumed')
        setState(replay, 'running', 'resume')
        schedule(replay)
      } else if (op === 'stop') {
        if (TERMINAL.includes(state)) throw new ActionError(409, 'this run has already ended')
        clearTimeout(replay.timer)
        queue = queue.filter((other) => other !== id)
        replay.run = { ...replay.run, question: null }
        setState(replay, 'stopped', 'stop')
        advance()
      } else {
        if (state !== 'failed' && state !== 'stopped') throw new ActionError(409, 'only a run that did not finish can be tried again')
        replay.cursor = 0
        replay.asked = false
        replay.run = { ...replay.run, attempt: replay.run.attempt + 1, result: null, ended: null, started: null, queued_at: iso(Date.now()) }
        setState(replay, 'queued', 'tried again')
        queue = [...queue, id]
        advance()
      }
      changed()
      return view(replay)
    }),
    reorder: (order: string[]) => later(() => {
      const known = new Set(queue)
      if (order.length !== queue.length || !order.every((id) => known.has(id))) throw new ActionError(400, 'the order must name every queued run once')
      queue = [...order]
      changed()
      return [...queue]
    }),
    questions: () => later(() => [...replays.values()].filter((r) => r.run.state === 'waiting_for_person' && r.run.question).map((r) => r.run.question!)),
    answer: (question: string, option: string | null, text?: string | null) => later(() => {
      const replay = get(question.slice(0, question.lastIndexOf('-q')))
      if (replay.run.state !== 'waiting_for_person' || replay.run.question?.id !== question) throw new ActionError(409, 'this question is not waiting for an answer')
      const chosen = replay.run.question.options.find((o) => o.id === option)
      const label = chosen?.label ?? bi(text ?? '', text ?? '')
      emit(replay, 'answer', bi(`You answered: ${label.en}`, `جاوبت: ${label.ar}`), { question, option, text: text ?? null, by: 'person' })
      replay.run = { ...replay.run, question: null }
      setState(replay, 'running', 'the answer')
      schedule(replay)
      changed()
      return view(replay)
    }),
    decide: (id: string, op: 'accept' | 'undo', confirm: string) => later(() => {
      if (confirm !== CONFIRM) throw new ActionError(403, `${op} needs your explicit confirmation: open its preview and confirm`, 'confirm')
      const replay = get(id)
      const branch = replay.run.result?.branch
      if (!branch) throw new ActionError(409, 'this run handed no branch over')
      if (replay.run.outcome) throw new ActionError(409, 'this branch was already decided')
      emit(replay, 'action', op === 'accept' ? bi(`You chose to accept ${branch}`, `اخترت اعتماد ${branch}`) : bi(`You chose to undo ${branch}`, `اخترت رمي ${branch}`), { action: op, by: 'person', arguments: { branch } })
      emit(replay, 'result', op === 'accept' ? bi(`Taken in: ${branch}`, `اعتُمد: ${branch}`) : bi(`Thrown away: ${branch}`, `رُمي: ${branch}`), { branch, outcome: op })
      replay.run = { ...replay.run, outcome: op === 'accept' ? 'accepted' : 'undone' }
      changed()
      return view(replay)
    }),
    watch(onChange: () => void) {
      listeners.add(onChange)
      return () => { listeners.delete(onChange) }
    },
  }
  return client
}
