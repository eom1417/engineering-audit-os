// The pieces around the data map: the seven tiers with what each knows (the gaps counted), the chain of one write,
// a store's inspector (writers, readers, endpoints, keys, the target) and the steps view, the map's linear twin for
// the phone and for screen readers.
import { Button as AriaButton } from 'react-aria-components'
import { Chip } from '../../components/Chip'
import { FoldList, Section } from '../../components/Panel'
import { TIERS, type DataPaths, type Endpoint, type Site, type Store, type Tier, type WritePath } from '../../data/dataMap'
import { Id, N } from '../../i18n/text'
import { CHANGE_TONE, pathsOf, ranked, tierCounts, type Mode } from './model'
import { useDataWords, type DataWord } from './words'
import css from './Data.module.css'

/** The seven links of every write, each with how many writes it reaches with evidence; the rest is hatched. */
export function TierStrip({ dp, vertical }: { dp: DataPaths; vertical?: boolean }) {
  const w = useDataWords()
  const total = dp.paths.length
  return (
    <ol className={[css.tiers, vertical && css.tiersV].filter(Boolean).join(' ')} aria-label={w('chain')}>
      {TIERS.map((tier) => {
        const { known } = tierCounts(dp.paths, tier)
        const share = total ? known / total : 0
        const row = dp.tiers.find((t) => t.id === tier)
        const why = row?.gaps.map((g) => `${w(`gap_${g.reason}` as DataWord)} (${w('stepWord', { s: g.step })})`).join(' · ')
        return (
          <li key={tier} className={css.tier} title={why || undefined}>
            <span className={css.tierName}>{w(`tier_${tier}`)}</span>
            <span className={css.tierBar} aria-hidden="true"><span style={{ inlineSize: `${Math.round(share * 100)}%` }} /></span>
            <span className={css.tierN}>{total ? w('knownOf', { k: known, n: total }) : w('noWrites')}</span>
            {vertical && why && <span className={css.tierWhy}>{why}</span>}
          </li>
        )
      })}
    </ol>
  )
}

function SiteRef({ site }: { site: Site }) {
  const w = useDataWords()
  return <span className={css.site}><Id value={site.path} keep={3} />{site.line ? <span className={css.lineNo}>{w('line', { n: site.line })}</span> : null}</span>
}

/** One write as its seven links, in order; a link the records do not reach is a hatched gap with its reason. */
export function Chain({ path, endpoint, steps }: { path: WritePath; endpoint?: Endpoint; steps: Record<string, string> }) {
  const w = useDataWords()
  const value = (tier: Tier) => {
    const step = path.steps[tier]
    if (step.state === 'gap') return <span className={css.gapText}>{w(`gap_${step.reason}` as DataWord)}{steps[step.reason ?? ''] ? ` · ${w('stepWord', { s: steps[step.reason ?? ''] })}` : ''}</span>
    if (step.state === 'direct') return <span className={css.muted}>{w('direct')}</span>
    if (tier === 'key' || tier === 'column') {
      const names = tier === 'key' ? step.keys : step.columns
      return names?.length ? <span className={css.keys}>{names.map((k) => <Id key={k} value={k} className={css.keyChip} />)}{step.partial ? '…' : null}</span> : <span className={css.muted}>—</span>
    }
    if (tier === 'caller') return <SiteRef site={path.site} />
    if (tier === 'endpoint') return <Id value={endpoint?.label ?? path.endpoint} />
    if (tier === 'handler') return <span><Id value={step.handler ?? ''} />{step.path ? <> · <SiteRef site={{ path: step.path, line: step.line ?? null, fact: null }} /></> : null}</span>
    return null
  }
  return (
    <ol className={css.chain}>
      {TIERS.map((tier) => (
        <li key={tier} className={path.steps[tier].state === 'gap' ? css.linkGap : css.link}>
          <span className={css.linkName}>{w(`tier_${tier}`)}</span>
          <span className={css.linkValue}>{value(tier)}</span>
        </li>
      ))}
    </ol>
  )
}

/** {gap reason: the plan step that reaches it}, as the tiers record it. */
export function gapSteps(dp: DataPaths): Record<string, string> {
  return Object.fromEntries(dp.tiers.flatMap((t) => t.gaps.map((g) => [g.reason, g.step])))
}

/** Who writes a store, in words: nobody, one file, several files for different inputs, or one input from several. */
export function ownerWord(store: Store, w: ReturnType<typeof useDataWords>): string {
  if (!store.writers.length) return w('readOnly')
  if (store.multi_writer) return store.kind === 'resource' ? w('multiWriterIn') : w('multiWriter', { n: store.writers.length })
  return store.writers.length === 1 ? w('singleWriter') : w('writtenFrom', { n: store.writers.length })
}

export function ChangeChip({ store }: { store: Store }) {
  const w = useDataWords()
  if (!store.change) return <Chip>{w(store.writers.length ? 'noTarget' : 'ch_none')}</Chip>
  const tone = CHANGE_TONE[store.change]
  return <Chip tone={tone === 'keep' ? 'good' : tone === 'merge' ? 'accent' : 'serious'}>{w(`ch_${store.change}`)}</Chip>
}

function Modules({ title, items }: { title: string; items: string[] }) {
  if (!items.length) return null
  return (
    <Section title={title} count={items.length}>
      <FoldList items={items} first={5} render={(m) => <span className={css.module}><Id value={m} keep={3} /></span>} />
    </Section>
  )
}

/** A store: what it is, where it is declared, who writes and reads it, its endpoints and keys, the target, and the
 * chain of every write into it. */
export function StoreInspector({ dp, store, mode }: { dp: DataPaths; store: Store; mode: Mode }) {
  const w = useDataWords()
  const endpoints = dp.endpoints.filter((e) => e.store === store.id)
  const byId = new Map(endpoints.map((e) => [e.id, e]))
  const paths = pathsOf(dp, store.id)
  const steps = gapSteps(dp)
  return (
    <div className={css.inspect}>
      <div className={css.inspectHead}>
        <span className={css.kindWord}>{w(`kind_${store.kind}`)}</span>
        <h2 className={css.storeName}><Id value={store.name} /></h2>
        <div className={css.chips}>
          <Chip tone={store.multi_writer ? 'serious' : 'neutral'}>{ownerWord(store, w)}</Chip>
          {mode !== 'current' && <ChangeChip store={store} />}
        </div>
      </div>
      <p className={css.declared}>
        {store.declared ? <>{w('declaredAt')} <SiteRef site={store.declared} />{store.declared.rls != null && <> · {w(store.declared.rls ? 'rlsOn' : 'rlsOff')}</>}</> : w('notDeclared')}
      </p>
      {store.target && (
        <Section title={w('inTarget')}>
          <p className={css.targetLine}>
            {store.target.components.length <= 1 && store.writers.length
              ? <>{w('targetOne', { c: '' })}<Id value={store.target.components[0] ?? '—'} /></>
              : store.writers.length ? w('targetMany', { n: store.target.components.length }) : w('readOnly')}
            {store.target.unmapped.length > 0 && <> · {w('targetUnmapped', { n: store.target.unmapped.length })}</>}
          </p>
        </Section>
      )}
      <Modules title={w('writers')} items={store.writers} />
      <Modules title={w('readers')} items={store.readers} />
      <Section title={w('endpoints')} count={endpoints.length}>
        <FoldList items={endpoints} first={4} render={(e) => (
          <div className={css.endpoint}>
            <Id value={e.label} />
            {e.multi_writer && <Chip tone="serious">{w('multiWriter', { n: e.writers.length })}</Chip>}
            {e.keys && <span className={css.keys}>{e.keys.map((k) => <Id key={k} value={k} className={css.keyChip} />)}</span>}
          </div>
        )} />
      </Section>
      {paths.length > 0 && (
        <Section title={w('chain')} count={paths.length}>
          <p className={css.hint}>{w('chainHint')}</p>
          <FoldList items={paths} first={2} render={(p) => <Chain path={p} endpoint={byId.get(p.endpoint)} steps={steps} />} />
        </Section>
      )}
    </div>
  )
}

/** The stores in the order that needs attention first, each opening its chain: the map's linear twin. */
export function StepsList({ dp, mode, focus, onFocus, first = 12 }: { dp: DataPaths; mode: Mode; focus?: string; onFocus: (id: string) => void; first?: number }) {
  const w = useDataWords()
  const order = ranked(dp.stores)
  return (
    <FoldList items={order} first={first} label={w('allStores')} render={(s, i) => (
      <AriaButton className={css.stepRow} onPress={() => onFocus(s.id)} aria-pressed={focus === s.id}>
        <span className={css.stepN}><N value={i + 1} /></span>
        <span className={css.stepMain}>
          <span className={css.stepTitle}><Id value={s.name} /> <span className={css.kindWord}>{w(`kind_${s.kind}`)}</span></span>
          <span className={css.stepSub}>
            {ownerWord(s, w)}
            {s.readers.length > 0 && <> · {w('readers')} <N value={s.readers.length} /></>}
            {mode !== 'current' && s.change && <> · {w(`ch_${s.change}`)}</>}
          </span>
        </span>
        {s.multi_writer && <span className={css.warn} aria-hidden="true">⚠</span>}
      </AriaButton>
    )} />
  )
}
