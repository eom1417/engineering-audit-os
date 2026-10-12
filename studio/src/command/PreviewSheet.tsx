// The preview sheet: before anything runs, what will happen, the cards (and the ones left out, with why), the files,
// the batches, the time, the risk, what happens on failure and which assistant runs it; then an explicit confirm,
// with a second "I understand" for what cannot be undone. An action with inputs asks for them first. In a snapshot
// (opened from a file) it explains how to start the live Studio, and offers the request to copy to an assistant.
import { useNavigate } from '@tanstack/react-router'
import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { Input, Label, TextArea, TextField } from 'react-aria-components'
import { Button, CopyRequestButton, copyText } from '../components/Button'
import { Chip, SeverityGlyph, type Tone } from '../components/Chip'
import { Segmented } from '../components/Controls'
import { FoldList, StateMessage } from '../components/Panel'
import { Sheet, SheetSub } from '../components/Sheet'
import { useToast } from '../components/Toast'
import { actionOf, personInputs, SNAPSHOT, verbOf } from '../data/actions/contract'
import { useActions } from '../data/actions/store'
import { ActionError, type Bi, type FixWhere, type JsonSchema, type Preview, type Selection, type WhereChoice } from '../data/actions/types'
import type { Severity } from '../data/types'
import { usePrefs } from '../i18n/prefs'
import { Id, N, Txt } from '../i18n/text'
import { useCommand, type CommandRequest } from './command'
import { SelectBox } from './SelectBox'
import { useCmdWords } from './words'
import css from './command.module.css'

const RISK_TONE: Record<Preview['risk']['level'], Tone> = { low: 'good', medium: 'warning', high: 'critical' }

/** The request a person pastes to their assistant, in both languages: the verb or action, the cards, the EAOS way. */
export function requestText(request: CommandRequest, preview?: Preview | null): Bi {
  if (preview?.handoff.request) return preview.handoff.request
  const cards = request.selection?.cards?.join(', ') ?? (request.selection?.step ? `step ${request.selection.step}` : request.selection?.group ? `${request.selection.group.by} ${request.selection.group.value}` : '')
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
      <dl className={css.facts}>
        {preview.verb && <div><dt>{w('cardsN', { n: preview.cards.length })}</dt><dd><N value={preview.cards.length} /></dd></div>}
        {preview.files.length > 0 && <div><dt>{w('filesN', { n: preview.files.length })}</dt><dd><N value={preview.files.length} /></dd></div>}
        {preview.batches.length > 0 && <div><dt>{w('batchesN', { n: preview.batches.length })}</dt><dd><N value={preview.batches.length} /></dd></div>}
        <div><dt>{w('time')}</dt><dd className="num">{minutes(preview, w)}</dd></div>
      </dl>
      {preview.where && <WhereBlock where={preview.where} onChange={onWhere} />}
      <Block title={w('risk')}>
        <div className={css.risk}>
          <Chip tone={RISK_TONE[preview.risk.level]}>{w(preview.risk.level === 'low' ? 'riskLow' : preview.risk.level === 'medium' ? 'riskMedium' : 'riskHigh')}</Chip>
          <span><Txt>{preview.risk.why[lang]}</Txt></span>
        </div>
      </Block>
      <Block title={w('onFailure')}><p className={css.pvText}><Txt>{preview.on_failure[lang]}</Txt></p></Block>
      {preview.cards.length > 0 && (
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
      )}
      {preview.left_out.length > 0 && (
        <Block title={w('leftOutN', { n: preview.left_out.length })}>
          <ul className={css.plain}>{preview.left_out.slice(0, 8).map((row) => <li key={row.id}><Id value={row.id} /> · <Txt>{row.why}</Txt></li>)}</ul>
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
      {(preview.assistant || preview.handoff.available) && (
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
      )}
      {preview.needs_consent && <p className={css.pvNote}>{w('consentLead')}</p>}
      {preview.irreversible && <p className={css.pvWarn} role="note">{w('irreversibleLead')}</p>}
    </div>
  )
}

export function PreviewSheet() {
  const command = useCommand()
  const actions = useActions()
  const navigate = useNavigate()
  const toast = useToast()
  const w = useCmdWords()
  const { lang } = usePrefs()
  const request = command.request
  const action = request?.action ? actionOf(request.action) : undefined
  const fields = useMemo<Field[]>(() => (action ? personInputs(action) : []), [action])
  const required = action?.inputs.required ?? []
  const needsForm = Boolean(action && fields.length && !request?.verb)
  const [values, setValues] = useState<Record<string, string | boolean>>({})
  const [preview, setPreview] = useState<Preview | null>(null)
  const [problem, setProblem] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [understood, setUnderstood] = useState(false)
  const [assistant, setAssistant] = useState<string | null>(null)
  const [asked, setAsked] = useState(false)
  const [place, setPlace] = useState<WhereChoice>({})
  const [moved, setMoved] = useState(false)
  // Fix only: the person's choice to accept the batch by itself when its checks pass; previewed again when it changes,
  // since the confirmation is bound to it
  const [autoAccept, setAutoAccept] = useState(false)
  const verbInputs = request?.verb === 'fix' && autoAccept ? { auto_accept: true } : undefined

  // A new request starts clean; one with no inputs to fill is previewed at once
  useEffect(() => {
    setPreview(null); setProblem(null); setUnderstood(false); setAssistant(null); setBusy(false); setPlace({}); setMoved(false); setAutoAccept(false)
    const start: Record<string, string | boolean> = {}
    if (action && request?.selection?.cards && fields.some(([name]) => name === 'cards')) start.cards = request.selection.cards.join('\n')
    if (action && request?.selection?.cards?.length === 1 && fields.some(([name]) => name === 'card')) start.card = request.selection.cards[0]
    setValues({ ...start, ...Object.fromEntries(Object.entries(request?.inputs ?? {}).map(([k, v]) => [k, typeof v === 'boolean' ? v : Array.isArray(v) ? v.join('\n') : String(v)])) })
    setAsked(Boolean(request) && !needsForm)
  }, [request, action, fields, needsForm])

  const inputsOf = (): Record<string, unknown> | null => {
    try { return parse(fields, values) } catch { setProblem('JSON'); return null }
  }

  useEffect(() => {
    if (!request || !asked || !actions.client) return
    let on = true
    const inputs = request.verb ? undefined : inputsOf()
    if (inputs === null) return
    const id = request.verb ?? request.action ?? ''
    const body = request.verb ? { verb: request.verb, selection: request.selection ?? undefined, assistant: assistant ?? undefined, where: request.verb === 'fix' ? place : undefined, inputs: verbInputs } : { inputs, assistant: assistant ?? undefined }
    setPreview(null); setProblem(null)
    actions.client.preview(id, body).then((next) => { if (on) setPreview(next) },
      (error) => { if (on) setProblem(error instanceof ActionError ? error.message : String(error)) })
    return () => { on = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [request, asked, actions.client, assistant, place, autoAccept])

  if (!request) return null
  const title = request.verb
    ? `${verbOf(request.verb).label[lang]} · ${w('cardsCount', { n: request.selection?.cards?.length ?? preview?.cards.length ?? 0 })}`
    : action?.label[lang] ?? request.action ?? ''
  const close = (open: boolean) => { if (!open) command.close() }

  const start = async () => {
    if (!actions.client || !preview) return
    setBusy(true)
    try {
      const inputs = request.verb ? undefined : inputsOf()
      if (inputs === null) { setBusy(false); return }
      const run = await actions.client.start({ action: request.verb ?? request.action ?? '', verb: request.verb, selection: (request.selection ?? undefined) as Selection | undefined,
        // The assistant the preview showed, never the server's own pick at start time (it may differ a minute later)
        inputs: (request.verb ? verbInputs : inputs) ?? undefined, assistant: assistant ?? preview.assistant?.id ?? undefined, confirm: preview.confirm?.token ?? null,
        // The place the preview showed, its base commit pinned: a branch that moved since is refused, never built on
        where: preview.where?.base ? { ...place, base: preview.where.base.branch, base_commit: preview.where.base.commit,
          deliver_as: preview.where.deliver_as ?? undefined, merge_into: preview.where.merge_into ?? undefined } : undefined })
      command.close()
      if (request.verb) command.clear()
      toast(run.state === 'queued' && run.position ? w('queuedToast', { label: run.label[lang] }) : w('started', { label: run.label[lang] }))
      void actions.refresh()
      navigate(run.action === 'audit' ? { to: '/scan', search: { flow: 'check' } } : { to: `/runs/${encodeURIComponent(run.id)}` })
    } catch (error) {
      setBusy(false)
      if (error instanceof ActionError && error.needs === 'preview') { setMoved(true); setPlace((was) => ({ ...was })); return }
      setProblem(error instanceof ActionError ? error.message : String(error))
    }
  }

  const installed = (preview?.assistants ?? []).filter((a) => a.installed && a.logged_in)
  const n = request.verb ? preview?.cards.length ?? request.selection?.cards?.length ?? 0 : 0
  const confirmLabel = request.verb ? w('startVerb', { verb: verbOf(request.verb).label[lang], n }) : w('startAction', { label: action?.label[lang] ?? '' })
  const blocked = !preview || busy || (preview.irreversible && !understood) || (request.verb && preview.cards.length === 0) || Boolean(preview.where?.problem)

  return (
    <Sheet isOpen onOpenChange={close} title={title}>
      {actions.mode === 'snapshot' ? <SnapshotBody request={request} /> : (
        <>
          {needsForm && (
            <Block title={w('inputs')}>
              <InputsForm fields={fields} required={required} values={values} onChange={(name, value) => { setValues((was) => ({ ...was, [name]: value })); setAsked(false) }} />
              {!asked && <Button variant="secondary" icon="eye" block data-confirm="preview" isDisabled={required.some((name) => !values[name])} onPress={() => setAsked(true)}>{w('previewIt')}</Button>}
            </Block>
          )}
          {asked && !preview && !problem && <StateMessage icon="clock" title={w('loadingPreview')} />}
          {problem && <StateMessage kind="error" title={w(preview ? 'startFailed' : 'previewFailed')} sub={<Txt>{problem}</Txt>} />}
          {moved && <p className={css.pvWarn} role="status">{w('branchMoved')}</p>}
          {preview && <PreviewBody preview={preview} request={request} onWhere={(next) => { setMoved(false); setPlace((was) => ({ ...was, ...next })) }} />}
          {preview && installed.length > 1 && (
            <Segmented label={w('assistant')} value={assistant ?? preview.assistant?.id ?? installed[0].id} onChange={setAssistant} comfortable
              options={installed.map((a) => ({ id: a.id, label: a.name }))} />
          )}
          {request.verb === 'fix' && (
            <div className={css.check} data-confirm="auto-accept">
              <SelectBox checked={autoAccept} label={w('autoAccept')} onToggle={() => setAutoAccept(!autoAccept)} />
              <span>{w('autoAccept')}<span className={css.hint}>{w('autoAcceptHint')}</span></span>
            </div>
          )}
          {preview?.irreversible && (
            <div className={css.check}>
              <SelectBox checked={understood} label={w('understand')} onToggle={() => setUnderstood(!understood)} />
              <span>{w('understand')}</span>
            </div>
          )}
          <div className={css.pvFoot}>
            <Button variant="secondary" onPress={() => command.close()}>{w('cancel')}</Button>
            <Button variant="primary" icon="play" busy={busy} isDisabled={Boolean(blocked)} onPress={start} className={css.pvGo} data-confirm="start">{confirmLabel}</Button>
          </div>
        </>
      )}
    </Sheet>
  )
}
