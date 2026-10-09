// Home: where the project stands in one sentence, its health, what waits for the person and the next step. A first
// composition of the design system on real data; NS37.T3 completes it (journey, land, plan, library).
import { useMemo, useState } from 'react'
import { BandChip, BandDot, HealthBlock, StatLink, StatLinks, StatTile, Tiles, useBandWord } from '../components/Health'
import { SeverityGlyph } from '../components/Chip'
import { FoldList, Panel, RowLink, Section } from '../components/Panel'
import { Sheet, SheetLead } from '../components/Sheet'
import { DecisionCard, Headline, NextStep, headlineParts } from '../components/Story'
import { counts } from '../data/context'
import type { StudioData } from '../data/types'
import { usePrefs } from '../i18n/prefs'
import { N, Txt } from '../i18n/text'
import { usePageChrome } from '../shell/chrome'
import { layout, MissingBanner, PageTitle, WithData } from '../shell/Layout'
import { HOME_NEEDS } from '../data/stages'
import { nextRequest } from './requests'
import { HomeMaps } from '../map/home'
import css from './Pages.module.css'

const AREA = {
  security: ['الأمان', 'Security'], structure: ['البنية', 'Structure'], quality: ['جودة الكود', 'Code quality'],
  performance: ['الأداء تحت الضغط', 'Performance under load'], maintainability: ['سهولة التطوير والاختبار', 'Ease of change and testing'],
} as Record<string, [string, string]>

function HealthSheet({ data, isOpen, onOpenChange }: { data: StudioData; isOpen: boolean; onOpenChange: (open: boolean) => void }) {
  const { t, lang } = usePrefs()
  const health = data.health
  if (!health) return null
  return (
    <Sheet isOpen={isOpen} onOpenChange={onOpenChange} title={t('projectHealth')}>
      <SheetLead><bdi dir="ltr" className="id">{health.formula}</bdi></SheetLead>
      <ul className={css.areas}>
        {health.domains.map((domain) => {
          const score = domain.score.value === null ? null : Math.round(domain.score.value * 100)
          return (
            <li key={domain.id} className={css.area}>
              <span>{(AREA[domain.id] ?? [domain.name, domain.name])[lang === 'ar' ? 0 : 1]}</span>
              <span className={css.areaBar} aria-hidden="true"><i style={{ inlineSize: `${score ?? 0}%` }} /></span>
              {score === null ? <span className={css.muted}>{t('notMeasured')}</span> : <><N value={score} className={css.areaScore} /><BandChip score={score} /></>}
            </li>
          )
        })}
      </ul>
    </Sheet>
  )
}

function HomeBody({ data }: { data: StudioData }) {
  const { t, lang } = usePrefs()
  const [healthOpen, setHealthOpen] = useState(false)
  const project = data.manifest.project.name
  usePageChrome(t('home'), undefined, project)
  const c = useMemo(() => counts(data), [data])
  const bandWord = useBandWord()
  const score = data.health?.score.value
  const scoreN = score === null || score === undefined ? null : Math.round(score * 100)
  const decisions = (data.decisions?.decisions ?? []).filter((d) => d.state === 'waiting')
  const [first, ...rest] = decisions
  const verdict = data.head?.verdict ?? ''
  const parts = headlineParts(verdict, [
    { value: c.cards, to: '/problems' },
    { value: c.fixable, to: '/problems', search: { who: 'eaos' } },
  ])
  const next = data.head?.next
  return (
    <div className={[layout.page, css.homePage].join(' ')}>
      <MissingBanner data={data} />
      <div className={layout.titleBlock}>
        <PageTitle title={project} kicker />
        {verdict && <Headline parts={parts} />}
      </div>
      <div className={layout.columns}>
        <div className={layout.col}>
          <div className={css.phoneOnly}>
            <Tiles>
              <StatTile value={scoreN} of={t('outOf100')} label={scoreN === null ? t('health') : <><BandDot score={scoreN} />{t('health')}: {bandWord(scoreN)}</>} meter={scoreN ?? undefined} onPress={() => setHealthOpen(true)} />
              <StatTile value={c.needDecision} label={t('needCheck')} to="/problems" search={{ who: 'you' }} />
              <StatTile value={c.bySeverity.high + c.bySeverity.critical} label={t('highSeverity')} to="/problems" search={{ severity: 'critical,high' }} />
            </Tiles>
          </div>
          <Panel className={[css.status, css.deskOnly].join(' ')}>
            {data.health && <HealthBlock score={data.health.score} history={data.health.history.length} onPress={() => setHealthOpen(true)} />}
            <div className={css.statusSide}>
              <StatLinks label={t('problems')}>
                <StatLink icon={<SeverityGlyph severity="critical" word={false} />} value={c.needDecision} label={t('needCheck')} to="/problems" search={{ who: 'you' }} />
                {(['high', 'medium', 'low'] as const).map((sev) => (
                  <StatLink key={sev} icon={<SeverityGlyph severity={sev} word={false} />} value={c.bySeverity[sev] + (sev === 'high' ? c.bySeverity.critical : 0)}
                    label={t(sev === 'high' ? 'sevHigh' : sev === 'medium' ? 'sevMedium' : 'sevLow')} to="/problems" search={{ severity: sev === 'high' ? 'critical,high' : sev }} />
                ))}
              </StatLinks>
            </div>
          </Panel>
          <HomeMaps data={data} />
        </div>
        <div className={layout.col}>
          {first && (
            <Section title={t('waitingForYou')} count={decisions.length}>
              <DecisionCard compact decision={first} cardsTo={{ to: '/problems', search: { who: 'you' } }} />
              {rest.length > 0 && (
                <Panel>
                  {/* folded at six with "Show all N" in place (DESIGN.md list folding), so Home stays within two phone screens */}
                  <FoldList items={rest} label={t('waitingForYou')} render={(d) => <RowLink compact to="/decisions" title={<Txt>{d.question}</Txt>} sub={<Txt>{d.recommendation}</Txt>} />} />
                </Panel>
              )}
            </Section>
          )}
          {next && (
            <Section title={t('nextStep')}>
              <NextStep action={next.action} tool={next.tool} request={nextRequest(next.action, next.tool, project, lang)} />
            </Section>
          )}
        </div>
      </div>
      <HealthSheet data={data} isOpen={healthOpen} onOpenChange={setHealthOpen} />
    </div>
  )
}

export function HomePage() {
  return <WithData needs={HOME_NEEDS}>{(data) => <HomeBody data={data} />}</WithData>
}
