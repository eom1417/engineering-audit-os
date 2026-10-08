// The pieces of the runs pages: the state chip, a run row, the batch bars, the timeline rows (with the diff and the
// technical detail one tap away), the before/after screens and the result with Accept and Undo.
import { useState, type ReactNode } from 'react'
import { Button } from '../../components/Button'
import { Chip, type Tone } from '../../components/Chip'
import { Go } from '../../components/Go'
import { Icon, type IconName } from '../../components/Icon'
import { STATE_WORDS } from '../../data/actions/contract'
import { duration, labelOf, share, type Batch, type Item, type Screens } from '../../data/actions/derive'
import type { Bi, Run, RunEvent, RunResult, RunState } from '../../data/actions/types'
import { usePrefs } from '../../i18n/prefs'
import { Id, N, Txt } from '../../i18n/text'
import { useCmdWords } from '../../command/words'
import css from './runs.module.css'

const TONE: Record<RunState, Tone> = {
  queued: 'neutral', running: 'accent', paused: 'neutral', waiting_for_person: 'warning', done: 'good', failed: 'critical', stopped: 'neutral',
}

export function StateChip({ state }: { state: RunState }) {
  const { lang } = usePrefs()
  return <Chip tone={TONE[state]}>{STATE_WORDS[state][lang]}</Chip>
}

/** The outcome word a finished run ends with: accepted, undone, waiting for a decision, or its state. */
export function OutcomeChip({ run }: { run: Run }) {
  const w = useCmdWords()
  if (run.outcome === 'accepted') return <Chip tone="good">{w('outcomeAccepted')}</Chip>
  if (run.outcome === 'undone') return <Chip tone="neutral">{w('outcomeUndone')}</Chip>
  if (run.state === 'done' && run.result?.branch) return <Chip tone="accent">{w('waitsForYou')}</Chip>
  return <StateChip state={run.state} />
}

const VERB_ICON: Record<string, IconName> = { fix: 'fix', verify: 'verify', explain: 'explain', plan: 'plan' }

export function RunRow({ run, end }: { run: Run; end?: ReactNode }) {
  const { lang, date } = usePrefs()
  const w = useCmdWords()
  const took = duration(run.started, run.ended, lang)
  const sub = [date(run.created), took && run.ended ? w('took', { d: took }) : null, run.cards.length ? w('cardsCount', { n: run.cards.length }) : null,
    run.attempt > 1 ? w('attempt', { n: run.attempt }) : null].filter(Boolean).join(' · ')
  return (
    <Go to={`/runs/${encodeURIComponent(run.id)}`} className={css.row}>
      <span className={css.rowIcon}><Icon name={VERB_ICON[run.verb ?? ''] ?? 'command'} /></span>
      <span className={css.rowMain}>
        <span className={css.rowTitle}><Txt>{labelOf(run.label, lang)}</Txt></span>
        <span className={css.rowSub}>{sub}</span>
      </span>
      <span className={css.rowEnd}>{end ?? <OutcomeChip run={run} />}</span>
    </Go>
  )
}

export function Meter({ value, label }: { value: number | null; label: string }) {
  const pct = value === null ? 0 : Math.round(value * 100)
  return (
    <span className={css.meter} role="progressbar" aria-label={label} aria-valuemin={0} aria-valuemax={100} aria-valuenow={value === null ? undefined : pct}>
      <span className={css.meterFill} style={{ inlineSize: `${pct}%` }} />
    </span>
  )
}

export function Batches({ batches }: { batches: Batch[] }) {
  const w = useCmdWords()
  const all = share(batches)
  return (
    <div className={css.batches}>
      {batches.length > 1 && (
        <div className={css.batch}>
          <span className={css.batchName}>{w('overall')}</span>
          <Meter value={all} label={w('overall')} />
          <span className={css.batchCount}>{all === null ? '' : `${Math.round(all * 100)}%`}</span>
        </div>
      )}
      {batches.map((b) => (
        <div key={b.number} className={css.batch}>
          <span className={css.batchName}>{b.number ? w('batchN', { n: b.number }) : w('progress')}</span>
          <Meter value={b.total ? b.done / b.total : null} label={b.number ? w('batchN', { n: b.number }) : w('progress')} />
          <span className={css.batchCount}>{w('doneOfTotal', { d: b.done, t: b.total })}</span>
        </div>
      ))}
    </div>
  )
}

const KIND_ICON: Record<string, IconName> = {
  state: 'pulse', step: 'chevron', read: 'file', edit: 'edit', check: 'pass', screenshot: 'eye', question: 'inbox', answer: 'check',
  result: 'branch', error: 'fail', action: 'command', say: 'say', progress: 'pulse',
}

function time(at: string): string {
  const when = new Date(at)
  return Number.isNaN(when.getTime()) ? '' : when.toISOString().slice(11, 19)
}

function Disclosure({ open, label, onToggle }: { open: boolean; label: string; onToggle: () => void }) {
  return (
    <Button variant="ghost" className={css.more} onPress={onToggle} aria-expanded={open}>
      <Icon name="chevronDown" className={open ? css.flip : undefined} />{label}
    </Button>
  )
}

/** A unified diff, its lines marked added or removed by colour and sign; always LTR with its own scroll. */
export function Diff({ text, label }: { text: string; label: string }) {
  return (
    <pre className={css.diff} tabIndex={0} aria-label={label} data-scroll-x="">
      <code>{text.split('\n').map((line, i) => {
        const kind = line.startsWith('+++') || line.startsWith('---') ? 'file' : line.startsWith('@@') ? 'hunk' : line.startsWith('+') ? 'add' : line.startsWith('-') ? 'del' : 'ctx'
        return <span key={i} className={css[`d_${kind}`]}>{line || ' '}{'\n'}</span>
      })}</code>
    </pre>
  )
}

function EventRow({ event }: { event: RunEvent }) {
  const { lang } = usePrefs()
  const w = useCmdWords()
  const [open, setOpen] = useState(false)
  const [detail, setDetail] = useState(false)
  const data = event.data
  const failed = (event.kind === 'check' && data.passed === false) || event.kind === 'error'
  const icon: IconName = event.kind === 'check' ? (data.passed === false ? 'fail' : 'pass') : KIND_ICON[event.kind] ?? 'chevron'
  const quiet = event.kind === 'state' || event.kind === 'action'
  return (
    <li className={[css.ev, quiet && css.evQuiet, failed && css.evBad, event.kind === 'check' && !failed && css.evGood].filter(Boolean).join(' ')}>
      <span className={css.evIcon}><Icon name={icon} /></span>
      <div className={css.evMain}>
        <p className={css.evText}><Txt>{event.text[lang]}</Txt></p>
        {event.kind === 'edit' && Array.isArray(data.paths) && (
          <div className={css.evMeta}>
            {(data.paths as string[]).map((p) => <Id key={p} value={p} keep={3} />)}
            {data.kept === true && <Chip tone="good">{w('kept')}</Chip>}
            {data.kept === false && <Chip tone="critical">{w('leftOut')}</Chip>}
          </div>
        )}
        {event.kind === 'check' && typeof data.summary === 'string' && data.summary && (
          <div className={css.evMeta}><Id value={String(data.name ?? '')} /><span>{data.summary}</span></div>
        )}
        {event.kind === 'edit' && typeof data.diff === 'string' && data.diff && (
          <>
            <Disclosure open={open} label={open ? w('hideChange') : w('showChange')} onToggle={() => setOpen(!open)} />
            {open && <Diff text={data.diff} label={w('showChange')} />}
          </>
        )}
        {event.detail && (
          <>
            <Disclosure open={detail} label={detail ? w('hideDetail') : w('showDetail')} onToggle={() => setDetail(!detail)} />
            {detail && <pre className={css.detail} tabIndex={0}>{event.detail}</pre>}
          </>
        )}
      </div>
      <time className={css.evTime} dateTime={event.at}>{time(event.at)}</time>
    </li>
  )
}

function ReadsRow({ events }: { events: RunEvent[] }) {
  const { lang } = usePrefs()
  const w = useCmdWords()
  const [open, setOpen] = useState(false)
  if (events.length === 1) return <EventRow event={events[0]} />
  return (
    <li className={css.ev}>
      <span className={css.evIcon}><Icon name="file" /></span>
      <div className={css.evMain}>
        <p className={css.evText}>{w('readN', { n: events.length })}</p>
        <Disclosure open={open} label={open ? w('hideDetail') : w('showDetail')} onToggle={() => setOpen(!open)} />
        {open && <ul className={css.reads}>{events.map((e) => <li key={e.seq}>{typeof e.data.path === 'string' ? <Id value={e.data.path} /> : <Txt>{e.text[lang]}</Txt>}</li>)}</ul>}
      </div>
      <time className={css.evTime} dateTime={events[0].at}>{time(events[0].at)}</time>
    </li>
  )
}

export function Timeline({ items }: { items: Item[] }) {
  const w = useCmdWords()
  return (
    <ol className={css.timeline} aria-label={w('whatHappened')}>
      {items.map((item) => item.kind === 'reads'
        ? <ReadsRow key={`r${item.events[0].seq}`} events={item.events} />
        : <EventRow key={item.event.seq} event={item.event} />)}
    </ol>
  )
}

function Shot({ event, word }: { event?: RunEvent; word: string }) {
  const w = useCmdWords()
  const src = typeof event?.data.src === 'string' ? event.data.src : null
  return (
    <figure className={css.shot}>
      {src ? <img src={src} alt={`${word}: ${String(event?.data.route ?? '')}`} className={css.shotImg} width={180} height={300} />
        : <div className={css.shotNone}>{event ? <Txt>{w('screenSaved', { path: String(event.data.path ?? '') })}</Txt> : '—'}</div>}
      <figcaption className={css.shotCap}>{word}{event && <> · <Id value={`${event.data.route ?? ''} ${event.data.viewport ?? ''}`.trim()} /></>}</figcaption>
    </figure>
  )
}

export function ScreenPairs({ screens }: { screens: Screens[] }) {
  const w = useCmdWords()
  return (
    <div className={css.pairs}>
      {screens.map((pair, i) => (
        <div key={i} className={css.pair}>
          {pair.batch !== null && <span className={css.pairTitle}>{w('batchN', { n: pair.batch })}</span>}
          <div className={css.pairShots}>
            <Shot event={pair.before} word={w('before')} />
            <Shot event={pair.after} word={w('after')} />
          </div>
        </div>
      ))}
    </div>
  )
}

export function ResultFacts({ result }: { result: RunResult }) {
  const w = useCmdWords()
  const { lang } = usePrefs()
  const answer = result.answer as Bi | string | null | undefined
  const words = typeof answer === 'string' ? answer : answer && typeof answer === 'object' && 'en' in answer ? answer[lang] : null
  return (
    <div className={css.result}>
      {words && <p className={css.answer}><Txt block>{words}</Txt></p>}
      <dl className={css.facts}>
        {result.branch && <div><dt>{w('branch')}</dt><dd><Icon name="branch" /><Id value={result.branch} /></dd></div>}
        {result.diff_stat && <div><dt>{w('changes')}</dt><dd className="num">{w('filesCount', { n: result.diff_stat.files })}<span aria-hidden="true">·</span><bdi dir="ltr" className={css.stat}>+{result.diff_stat.insertions} −{result.diff_stat.deletions}</bdi></dd></div>}
        {result.tests && <div><dt>{w('tests')}</dt><dd>{result.tests.passed === false ? <Chip tone="critical">{w('failed')}</Chip> : <Chip tone="good">{w('passed')}</Chip>}<span className={css.factSub}><Txt>{result.tests.summary}</Txt></span></dd></div>}
      </dl>
      {result.cards_closed.length > 0 && (
        <section className={css.closed} aria-label={w('cardsClosed', { n: result.cards_closed.length })}>
          <h3 className={css.subTitle}>{w('cardsClosed', { n: result.cards_closed.length })}</h3>
          <ul className={css.chips}>
            {result.cards_closed.map((id) => <li key={id}><Go to="/problems" search={{ card: id }} className={css.cardLink}><Id value={id} /></Go></li>)}
          </ul>
        </section>
      )}
      {result.indicators.length > 0 && (
        <section aria-label={w('indicators')}>
          <h3 className={css.subTitle}>{w('indicators')}</h3>
          <ul className={css.indicators}>
            {result.indicators.map((row) => (
              <li key={row.id}>
                <span className={css.indName}><Txt>{row.id}</Txt></span>
                <span className={css.indMove}>
                  {row.before === null ? '—' : <N value={row.before} />}<Icon name="arrow" size={14} />{row.after === null ? '—' : <N value={row.after} />}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  )
}
