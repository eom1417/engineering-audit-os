// The recorded runs the demo replays: what a Fix, Verify, Explain or Plan run streams, event by event, in the
// contract's shapes (docs/studio-actions.json `events`). Recorded once from the run manager's event log and kept as
// a template, so the demo replays it over the cards of the report that is open. Nothing here reaches a project.
import type { Bi, EventKind, Question, RunResult, VerbId } from './types'

export interface CardLike { id: string; title?: string | null; paths?: string[]; severity?: string | null }

/** One recorded step: an event after `after` ms, or a question the replay waits on. */
export interface Step { after: number; kind: EventKind; text: Bi; data: Record<string, unknown>; detail?: string | null }

/** The demo shows two batches of two cards (the server batches ten), so a short selection still shows batching. */
export const DEMO_BATCH = 2

const bi = (en: string, ar: string): Bi => ({ en, ar })

const EDITS: { before: string; after: string[]; added?: string }[] = [
  { before: '  const response = await fetch(url)', after: ['  const response = await fetchWithTimeout(url, { timeout: 10_000 })'], added: "import { fetchWithTimeout } from './http'" },
  { before: '  } catch (error) {}', after: ['  } catch (error) {', "    log.warn('load failed', { url, error })", '    throw error', '  }'], added: "import { log } from './log'" },
  { before: '  if (user.role == "admin") {', after: ["  if (user.role === 'admin') {"] },
  { before: '  items.forEach(async (item) => await save(item))', after: ['  await Promise.all(items.map((item) => save(item)))'] },
]

/** A unified diff for one recorded edit of `path` (the shape the edit event carries). */
export function diffFor(path: string, index: number): string {
  const edit = EDITS[index % EDITS.length]
  const lines = [`--- a/${path}`, `+++ b/${path}`]
  if (edit.added) lines.push('@@ -1,2 +1,3 @@', `+${edit.added}`, " import { useState } from 'react'", ' ')
  const at = 18 + index * 7
  lines.push(`@@ -${at},5 +${at},${4 + edit.after.length} @@`, ' export async function load(url: string) {', '   const started = Date.now()',
    `-${edit.before}`, ...edit.after.map((line) => `+${line}`), '   report(Date.now() - started)', '   return response')
  return lines.join('\n')
}

/** A small drawn screen, before or after a fix: the kind of picture the screen gate records. */
export function screenFor(when: 'before' | 'after', index: number): string {
  const broken = when === 'before'
  const rows = [0, 1, 2, 3].map((i) => {
    const y = 96 + i * 46
    const wide = broken && i === 1 + (index % 2) ? 196 : 148
    return `<rect x="16" y="${y}" width="${wide}" height="34" rx="6" fill="#ffffff" stroke="${broken && wide > 148 ? '#c92a2a' : '#d8d9df'}"/>`
      + `<rect x="26" y="${y + 9}" width="${60 + ((i * 23) % 50)}" height="6" rx="3" fill="#8a8e99"/>`
      + `<rect x="26" y="${y + 20}" width="${40 + ((i * 17) % 40)}" height="5" rx="2.5" fill="#cbcdd5"/>`
  }).join('')
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 180 300"><rect width="180" height="300" rx="14" fill="#f0f1f3"/>`
    + `<rect x="0" y="0" width="180" height="44" rx="14" fill="#17191d"/><rect x="16" y="17" width="70" height="9" rx="4.5" fill="#e0e1e6"/>`
    + `<rect x="16" y="58" width="${broken ? 120 : 96}" height="14" rx="4" fill="#5d616b"/>${rows}`
    + `<rect x="16" y="262" width="148" height="24" rx="6" fill="${broken ? '#b6b9c3' : '#2068c2'}"/></svg>`
  return `data:image/svg+xml,${encodeURIComponent(svg)}`
}

const title = (card: CardLike) => card.title || card.id

/** The run-consent question, the first of the three EAOS questions a Fix run may ask. */
export function consentQuestion(run: string): Question {
  return {
    id: `${run}-q1`, run,
    text: bi('May EAOS start your app in its isolated copy, to check every fix on the real screens? Your own files are not touched.',
      'هل يشغّل EAOS تطبيقك في نسخته المعزولة ليتأكد من كل إصلاح على الشاشات الحقيقية؟ ملفاتك أنت ما تُلمس.'),
    options: [{ id: 'yes', label: bi('Yes, run it', 'نعم، شغّله') }, { id: 'no', label: bi('No, check without running it', 'لا، افحص بدون تشغيل') }],
    recommendation: 'yes',
    why: 'run consent',
  }
}

function fixSteps(cards: CardLike[], run: string, branch: string): { before: Step[]; after: Step[]; question: Question } {
  const before: Step[] = [
    { after: 500, kind: 'step', text: bi('Checking where the project stands', 'أشوف وين وصل المشروع'), data: { tool: 'status', card: null } },
    { after: 900, kind: 'step', text: bi('Asking whether your app may run, to check the fixes', 'أسأل هل يجوز تشغيل تطبيقك للتأكد من الإصلاحات'), data: { tool: 'run_setup', card: null } },
  ]
  const after: Step[] = [
    { after: 700, kind: 'check', text: bi('Your app starts in the isolated copy', 'تطبيقك يشتغل في النسخة المعزولة'), data: { name: 'run_try', passed: true, summary: 'npm run dev answered on its port in 6 s' } },
    { after: 800, kind: 'step', text: bi('Preparing an isolated copy and the first batch', 'أجهّز نسخة معزولة وأول دفعة'), data: { tool: 'fix_start', card: null } },
  ]
  const batches: CardLike[][] = []
  for (let at = 0; at < cards.length; at += DEMO_BATCH) batches.push(cards.slice(at, at + DEMO_BATCH))
  const closed: string[] = []
  let edit = 0
  batches.forEach((batch, b) => {
    const number = b + 1
    after.push({ after: 400, kind: 'progress', text: bi(`Batch ${number} of ${batches.length}: started`, `الدفعة ${number} من ${batches.length}: بدأت`), data: { batch: number, done: 0, total: batch.length } })
    after.push({ after: 300, kind: 'screenshot', text: bi('The screens before the change', 'الشاشات قبل التغيير'), data: { route: '/', viewport: '390x844', when: 'before', path: `screens/batch-${number}/before.png`, src: screenFor('before', b) } })
    batch.forEach((card, i) => {
      const paths = card.paths?.length ? card.paths : [`src/${card.id.toLowerCase()}.ts`]
      const failing = b === batches.length - 1 && i === batch.length - 1 && cards.length > 2
      after.push({ after: 700, kind: 'step', text: bi(`Working on ${card.id}: ${title(card)}`, `أشتغل على ${card.id}: ${title(card)}`), data: { tool: 'finding', card: card.id } })
      for (const path of paths.slice(0, 2)) {
        after.push({ after: 500, kind: 'read', text: bi(`Read ${path}`, `قرأت ${path}`), data: { path, tool: 'fix_read' } })
      }
      const changed = paths.slice(0, 1)
      after.push({
        after: 900, kind: 'edit', text: bi(`Changed ${changed.length} file for ${card.id}`, `غيّرت ملفًا واحدًا لـ ${card.id}`),
        data: { card: card.id, paths: changed, diff: changed.map((path) => diffFor(path, edit++)).join('\n'), kept: !failing },
      })
      if (failing) {
        after.push({ after: 900, kind: 'check', text: bi(`The type check failed for ${card.id}: the change is left out`, `فحص الأنواع فشل في ${card.id}: تركت التغيير`), data: { name: 'typecheck', passed: false, summary: 'TS2345 in one file' }, detail: `src/${card.id.toLowerCase()}.ts(41,7): error TS2345: Argument of type 'string | undefined' is not assignable to parameter of type 'string'.` })
        after.push({ after: 500, kind: 'say', text: bi(`I left ${card.id} out: its fix broke the type check. It stays open, with the reason as a note.`, `تركت ${card.id}: إصلاحه كسر فحص الأنواع. تبقى مفتوحة ومعها السبب كملاحظة.`), data: { words: 'Left out after a failed type check.' } })
      } else {
        closed.push(card.id)
        after.push({ after: 800, kind: 'check', text: bi(`The build and the tests pass with ${card.id}`, `البناء والاختبارات تنجح مع ${card.id}`), data: { name: 'tests', passed: true, summary: '214 passed' } })
      }
      after.push({ after: 300, kind: 'progress', text: bi(`Batch ${number}: ${i + 1} of ${batch.length} done`, `الدفعة ${number}: انتهى ${i + 1} من ${batch.length}`), data: { batch: number, done: i + 1, total: batch.length } })
    })
    after.push({ after: 700, kind: 'check', text: bi('Every endpoint still answers', 'كل نقاط الخدمة ما زالت ترد'), data: { name: 'endpoints', passed: true, summary: '38 of 38' } })
    after.push({ after: 600, kind: 'screenshot', text: bi('The screens after the change', 'الشاشات بعد التغيير'), data: { route: '/', viewport: '390x844', when: 'after', path: `screens/batch-${number}/after.png`, src: screenFor('after', b) } })
    after.push({ after: 500, kind: 'check', text: bi('Every recorded screen still passes', 'كل الشاشات المسجلة ما زالت تنجح'), data: { name: 'screens', passed: true, summary: '12 of 12' } })
  })
  const result: RunResult = {
    branch, diff_stat: { files: closed.length + 1, insertions: closed.length * 9 + 3, deletions: closed.length * 4 },
    tests: { passed: true, summary: `${closed.length} change(s) passed every check; ${cards.length - closed.length} left out` },
    cards_closed: closed, indicators: [{ id: 'health', before: 61, after: 61 + closed.length * 2 }, { id: 'open cards', before: 120, after: 120 - closed.length }],
  }
  after.push({ after: 700, kind: 'step', text: bi('Handing the kept fixes over as a new branch', 'أسلّم الإصلاحات المقبولة كفرع جديد'), data: { tool: 'fix_finish', card: null } })
  after.push({ after: 900, kind: 'result', text: bi(`Ready: ${closed.length} fixed on ${branch}, waiting for you to take it in or throw it away`, `جاهز: انصلح ${closed.length} على ${branch}، ينتظر تعتمده أو ترميه`), data: result as unknown as Record<string, unknown> })
  return { before, after, question: consentQuestion(run) }
}

const ANSWERS: Record<Exclude<VerbId, 'fix'>, (cards: CardLike[]) => Bi> = {
  explain: (cards) => bi(
    `${cards.map((c) => c.id).join(', ')}: ${cards.length === 1 ? 'this code' : 'these places'} can fail without telling anyone, so a person sees an empty screen and nobody knows why. Fixing it adds a clear error and a log line; nothing else changes.`,
    `${cards.map((c) => c.id).join('، ')}: ${cards.length === 1 ? 'هذا الكود' : 'هذه الأماكن'} ممكن تفشل بصمت، فيشوف الشخص شاشة فاضية وما أحد يدري ليش. الإصلاح يضيف رسالة خطأ واضحة وسطرًا في السجل، وما يتغير شي ثاني.`),
  verify: (cards) => bi(
    `${Math.max(1, cards.length - 1)} still real, with the evidence on the same lines; ${cards.length > 1 ? '1 already gone after an earlier change' : 'none gone'}. Written as a note on each card.`,
    `${Math.max(1, cards.length - 1)} ما زالت موجودة ودليلها في نفس الأسطر؛ ${cards.length > 1 ? 'وواحدة اختفت بعد تغيير سابق' : 'وما اختفى شي'}. كتبتها ملاحظة على كل بطاقة.`),
  plan: (cards) => bi(
    `Two batches: first ${cards.slice(0, Math.ceil(cards.length / 2)).map((c) => c.id).join(', ')} (low risk, no screen changes), then the rest, which touch shared code and wait for the first.`,
    `دفعتان: أولًا ${cards.slice(0, Math.ceil(cards.length / 2)).map((c) => c.id).join('، ')} (خطرها قليل وما تغيّر الشاشات)، ثم الباقي لأنه يلمس كودًا مشتركًا وينتظر الأولى.`),
}

function readSteps(verb: Exclude<VerbId, 'fix'>, cards: CardLike[]): Step[] {
  const steps: Step[] = [{ after: 500, kind: 'step', text: bi('Checking where the project stands', 'أشوف وين وصل المشروع'), data: { tool: 'status', card: null } }]
  for (const card of cards.slice(0, 4)) {
    steps.push({ after: 600, kind: 'step', text: bi(`Reading the evidence of ${card.id}`, `أقرأ دليل ${card.id}`), data: { tool: 'finding', card: card.id } })
    if (card.paths?.[0]) steps.push({ after: 450, kind: 'read', text: bi(`Read ${card.paths[0]}`, `قرأت ${card.paths[0]}`), data: { path: card.paths[0], tool: 'finding' } })
  }
  steps.push({ after: 700, kind: 'step', text: bi('Looking at what depends on it', 'أشوف وش يعتمد عليه'), data: { tool: 'impact', card: null } })
  const answer = ANSWERS[verb](cards)
  steps.push({ after: 900, kind: 'say', text: answer, data: { words: answer.en } })
  const result: RunResult = { branch: null, diff_stat: null, tests: null, cards_closed: [], indicators: [], answer }
  steps.push({ after: 500, kind: 'result', text: bi('Done: the answer is above', 'خلص: الجواب فوق'), data: result as unknown as Record<string, unknown> })
  return steps
}

/** The recorded steps of a run over `cards`: a Fix run waits on its question between `before` and `after`. */
export function recordingFor(verb: VerbId | null, cards: CardLike[], run: string, branch: string, label: Bi): { before: Step[]; after: Step[]; question: Question | null } {
  if (verb === 'fix') return fixSteps(cards, run, branch)
  if (verb) return { before: readSteps(verb, cards), after: [], question: null }
  const words = bi(`This is an example run of “${label.en}”. In the live Studio, EAOS answers here with the real result.`,
    `هذا تشغيل تجريبي لـ «${label.ar}». في الاستوديو الحي يرد EAOS هنا بالنتيجة الحقيقية.`)
  return {
    before: [
      { after: 400, kind: 'step', text: bi(`Calling EAOS: ${label.en}`, `أنادي EAOS: ${label.ar}`), data: { tool: null, card: null } },
      { after: 900, kind: 'say', text: words, data: { words: words.en } },
      { after: 400, kind: 'result', text: bi('Done', 'خلص'), data: { branch: null, diff_stat: null, tests: null, cards_closed: [], indicators: [], answer: words } },
    ],
    after: [], question: null,
  }
}
