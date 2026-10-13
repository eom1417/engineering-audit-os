// The pipeline as a linear list, in EAOS's reading order (layer, then order): the phone's default and the screen
// reader's view of the map. Each stage says what it takes and gives, its tools, a router's branches, its failure
// routes, and marks what is hidden, not followed, or changed by the view.
import { useMemo, useState } from 'react'
import { Button as AriaButton } from 'react-aria-components'
import { Button } from '../../components/Button'
import { OperationChip } from '../../components/Chip'
import { stageTitle } from './names'
import { usePrefs } from '../../i18n/prefs'
import { Id } from '../../i18n/text'
import { ordered, where, type Scope, type View } from './model'
import { RELATION } from './Inspector'
import type { Lit } from './Flowchart'
import { KIND_WORD, usePipelineWords } from './words'
import css from './panels.module.css'

type Step = ReturnType<typeof ordered>[number]

/** {stage: the numbers of the gap rows about it}: a hidden finding's stages, a router's stage, or the stage itself. */
function gapNumbers(scope: Scope): Map<string, number[]> {
  const out = new Map<string, number[]>()
  scope.gap.forEach((g, i) => {
    const h = scope.hidden.find((x) => x.id === g.subject)
    const r = scope.routers.find((x) => x.id === g.subject)
    const ids = h ? h.stages : r ? [r.stage] : [g.subject]
    for (const id of ids) out.set(id, [...(out.get(id) ?? []), i + 1])
  })
  return out
}

/** The stage's name (the ideal's own name in that view), its kind, and its gap numbers. */
function StepTitle({ s, scope, view, nos }: { s: Step; scope: Scope; view: View; nos?: number[] }) {
  const w = usePipelineWords()
  const { lang } = usePrefs()
  const ideal = scope.ideal.get(s.id)
  return (
    <span className={css.stepTitle}>
      <span>{view === 'ideal' && ideal?.label && ideal.label !== s.label ? ideal.label : stageTitle(s, lang)}</span>
      <span className={css.muted}>{w(KIND_WORD[s.kind])}</span>
      {nos && <bdi dir="ltr" className={css.gapNos}>{nos.join(', ')}</bdi>}
    </span>
  )
}

/** A label and the first `first` names, comma separated; nothing when there are none. */
function IdRow({ label, names, first }: { label: string; names: string[]; first: number }) {
  if (!names.length) return null
  return <span>{label}: {names.slice(0, first).map((name, i) => <span key={name}>{i > 0 && ', '}<Id value={name} /></span>)}</span>
}

const nameOf = (port: { name: string }) => port.name

/** What the stage takes and gives, and its tools, the first few of each. */
function StepIo({ s }: { s: Step }) {
  const w = usePipelineWords()
  return (
    <span className={css.stepIo}>
      <IdRow label={w('takes')} names={s.inputs.map(nameOf)} first={3} />
      <IdRow label={w('gives')} names={s.outputs.map(nameOf)} first={3} />
      <IdRow label={w('tools')} names={s.tools} first={4} />
    </span>
  )
}

/** A router's switch and its first six branches. */
function StepRouter({ scope, id }: { scope: Scope; id: string }) {
  const w = usePipelineWords()
  const router = scope.routerOf.get(id)
  if (!router) return null
  return (
    <span className={css.stepIo}>
      {w('routesOn')} <Id value={router.on} />: {router.branches.slice(0, 6).map((b, i) => <span key={i}>{i > 0 && ' · '}<Id value={b.condition} /></span>)}{router.branches.length > 6 && ' …'}
    </span>
  )
}

/** Where a stage's failures go, what is hidden in it, and the calls the trace could not follow from it. */
function StepTags({ scope, id }: { scope: Scope; id: string }) {
  const w = usePipelineWords()
  const failures = scope.errors.filter((e) => e.from === id)
  const hidden = scope.hidden.filter((h) => h.stages.includes(id))
  const lost = scope.unresolved.filter((u) => u.stage === id)
  if (!failures.length && !hidden.length && !lost.length) return null
  return (
    <span className={css.stepTags}>
      {failures.map((e) => <span key={e.id} className={css.tagErr}>{w.known('err_', e.kind)} → <Id value={e.to} /></span>)}
      {hidden.map((h) => <span key={h.id} className={css.tagHidden}>{w.known('hidden_', h.kind)}</span>)}
      {lost.map((u) => <span key={u.id} className={css.tagGap}>? <Id value={u.call} /></span>)}
    </span>
  )
}

interface StepRowProps { s: Step; head: boolean; scope: Scope; view: View; nos?: number[]; selected?: string; onSelect: (id: string) => void }

/** One stage of the list: a button that selects it, under its layer's head when it opens a layer. */
function StepRow({ s, head, scope, view, nos, selected, onSelect }: StepRowProps) {
  const w = usePipelineWords()
  const op = view !== 'current' ? scope.ideal.get(s.id)?.op : undefined
  return (
    <li className={css.stepItem} data-layer-start={head ? '' : undefined}>
      {head && <span className={css.layerHead}>{w('layerN', { n: s.layer + 1 })}</span>}
      <AriaButton className={[css.stepBtn, s.id === selected && css.stepOn].filter(Boolean).join(' ')} onPress={() => onSelect(s.id)} aria-pressed={s.id === selected}>
        <span className={[css.glyph, css[`g_${s.kind}`]].filter(Boolean).join(' ')} aria-hidden="true" />
        <span className={css.stepMain}>
          <StepTitle s={s} scope={scope} view={view} nos={nos} />
          <StepIo s={s} />
          <StepRouter scope={scope} id={s.id} />
          <StepTags scope={scope} id={s.id} />
          <span className={css.stepWhere}><Id value={where(s.entry) ?? ''} keep={2} /></span>
        </span>
        {op && op !== 'retain' && <OperationChip relation={RELATION[op]} />}
      </AriaButton>
    </li>
  )
}

export function StepList({ scope, view, selected, onSelect, lit, first = 40 }:
  { scope: Scope; view: View; selected?: string; onSelect: (id: string) => void; lit?: Lit | null; first?: number }) {
  const w = usePipelineWords()
  const [all, setAll] = useState(false)
  const rows = useMemo(() => {
    const list = ordered(scope.stages)
    return lit ? list.filter((s) => lit.stages.has(s.id)) : list
  }, [scope.stages, lit])
  const gapNo = useMemo(() => gapNumbers(scope), [scope])
  const shown = all ? rows : rows.slice(0, first)
  return (
    <>
      <ol className={css.steps}>
        {shown.map((s, i) => (
          <StepRow key={s.id} s={s} head={i === 0 || shown[i - 1].layer !== s.layer} scope={scope} view={view}
            nos={view === 'gap' ? gapNo.get(s.id) : undefined} selected={selected} onSelect={onSelect} />
        ))}
      </ol>
      {rows.length > shown.length && <Button variant="ghost" onPress={() => setAll(true)}>{w('showAll', { n: rows.length })}</Button>}
    </>
  )
}
