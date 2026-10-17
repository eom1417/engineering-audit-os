// The preview sheet: before anything runs, what will happen, the cards (and the ones left out, with why), the files,
// the batches, the time, the risk, what happens on failure and which assistant runs it; then an explicit confirm,
// with a second "I understand" for what cannot be undone. An action with inputs asks for them first. In a snapshot
// (opened from a file) it explains how to start the live Studio, and offers the request to copy to an assistant.
import { useNavigate } from '@tanstack/react-router'
import { useEffect, useMemo, useState, type Dispatch, type ReactNode, type SetStateAction } from 'react'
import { Input, Label, TextArea, TextField } from 'react-aria-components'
import { Button, CopyRequestButton, copyText } from '../components/Button'
import { Chip, SeverityGlyph, type Tone } from '../components/Chip'
import { Segmented } from '../components/Controls'
import { FoldList, StateMessage } from '../components/Panel'
import { Sheet, SheetSub } from '../components/Sheet'
import { useToast } from '../components/Toast'
import { actionOf, personInputs, SNAPSHOT, verbOf } from '../data/actions/contract'
import { useActions } from '../data/actions/store'
import { ActionError, type Bi, type CheckOffer, type FixWhere, type JsonSchema, type Preview, type PreviewBody, type Selection, type StartBody, type WhereChoice } from '../data/actions/types'
import type { Severity } from '../data/types'
import { usePrefs } from '../i18n/prefs'
import { Id, N, Txt } from '../i18n/text'
import { CheckOptions, checkInputs, freshOf, type CheckChoice } from './CheckOptions'
import { useCommand, type CommandRequest } from './command'
import { SelectBox } from './SelectBox'
import { useCmdWords } from './words'
import css from './command.module.css'

const RISK_TONE: Record<Preview['risk']['level'], Tone> = { low: 'good', medium: 'warning', high: 'critical' }

/** The request a person pastes to their assistant, in both languages: the verb or action, the cards, the EAOS way. */
export function requestText(request: CommandRequest, preview?: Preview | null): Bi {
  if (preview?.handoff.request) return preview.handoff.request
  const cards = selectionText(request.selection)
  if (request.verb) {
    const verb = verbOf(request.verb)
    return {
      en: `With EAOS: ${verb.label.en} ${cards}. Follow the EAOS way (status first), and ask me before anything I must decide.`,
      ar: `باستخدام EAOS: ${verb.label.ar} ${cards}. اتبع طريقة EAOS (ابدأ بـ status)، واسألني قبل أي شيء يحتاج قراري.`,
    }
  }
  const action = actionOf(request.action ?? '')
  const inputs = Object.entries(request.inputs ?? {}).map(([k, v]) => `${k}=${JSON.stringify(v)}`).join(', ')
  return {
    en: `Use the EAOS tool ${action?.tool ?? request.action}${inputs ? ` with ${inputs}` : ''}: ${action?.label.en ?? ''}.`,
    ar: `استخدم أداة EAOS ${action?.tool ?? request.action}${inputs ? ` مع ${inputs}` : ''}: ${action?.label.ar ?? ''}.`,
  }
}

/** What a request is about, in a few words: its cards, else its plan step, else its group. */
function selectionText(selection: CommandRequest['selection']): string {
  if (selection?.cards) return selection.cards.join(', ')
  if (selection?.step) return `step ${selection.step}`
  return selection?.group ? `${selection.group.by} ${selection.group.value}` : ''
}

function Block({ title, children }: { title: string; children: ReactNode }) {
  return <section className={css.pvBlock}><SheetSub>{title}</SheetSub>{children}</section>
}

function SnapshotBody({ request }: { request: CommandRequest }) {
  const w = useCmdWords()
  const { lang } = usePrefs()
  const toast = useToast()
  return (
    <div className={css.pvBody}>
      <p className={css.pvLead}>{SNAPSHOT.text[lang]}</p>
      <ol className={css.snapSteps}>
        <li>{w('snapshotStep1')}</li>
        <li>
          {w('snapshotStep2')}
          <div className={css.command}>
            <code><bdi dir="ltr">{SNAPSHOT.command}</bdi></code>
            <Button variant="secondary" icon="copy" onPress={async () => toast((await copyText(SNAPSHOT.command)) ? w('copyCommand') + ' ✓' : '')}>{w('copyCommand')}</Button>
          </div>
        </li>
      </ol>
      <p className={css.pvMuted}>{w('orAssistant')}</p>
      <CopyRequestButton request={requestText(request)[lang]} label={w('copyRequest')} block />
    </div>
  )
}

type Field = [string, JsonSchema]

function kindOf(schema: JsonSchema): string {
  const types = Array.isArray(schema.type) ? schema.type.filter((t) => t !== 'null') : [schema.type]
  if (schema.enum) return 'enum'
  return String(types[0] ?? 'string')
}

/** Turns the form's text into the inputs the contract's schema asks for. */
function parse(fields: Field[], values: Record<string, string | boolean>): Record<string, unknown> {
  const inputs: Record<string, unknown> = {}
  for (const [name, schema] of fields) {
    const raw = values[name]
    const kind = kindOf(schema)
    if (kind === 'boolean') { if (raw) inputs[name] = true; continue }
    const text = String(raw ?? '').trim()
    if (!text) continue
    if (kind === 'integer' || kind === 'number') inputs[name] = Number(text)
    else if (kind === 'array') inputs[name] = schema.items?.type === 'object' ? JSON.parse(text) : text.split(/[\n,]+/).map((s) => s.trim()).filter(Boolean)
    else if (kind === 'object') inputs[name] = JSON.parse(text)
    else inputs[name] = text
  }
  return inputs
}

function InputsForm({ fields, required, values, onChange }:
  { fields: Field[]; required: string[]; values: Record<string, string | boolean>; onChange: (name: string, value: string | boolean) => void }) {
  const w = useCmdWords()
  return (
    <div className={css.form}>
      {fields.map(([name, schema]) => {
        const kind = kindOf(schema)
        const label = <><Id value={name} />{required.includes(name) && <span className={css.req}>{w('required')}</span>}</>
        if (kind === 'boolean') {
          return (
            <div key={name} className={css.check}>
              <SelectBox checked={Boolean(values[name])} label={name} onToggle={() => onChange(name, !values[name])} />
              <span>{label}{schema.description && <span className={css.hint}><Txt>{schema.description}</Txt></span>}</span>
            </div>
          )
        }
        if (kind === 'enum') {
          return (
            <label key={name} className={css.field}>
              <span className={css.fieldLabel}>{label}</span>
              <select className={css.select} value={String(values[name] ?? '')} onChange={(e) => onChange(name, e.target.value)}>
                <option value="">—</option>
                {(schema.enum ?? []).filter((v) => v !== null).map((v) => <option key={String(v)} value={String(v)}>{String(v)}</option>)}
              </select>
            </label>
          )
        }
        const long = kind === 'array' || kind === 'object' || name === 'text' || name === 'question' || name === 'spec' || name === 'proposal'
        return (
          <TextField key={name} className={css.field} value={String(values[name] ?? '')} onChange={(v) => onChange(name, v)} isRequired={required.includes(name)}>
            <Label className={css.fieldLabel}>{label}</Label>
            {long ? <TextArea className={css.textarea} rows={3} /> : <Input className={css.input} inputMode={kind === 'integer' || kind === 'number' ? 'numeric' : undefined} />}
            {schema.description && <span className={css.hint}><Txt>{schema.description}</Txt></span>}
          </TextField>
        )
      })}
    </div>
  )
}

/** Where a Fix is built and where its fixes arrive: on a new branch (named after the group, editable), on an EAOS
 * branch still waiting for a decision (the fixes go on top of it), or directly on the base branch (built and checked in
 * the isolated copy as always, landing on the base once every check passes; never a protected branch). The base comes
 * with its short commit (the one the confirmation pins); a protected branch is shown with its reason, never choosable. */
function WhereBlock({ where, onChange }: { where: FixWhere; onChange: (next: WhereChoice) => void }) {
  const w = useCmdWords()
  const { lang } = usePrefs()
  const base = where.base?.branch ?? ''
  const mode = where.mode ?? 'new'
  const [name, setName] = useState(mode === 'new' ? where.deliver_as ?? '' : '')
  useEffect(() => { if (mode === 'new') setName(where.deliver_as ?? '') }, [where.deliver_as, mode])
  // an empty deliver_as asks the server for the default name again (the group's, else wave-N)
  const pick = (next: string) => {
    if (next === mode) return
    if (next === 'direct') onChange({ deliver_as: base })
    else if (next === 'continue') onChange({ deliver_as: where.continuable[0]?.name ?? '' })
    else onChange({ deliver_as: '' })
  }
  const options = [
    { id: 'new', label: w('modeNew') },
    ...(where.continuable.length ? [{ id: 'continue', label: w('modeContinue') }] : []),
    ...(!where.direct_blocked && base ? [{ id: 'direct', label: w('modeDirect', { b: base }) }] : []),
  ]
  return (
    <Block title={w('where')}>
      <div className={css.form} data-where="block">
        <label className={css.field}>
          <span className={css.fieldLabel}>{w('buildOn')}</span>
          <select className={css.select} data-where="base" value={base} onChange={(e) => onChange({ base: e.target.value, deliver_as: '' })}>
            {where.branches.map((b) => (
              <option key={b.name} value={b.name} disabled={Boolean(b.blocked) && b.name !== base}>
                {b.blocked ? `${b.name} · ${b.blocked[lang]}` : `${b.name} · ${b.short}`}
              </option>
            ))}
          </select>
          {where.base && <span className={css.hint}><bdi dir="ltr">{where.base.short}</bdi>{where.base.checked_out ? ` · ${w('openInFolder')}` : ` · ${w('notOpenBase')}`}</span>}
        </label>
        <Segmented label={w('deliverMode')} value={mode} onChange={pick} comfortable options={options} />
        {mode === 'new' && (
          <>
            <TextField className={css.field} value={name} onChange={setName}>
              <Label className={css.fieldLabel}>{w('deliverAs')}</Label>
              <Input className={css.input} dir="ltr" data-where="deliver" />
              <span className={css.hint}>{w('modeNewHint')}</span>
            </TextField>
            {name.trim() && name.trim() !== where.deliver_as && (
              <Button variant="secondary" icon="eye" onPress={() => onChange({ deliver_as: name.trim() })}>{w('updatePreview')}</Button>
            )}
          </>
        )}
        {mode === 'continue' && (
          <label className={css.field}>
            <span className={css.fieldLabel}>{w('continueOn')}</span>
            <select className={css.select} data-where="continue" value={where.deliver_as ?? ''} onChange={(e) => onChange({ deliver_as: e.target.value })}>
              {where.continuable.map((b) => <option key={b.name} value={b.name}>{`${b.name} · ${b.short}`}</option>)}
            </select>
            <span className={css.hint}>{w('modeContinueHint')}</span>
          </label>
        )}
        {mode === 'direct' ? <p className={css.pvNote} data-where="direct">{w('modeDirectHint', { b: base })}</p> : (
          <label className={css.field}>
            <span className={css.fieldLabel}>{w('mergeInto')}</span>
            <select className={css.select} data-where="target" value={where.merge_into ?? ''} onChange={(e) => onChange({ merge_into: e.target.value })}>
              {where.branches.map((b) => (
                <option key={b.name} value={b.name} disabled={Boolean(b.blocked) && b.name !== where.merge_into}>
                  {b.blocked ? `${b.name} · ${b.blocked[lang]}` : b.name}
                </option>
              ))}
            </select>
          </label>
        )}
        {where.direct_blocked && mode !== 'direct' && <p className={css.hint}><Txt>{where.direct_blocked[lang]}</Txt></p>}
        {where.problem && <p className={css.pvWarn} role="note"><Txt>{where.problem[lang]}</Txt></p>}
      </div>
    </Block>
  )
}

function minutes(preview: Preview, w: ReturnType<typeof useCmdWords>): string {
  const { minutes_low: low, minutes_high: high } = preview.estimate
  if (low === null || high === null) return w('minutesUnknown')
  return w('minutes', { a: low, b: high })
}

function PreviewBody({ preview, request, onWhere }: { preview: Preview; request: CommandRequest; onWhere: (next: WhereChoice) => void }) {
  const w = useCmdWords()
  const { lang } = usePrefs()
  const action = actionOf(preview.action)
  const lead = preview.verb ? verbOf(preview.verb).result[lang] : action?.description[lang]
  return (
    <div className={css.pvBody}>
      {lead && <p className={css.pvLead}><Txt>{lead}</Txt></p>}
      <PreviewFacts preview={preview} />
      {preview.where && <WhereBlock where={preview.where} onChange={onWhere} />}
      <RiskBlock preview={preview} />
      <Block title={w('onFailure')}><p className={css.pvText}><Txt>{preview.on_failure[lang]}</Txt></p></Block>
      {preview.cards.length > 0 && <CardsBlock preview={preview} />}
      <PreviewLists preview={preview} />
      {(preview.assistant || preview.handoff.available) && <AssistantBlock preview={preview} request={request} />}
      {preview.needs_consent && <p className={css.pvNote}>{w('consentLead')}</p>}
      {preview.irreversible && <p className={css.pvWarn} role="note">{w('irreversibleLead')}</p>}
    </div>
  )
}

/** The cards, files and batches counted, and the time it may take. */
function PreviewFacts({ preview }: { preview: Preview }) {
  const w = useCmdWords()
  return (
    <dl className={css.facts}>
      {preview.verb && <div><dt>{w('cardsN', { n: preview.cards.length })}</dt><dd><N value={preview.cards.length} /></dd></div>}
      {preview.files.length > 0 && <div><dt>{w('filesN', { n: preview.files.length })}</dt><dd><N value={preview.files.length} /></dd></div>}
      {preview.batches.length > 0 && <div><dt>{w('batchesN', { n: preview.batches.length })}</dt><dd><N value={preview.batches.length} /></dd></div>}
      <div><dt>{w('time')}</dt><dd className="num">{minutes(preview, w)}</dd></div>
    </dl>
  )
}

function RiskBlock({ preview }: { preview: Preview }) {
  const w = useCmdWords()
  const { lang } = usePrefs()
  return (
    <Block title={w('risk')}>
      <div className={css.risk}>
        <Chip tone={RISK_TONE[preview.risk.level]}>{w(preview.risk.level === 'low' ? 'riskLow' : preview.risk.level === 'medium' ? 'riskMedium' : 'riskHigh')}</Chip>
        <span><Txt>{preview.risk.why[lang]}</Txt></span>
      </div>
    </Block>
  )
}

function CardsBlock({ preview }: { preview: Preview }) {
  const w = useCmdWords()
  return (
    <Block title={w('cardsN', { n: preview.cards.length })}>
      <div className={css.pvList}>
        <FoldList items={preview.cards} first={4} render={(card) => (
          <div className={css.pvCard}>
            {card.severity && <SeverityGlyph severity={card.severity as Severity} word={false} />}
            <span className={css.pvCardMain}><span className={css.pvCardTitle}><Txt block>{card.title ?? card.id}</Txt></span><Id value={card.id} className={css.pvMuted} /></span>
          </div>
        )} />
      </div>
    </Block>
  )
}

/** The cards left out and why, the files it may touch, and its batches. */
function PreviewLists({ preview }: { preview: Preview }) {
  const w = useCmdWords()
  const { lang } = usePrefs()
  return (
    <>
      {preview.left_out.length > 0 && (
        <Block title={w('leftOutN', { n: preview.left_out.length })}>
          <ul className={css.plain}>{preview.left_out.slice(0, 8).map((row) => <li key={row.id}><Id value={row.id} /> · <Txt>{lang === 'ar' && row.why_ar ? row.why_ar : row.why}</Txt></li>)}</ul>
        </Block>
      )}
      {preview.files.length > 0 && (
        <Block title={w('filesN', { n: preview.files.length })}>
          <div className={css.pvList}><FoldList items={preview.files} first={5} render={(file) => <div className={css.pvFile}><Id value={file} /></div>} /></div>
        </Block>
      )}
      {preview.batches.length > 0 && (
        <Block title={w('batchesN', { n: preview.batches.length })}>
          <ol className={css.plain}>{preview.batches.map((b) => <li key={b.number}>{w('batchCards', { n: b.number, c: b.cards.length })}</li>)}</ol>
        </Block>
      )}
    </>
  )
}

/** The assistant that will do it (or the request to hand to one), and the others with their state. */
function AssistantBlock({ preview, request }: { preview: Preview; request: CommandRequest }) {
  const w = useCmdWords()
  const { lang } = usePrefs()
  return (
    <Block title={w('assistant')}>
      {preview.assistant ? (
        <p className={css.pvText}><strong>{preview.assistant.name}</strong>{preview.assistant.version ? <> · <Id value={preview.assistant.version} /></> : null} · {preview.assistant.logged_in ? w('ready') : w('notLoggedIn')}</p>
      ) : (
        <div className={css.handoff}>
          <p>{w('handoffLead')}</p>
          <CopyRequestButton request={requestText(request, preview)[lang]} label={w('copyRequest')} block />
        </div>
      )}
      {(preview.assistants ?? []).filter((a) => a.id !== preview.assistant?.id).map((a) => (
        <p key={a.id} className={css.pvMuted}>{a.name} · {!a.installed ? w('notInstalled') : !a.logged_in ? w('notLoggedIn') : w('ready')}</p>
      ))}
    </Block>
  )
}

type Action = ReturnType<typeof actionOf>
type Words = ReturnType<typeof useCmdWords>
type Lang = ReturnType<typeof usePrefs>['lang']
type Inputs = Record<string, unknown>
/** What the person chose around the request: the assistant, the place of a Fix, and a Fix's own option. */
interface Asked { assistant: string | null; place: WhereChoice; verbInputs?: { auto_accept: boolean }; inputs?: Inputs; check?: CheckChoice }

/** The form's first values: the cards the person selected, then the inputs the request carries. */
function startValues(request: CommandRequest | null | undefined, action: Action | undefined, fields: Field[]): Record<string, string | boolean> {
  const start: Record<string, string | boolean> = {}
  if (action && request?.selection?.cards && fields.some(([name]) => name === 'cards')) start.cards = request.selection.cards.join('\n')
  if (action && request?.selection?.cards?.length === 1 && fields.some(([name]) => name === 'card')) start.card = request.selection.cards[0]
  return { ...start, ...Object.fromEntries(Object.entries(request?.inputs ?? {}).map(([k, v]) => [k, typeof v === 'boolean' ? v : Array.isArray(v) ? v.join('\n') : String(v)])) }
}

/** An action asks for its inputs first; a verb never does, nor a check, whose choices are the person's words (CheckOptions). */
const formNeeded = (action: Action | undefined, fields: Field[], request: CommandRequest | null | undefined) =>
  Boolean(action && fields.length && !request?.verb && action.id !== 'audit')

/** Fix only: the person's choice to accept the batch by itself when its checks pass; previewed again when it changes,
 * since the confirmation is bound to it. */
const verbInputsOf = (request: CommandRequest | null | undefined, autoAccept: boolean) => (request?.verb === 'fix' && autoAccept ? { auto_accept: true } : undefined)

/** What the preview is asked: a verb on the selection (a Fix with its place), or an action with its inputs. */
function previewRequest(request: CommandRequest, a: Asked): PreviewBody {
  return request.verb
    ? { verb: request.verb, selection: request.selection ?? undefined, assistant: a.assistant ?? undefined, where: request.verb === 'fix' ? a.place : undefined, inputs: a.verbInputs }
    : { inputs: a.inputs, assistant: a.assistant ?? undefined }
}

/** What starts the run, as the preview showed it. */
function startRequest(request: CommandRequest, preview: Preview, a: Asked): StartBody {
  return { action: request.verb ?? request.action ?? '', verb: request.verb, selection: (request.selection ?? undefined) as Selection | undefined,
    // The assistant the preview showed, never the server's own pick at start time (it may differ a minute later)
    inputs: (request.verb ? a.verbInputs : a.inputs) ?? undefined, assistant: a.assistant ?? preview.assistant?.id ?? undefined, confirm: preview.confirm?.token ?? null,
    // The place the preview showed, its base commit pinned: a branch that moved since is refused, never built on
    where: preview.where?.base ? { ...a.place, base: preview.where.base.branch, base_commit: preview.where.base.commit,
      deliver_as: preview.where.deliver_as ?? undefined, merge_into: preview.where.merge_into ?? undefined } : undefined }
}

function sheetTitle(request: CommandRequest, action: Action | undefined, preview: Preview | null, w: Words, lang: Lang): string {
  return request.verb
    ? `${verbOf(request.verb).label[lang]} · ${w('cardsCount', { n: request.selection?.cards?.length ?? preview?.cards.length ?? 0 })}`
    : action?.label[lang] ?? request.action ?? ''
}

/** The start button's words, and whether it is locked: no preview yet, busy, not understood, no card, or a place problem. */
function confirmOf(c: { request: CommandRequest; action: Action | undefined; preview: Preview | null; busy: boolean; understood: boolean; w: Words; lang: Lang }) {
  const { request, preview, w, lang } = c
  const n = request.verb ? preview?.cards.length ?? request.selection?.cards?.length ?? 0 : 0
  const label = request.verb ? w('startVerb', { verb: verbOf(request.verb).label[lang], n }) : w('startAction', { label: c.action?.label[lang] ?? '' })
  const blocked = !preview || c.busy || (preview.irreversible && !c.understood) || (request.verb && preview.cards.length === 0) || Boolean(preview.where?.problem)
  return { label, blocked: Boolean(blocked) }
}

/** The preview of what the person chose, asked again whenever the choice changes; a failure goes to `problem`. */
function usePreview(c: { request: CommandRequest | null | undefined; asked: boolean; inputsOf: () => Inputs | null; a: Asked; autoAccept: boolean;
  setPreview: (preview: Preview | null) => void; setProblem: (problem: string | null) => void }) {
  const actions = useActions()
  const { request, asked, a } = c
  useEffect(() => {
    if (!request || !asked || !actions.client) return
    let on = true
    const inputs = request.verb ? undefined : c.inputsOf()
    if (inputs === null) return
    c.setPreview(null); c.setProblem(null)
    actions.client.preview(request.verb ?? request.action ?? '', previewRequest(request, { ...a, inputs })).then((next) => { if (on) c.setPreview(next) },
      (error) => { if (on) c.setProblem(error instanceof ActionError ? error.message : String(error)) })
    return () => { on = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [request, asked, actions.client, a.assistant, a.place, c.autoAccept, JSON.stringify(a.check)])
}

/** Starting the run the preview showed: the run page (or the live check) opens; a branch that moved since asks for the
 * preview again. */
function useStart(c: { request: CommandRequest | null | undefined; preview: Preview | null; inputsOf: () => Inputs | null; a: Asked; setBusy: (busy: boolean) => void;
  setMoved: (moved: boolean) => void; setPlace: Dispatch<SetStateAction<WhereChoice>>; setProblem: (problem: string | null) => void }) {
  const command = useCommand()
  const actions = useActions()
  const navigate = useNavigate()
  const toast = useToast()
  const w = useCmdWords()
  const { lang } = usePrefs()
  return async () => {
    const { request, preview } = c
    if (!actions.client || !preview || !request) return
    c.setBusy(true)
    try {
      const inputs = request.verb ? undefined : c.inputsOf()
      if (inputs === null) { c.setBusy(false); return }
      const run = await actions.client.start(startRequest(request, preview, { ...c.a, inputs }))
      command.close()
      if (request.verb) command.clear()
      toast(run.state === 'queued' && run.position ? w('queuedToast', { label: run.label[lang] }) : w('started', { label: run.label[lang] }))
      void actions.refresh()
      navigate(run.action === 'audit' ? { to: '/checks', search: { flow: 'check' } } : { to: `/runs/${encodeURIComponent(run.id)}` })
    } catch (error) {
      c.setBusy(false)
      if (error instanceof ActionError && error.needs === 'preview') { c.setMoved(true); c.setPlace((was) => ({ ...was })); return }
      c.setProblem(error instanceof ActionError ? error.message : String(error))
    }
  }
}

function InputsBlock({ fields, required, values, asked, onChange, onAsk }:
  { fields: Field[]; required: string[]; values: Record<string, string | boolean>; asked: boolean; onChange: (name: string, value: string | boolean) => void; onAsk: () => void }) {
  const w = useCmdWords()
  return (
    <Block title={w('inputs')}>
      <InputsForm fields={fields} required={required} values={values} onChange={onChange} />
      {!asked && <Button variant="secondary" icon="eye" block data-confirm="preview" isDisabled={required.some((name) => !values[name])} onPress={onAsk}>{w('previewIt')}</Button>}
    </Block>
  )
}

/** What the sheet says while it works: the preview loading, a failure, or a branch that moved since. */
function SheetStatus({ asked, preview, problem, moved }: { asked: boolean; preview: Preview | null; problem: string | null; moved: boolean }) {
  const w = useCmdWords()
  return <>
    {asked && !preview && !problem && <StateMessage icon="clock" title={w('loadingPreview')} />}
    {problem && <StateMessage kind="error" title={w(preview ? 'startFailed' : 'previewFailed')} sub={<Txt>{problem}</Txt>} />}
    {moved && <p className={css.pvWarn} role="status">{w('branchMoved')}</p>}
  </>
}

/** The assistant to run it, when more than one is ready. */
function AssistantChoice({ preview, assistant, onChange }: { preview: Preview; assistant: string | null; onChange: (id: string) => void }) {
  const w = useCmdWords()
  const installed = (preview.assistants ?? []).filter((a) => a.installed && a.logged_in)
  if (installed.length < 2) return null
  return <Segmented label={w('assistant')} value={assistant ?? preview.assistant?.id ?? installed[0].id} onChange={onChange} comfortable
    options={installed.map((a) => ({ id: a.id, label: a.name }))} />
}

/** A Fix's choice to accept the batch by itself, and the second "I understand" for what cannot be undone. */
function Checks({ fix, autoAccept, onAutoAccept, irreversible, understood, onUnderstood }:
  { fix: boolean; autoAccept: boolean; onAutoAccept: () => void; irreversible: boolean; understood: boolean; onUnderstood: () => void }) {
  const w = useCmdWords()
  return <>
    {fix && (
      <div className={css.check} data-confirm="auto-accept">
        <SelectBox checked={autoAccept} label={w('autoAccept')} onToggle={onAutoAccept} />
        <span>{w('autoAccept')}<span className={css.hint}>{w('autoAcceptHint')}</span></span>
      </div>
    )}
    {irreversible && (
      <div className={css.check}>
        <SelectBox checked={understood} label={w('understand')} onToggle={onUnderstood} />
        <span>{w('understand')}</span>
      </div>
    )}
  </>
}

export function PreviewSheet() {
  const command = useCommand()
  const actions = useActions()
  const w = useCmdWords()
  const { lang } = usePrefs()
  const request = command.request
  const action = request?.action ? actionOf(request.action) : undefined
  const fields = useMemo<Field[]>(() => (action ? personInputs(action) : []), [action])
  const required = action?.inputs.required ?? []
  const needsForm = formNeeded(action, fields, request)
  const [values, setValues] = useState<Record<string, string | boolean>>({})
  const [preview, setPreview] = useState<Preview | null>(null)
  const [problem, setProblem] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [understood, setUnderstood] = useState(false)
  const [assistant, setAssistant] = useState<string | null>(null)
  const [asked, setAsked] = useState(false)
  const [place, setPlace] = useState<WhereChoice>({})
  const [moved, setMoved] = useState(false)
  const [autoAccept, setAutoAccept] = useState(false)
  const [check, setCheck] = useState<CheckChoice | undefined>(undefined)
  const [offer, setOffer] = useState<CheckOffer | undefined>(undefined)
  const a: Asked = { assistant, place, verbInputs: verbInputsOf(request, autoAccept), check }

  // A new request starts clean; one with no inputs to fill is previewed at once
  useEffect(() => {
    setPreview(null); setProblem(null); setUnderstood(false); setAssistant(null); setBusy(false); setPlace({}); setMoved(false); setAutoAccept(false); setCheck(undefined); setOffer(undefined)
    setValues(startValues(request, action, fields))
    setAsked(Boolean(request) && !needsForm)
  }, [request, action, fields, needsForm])

  const inputsOf = (): Inputs | null => {
    try { return { ...parse(fields, values), ...(check ? checkInputs(check) : {}), ...freshOf(request, values) } } catch { setProblem('JSON'); return null }
  }
  // what a check offers stays while its preview is asked again; the kept mode is the first choice, never the person's
  useEffect(() => {
    if (!preview?.check || offer) return
    setOffer(preview.check); setCheck({ paths: ['complete'], mode: preview.check.mode })
  }, [preview, offer])
  usePreview({ request, asked, inputsOf, a, autoAccept, setPreview, setProblem })
  const start = useStart({ request, preview, inputsOf, a, setBusy, setMoved, setPlace, setProblem })

  if (!request) return null
  const confirm = confirmOf({ request, action, preview, busy, understood, w, lang })
  return (
    <Sheet isOpen onOpenChange={(open) => { if (!open) command.close() }} title={sheetTitle(request, action, preview, w, lang)}>
      {actions.mode === 'snapshot' ? <SnapshotBody request={request} /> : (
        <>
          {needsForm && <InputsBlock fields={fields} required={required} values={values} asked={asked} onAsk={() => setAsked(true)}
            onChange={(name, value) => { setValues((was) => ({ ...was, [name]: value })); setAsked(false) }} />}
          {offer && check && <Block title={w('checkTitle')}><CheckOptions offer={offer} choice={check} onChange={setCheck} /></Block>}
          <SheetStatus asked={asked} preview={preview} problem={problem} moved={moved} />
          {preview && <PreviewBody preview={preview} request={request} onWhere={(next) => { setMoved(false); setPlace((was) => ({ ...was, ...next })) }} />}
          {preview && <AssistantChoice preview={preview} assistant={assistant} onChange={setAssistant} />}
          <Checks fix={request.verb === 'fix'} autoAccept={autoAccept} onAutoAccept={() => setAutoAccept(!autoAccept)}
            irreversible={Boolean(preview?.irreversible)} understood={understood} onUnderstood={() => setUnderstood(!understood)} />
          <div className={css.pvFoot}>
            <Button variant="secondary" onPress={() => command.close()}>{w('cancel')}</Button>
            <Button variant="primary" icon="play" busy={busy} isDisabled={confirm.blocked} onPress={start} className={css.pvGo} data-confirm="start">{confirm.label}</Button>
          </div>
        </>
      )}
    </Sheet>
  )
}
