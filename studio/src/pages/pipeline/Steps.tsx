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

export function StepList({ scope, view, selected, onSelect, lit, first = 40 }:
  { scope: Scope; view: View; selected?: string; onSelect: (id: string) => void; lit?: Lit | null; first?: number }) {
  const w = usePipelineWords()
  const { lang } = usePrefs()
  const [all, setAll] = useState(false)
  const rows = useMemo(() => {
    const list = ordered(scope.stages)
    return lit ? list.filter((s) => lit.stages.has(s.id)) : list
  }, [scope.stages, lit])
  const gapNo = useMemo(() => {
    const out = new Map<string, number[]>()
    scope.gap.forEach((g, i) => {
      const h = scope.hidden.find((x) => x.id === g.subject)
      const r = scope.routers.find((x) => x.id === g.subject)
      const ids = h ? h.stages : r ? [r.stage] : [g.subject]
      for (const id of ids) out.set(id, [...(out.get(id) ?? []), i + 1])
    })
    return out
  }, [scope])
  const shown = all ? rows : rows.slice(0, first)
  let layer = -1
  return (
    <>
      <ol className={css.steps}>
        {shown.map((s) => {
          const head = s.layer !== layer
          layer = s.layer
          const router = scope.routerOf.get(s.id)
          const op = view !== 'current' ? scope.ideal.get(s.id)?.op : undefined
          const nos = view === 'gap' ? gapNo.get(s.id) : undefined
          const failures = scope.errors.filter((e) => e.from === s.id)
          const hidden = scope.hidden.filter((h) => h.stages.includes(s.id))
          const lost = scope.unresolved.filter((u) => u.stage === s.id)
          return (
            <li key={s.id} className={css.stepItem} data-layer-start={head ? '' : undefined}>
              {head && <span className={css.layerHead}>{w('layerN', { n: s.layer + 1 })}</span>}
              <AriaButton className={[css.stepBtn, s.id === selected && css.stepOn].filter(Boolean).join(' ')} onPress={() => onSelect(s.id)} aria-pressed={s.id === selected}>
                <span className={[css.glyph, css[`g_${s.kind}`]].filter(Boolean).join(' ')} aria-hidden="true" />
                <span className={css.stepMain}>
                  <span className={css.stepTitle}>
                    <span>{view === 'ideal' && scope.ideal.get(s.id)?.label && scope.ideal.get(s.id)?.label !== s.label ? scope.ideal.get(s.id)!.label : stageTitle(s, lang)}</span>
                    <span className={css.muted}>{w(KIND_WORD[s.kind])}</span>
                    {nos && <bdi dir="ltr" className={css.gapNos}>{nos.join(', ')}</bdi>}
                  </span>
                  <span className={css.stepIo}>
                    {s.inputs.length > 0 && <span>{w('takes')}: {s.inputs.slice(0, 3).map((p, i) => <span key={p.name}>{i > 0 && ', '}<Id value={p.name} /></span>)}</span>}
                    {s.outputs.length > 0 && <span>{w('gives')}: {s.outputs.slice(0, 3).map((p, i) => <span key={p.name}>{i > 0 && ', '}<Id value={p.name} /></span>)}</span>}
                    {s.tools.length > 0 && <span>{w('tools')}: {s.tools.slice(0, 4).map((t, i) => <span key={t}>{i > 0 && ', '}<Id value={t} /></span>)}</span>}
                  </span>
                  {router && (
                    <span className={css.stepIo}>
                      {w('routesOn')} <Id value={router.on} />: {router.branches.slice(0, 6).map((b, i) => <span key={i}>{i > 0 && ' · '}<Id value={b.condition} /></span>)}{router.branches.length > 6 && ' …'}
                    </span>
                  )}
                  {(failures.length > 0 || hidden.length > 0 || lost.length > 0) && (
                    <span className={css.stepTags}>
                      {failures.map((e) => <span key={e.id} className={css.tagErr}>{w.known('err_', e.kind)} → <Id value={e.to} /></span>)}
                      {hidden.map((h) => <span key={h.id} className={css.tagHidden}>{w.known('hidden_', h.kind)}</span>)}
                      {lost.map((u) => <span key={u.id} className={css.tagGap}>? <Id value={u.call} /></span>)}
                    </span>
                  )}
                  <span className={css.stepWhere}><Id value={where(s.entry) ?? ''} keep={2} /></span>
                </span>
                {op && op !== 'retain' && <OperationChip relation={RELATION[op]} />}
              </AriaButton>
            </li>
          )
        })}
      </ol>
      {rows.length > shown.length && <Button variant="ghost" onPress={() => setAll(true)}>{w('showAll', { n: rows.length })}</Button>}
    </>
  )
}
