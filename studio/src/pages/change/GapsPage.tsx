// #/change/gaps?relation=<op>: the gap register (C-experience 3.7) from studio/gaps.json. Desktop: a table (component,
// operation, target, files, closed by its cards, steps, decision); the phone: the same as rows. #/change/gaps/<id>:
// one gap with its target and responsibility, why, the cards that close it, its operations, steps and decision.
import { useParams, useSearch } from '@tanstack/react-router'
import { useMemo, type ReactNode } from 'react'
import { OperationChip } from '../../components/Chip'
import { Go } from '../../components/Go'
import { FoldList, Panel, Props, RowLink, Section, StateMessage } from '../../components/Panel'
import { RELATION_OF, type ChangeOp, type Gap } from '../../data/change'
import type { StudioData } from '../../data/types'
import { usePrefs } from '../../i18n/prefs'
import { Id, N, Txt } from '../../i18n/text'
import { usePageChrome } from '../../shell/chrome'
import { layout as page, MissingBanner, PageTitle, WithData } from '../../shell/Layout'
import { usePhone } from '../SystemMap'
import { byId, cardState, OP_LABEL, opsMix, registerOrder } from './model'
import { ChangeNav, Closure, GapLink, LinkList, NotMeasured, OpLink, StepLink } from './parts'
import { STATE_WORD, useChangeWords } from './words'
import css from './change.module.css'

const PLAN = 'fix'

function Filter({ gaps, chosen }: { gaps: Gap[]; chosen?: ChangeOp }) {
  const w = useChangeWords()
  const { t } = usePrefs()
  return (
    <nav aria-label={w('byOperation')} className={css.filters}>
      <Go to="/change/gaps" className={css.filter} current={!chosen}>{w('allOps', { n: gaps.length })}</Go>
      {opsMix(gaps).map(([op, n]) => (
        <Go key={op} to="/change/gaps" search={{ relation: op }} className={css.filter} current={chosen === op}>
          {w('opCount', { op: t(OP_LABEL[op]), n })}
        </Go>
      ))}
    </nav>
  )
}

function GapTable({ gaps }: { gaps: Gap[] }) {
  const w = useChangeWords()
  return (
    <div className={css.tableBox} data-scroll-x="">
      <table className={css.table}>
        <thead>
          <tr>
            <th scope="col">{w('colComponent')}</th><th scope="col">{w('colOperation')}</th><th scope="col">{w('colTo')}</th>
            <th scope="col" className={css.numCol}>{w('files')}</th><th scope="col">{w('colClosed')}</th>
            <th scope="col">{w('colSteps')}</th><th scope="col">{w('colDecision')}</th>
          </tr>
        </thead>
        <tbody>
          {gaps.map((g) => (
            <tr key={g.id}>
              <th scope="row"><GapLink id={g.id}><Id value={g.component} keep={3} /></GapLink></th>
              <td><OperationChip relation={RELATION_OF[g.operation]} /></td>
              <td>{g.to ? <Id value={g.to} /> : null}</td>
              <td className={css.numCol}><N value={g.files} /></td>
              <td><Closure gap={g} /></td>
              <td><LinkList>{(g.steps ?? []).map((s) => <StepLink key={s} plan={PLAN} step={s} />)}</LinkList></td>
              <td>{g.decision ? <Id value={g.decision} /> : null}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function RegisterBody({ data }: { data: StudioData }) {
  const w = useChangeWords()
  const { t } = usePrefs()
  const phone = usePhone()
  const search = useSearch({ strict: false }) as { relation?: string }
  usePageChrome(w('gapsTitle'), { to: '/change', label: t('journeyAndPlan') }, data.manifest.project.name)
  const all = useMemo(() => registerOrder(data.gaps?.gaps ?? []), [data.gaps])
  const chosen = all.some((g) => g.operation === search.relation) ? search.relation as ChangeOp : undefined
  const shown = chosen ? all.filter((g) => g.operation === chosen) : all
  const withCards = all.filter((g) => g.cards.length > 0).length
  return (
    <div className={page.page}>
      <MissingBanner data={data} />
      <ChangeNav />
      <PageTitle title={w('gapsTitle')} lead={w('gapsLead')} />
      {!data.gaps ? <NotMeasured data={data} section="gaps" title={w('gapsTitle')} /> : (
        <>
          <p className={css.count}>{w('gapsCount', { n: all.length, c: withCards, u: all.filter((g) => !g.cards.length && g.operation !== 'retain').length })}</p>
          <Filter gaps={all} chosen={chosen} />
          {!shown.length ? <Panel><StateMessage title={w('noGapsShown')} /></Panel> : phone ? (
            <Panel>
              <FoldList items={shown} first={12} label={w('gapsTitle')} render={(g) => (
                <RowLink to={`/change/gaps/${encodeURIComponent(g.id)}`} chevron={false}
                  title={<Id value={g.component} keep={3} />}
                  sub={<span className={css.rowSub}><OperationChip relation={RELATION_OF[g.operation]} to={g.to} /><Closure gap={g} /></span>}
                  end={<span className={css.muted}>{w('filesN', { n: g.files })}</span>} />
              )} />
            </Panel>
          ) : <Panel><GapTable gaps={shown} /></Panel>}
        </>
      )}
    </div>
  )
}

export function GapsPage() {
  return <WithData>{(data) => <RegisterBody data={data} />}</WithData>
}

function GapBody({ data, id }: { data: StudioData; id: string }) {
  const w = useChangeWords()
  const gap = data.gaps?.gaps.find((g) => g.id === id)
  usePageChrome(gap?.component ?? w('gapsTitle'), { to: '/change/gaps', label: w('gapsTitle') }, data.manifest.project.name)
  const cards = useMemo(() => byId(data.cards?.cards), [data.cards])
  const ops = useMemo(() => byId(data.operations?.operations), [data.operations])
  if (!data.gaps) return <div className={page.page}><ChangeNav /><NotMeasured data={data} section="gaps" title={w('gapsTitle')} /></div>
  if (!gap) return <div className={page.page}><ChangeNav /><Panel><StateMessage title={w('gapNotFound')} sub={<Id value={id} />} /></Panel></div>
  const sources = gap.operations?.map((o) => ops.get(o)?.sources ?? []).flat() ?? []
  const current = !gap.id.startsWith('target:')
  return (
    <div className={page.page}>
      <MissingBanner data={data} />
      <ChangeNav />
      <div className={css.head}>
        <span className={css.kicker}>{w('navGaps')}</span>
        <h1 className={css.title}><Id value={gap.component} /></h1>
        <span className={css.chips}><OperationChip relation={RELATION_OF[gap.operation]} to={gap.to} /><Closure gap={gap} /></span>
      </div>
      <div className={page.columns}>
        <div className={page.col}>
          {gap.reason && <Section title={w('why')}><Panel pad><Txt block>{gap.reason}</Txt></Panel></Section>}
          <Section title={w('closesIt')} count={gap.cards.length}>
            <Panel>
              {gap.cards.length ? (
                <FoldList items={gap.cards} first={8} label={w('closesIt')} render={(cid) => {
                  const card = cards.get(cid)
                  return <RowLink to={`/tasks/${encodeURIComponent(cid)}`} title={<Txt>{card?.title ?? cid}</Txt>} sub={<Id value={cid} />}
                    end={card ? <span className={css.muted}>{w(STATE_WORD[cardState(card.state)])}</span> : undefined} />
                }} />
              ) : <StateMessage title={w('noCard')} sub={w('closedSrc', { src: gap.closed.src })} />}
            </Panel>
          </Section>
          {sources.length > 0 && (
            <Section title={w('sources')} count={sources.length}>
              <Panel><FoldList items={sources} first={8} label={w('sources')} render={(s) => <RowLink to={`/change/gaps/${encodeURIComponent(s)}`} title={<Id value={s} keep={3} />} />} /></Panel>
            </Section>
          )}
        </div>
        <div className={page.col}>
          <Panel pad>
            <Props rows={[
              [w('colTo'), gap.to ? <Id value={gap.to} /> : '—'],
              ...(gap.responsibility ? [[w('responsibility'), <Txt key="r">{gap.responsibility}</Txt>] as [ReactNode, ReactNode]] : []),
              [w('files'), <N key="f" value={gap.files} />],
              ...(gap.cover ? [[w('cover'), w(`cover_${gap.cover}`)] as [ReactNode, ReactNode]] : []),
              [w('operations'), gap.operations?.length ? <LinkList key="o">{gap.operations.map((o) => <OpLink key={o} id={o} />)}</LinkList> : '—'],
              [w('planSteps'), gap.steps?.length ? <LinkList key="s">{gap.steps.map((s) => <StepLink key={s} plan={PLAN} step={s} />)}</LinkList> : w('notPlanned')],
              [w('decision'), gap.decision ? <Go key="d" to="/decisions" className={css.inlineLink}><Id value={gap.decision} /></Go> : '—'],
            ]} />
          </Panel>
          {current && <RowLinkPanel to="/system" search={{ view: 'change', focus: gap.component }} title={w('openOnMap')} />}
        </div>
      </div>
    </div>
  )
}

function RowLinkPanel({ to, search, title }: { to: string; search?: Record<string, string>; title: string }) {
  return <Panel><RowLink to={to} search={search} title={title} icon="system" /></Panel>
}

export function GapPage() {
  const { gapId } = useParams({ strict: false }) as { gapId?: string }
  return <WithData>{(data) => <GapBody data={data} id={decodeURIComponent(gapId ?? '')} />}</WithData>
}
