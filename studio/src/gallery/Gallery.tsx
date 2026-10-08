// #/_gallery: every component in every state (DESIGN.md §3), with the page's language and theme, or as a matrix of
// the four (ar/en × light/dark) frames. The automated gates run on it like on any page (scripts/gates.mjs).
import { useSearch } from '@tanstack/react-router'
import { useLayoutEffect, useRef, useState, type ReactNode } from 'react'
import { Button, CopyRequestButton, IconButton } from '../components/Button'
import { Badge, Chip, FreshnessChip, OperationChip, SeverityGlyph } from '../components/Chip'
import { SearchField, Segmented } from '../components/Controls'
import { EvidenceCard, FindingRow } from '../components/Finding'
import { Go } from '../components/Go'
import { HealthBlock, Meter, StatLink, StatLinks, StatTile, Tiles } from '../components/Health'
import { Icon, type IconName } from '../components/Icon'
import { FoldList, Panel, Props, RowButton, RowLink, Section, Skeleton, StateMessage } from '../components/Panel'
import { Sheet, SheetLead } from '../components/Sheet'
import { DecisionCard, Headline, Journey, NextStep, PlanStrip } from '../components/Story'
import { useToast } from '../components/Toast'
import type { Freshness, Relation, Severity } from '../data/types'
import { PrefsScope, usePrefs, type Lang, type Theme } from '../i18n/prefs'
import { Id, N, Txt } from '../i18n/text'
import { usePageChrome } from '../shell/chrome'
import { layout, PageTitle } from '../shell/Layout'
import { DataChainFixture, DataFixture, InfraFixture } from '../pages/data/MapsGallery'
import { cards, code, decisionAnswered, decisionMany, decisionTwo, facts, plan } from './fixtures'
import css from './Gallery.module.css'

type Forced = 'hover' | 'pressed' | 'focus' | 'selected'
const FORCED: Record<Forced, string> = { hover: 'data-hovered', pressed: 'data-pressed', focus: 'data-focus-visible', selected: 'data-selected' }

/** Shows a state that needs a pointer or a key (hover, pressed, focus-visible) by setting React Aria's attribute. */
function Force({ state, children }: { state?: Forced; children: ReactNode }) {
  const ref = useRef<HTMLSpanElement>(null)
  useLayoutEffect(() => {
    const target = ref.current?.firstElementChild
    if (target && state) target.setAttribute(FORCED[state], 'true')
  })
  return <span ref={ref} className={css.force}>{children}</span>
}

function State({ name, children, wide }: { name: string; children: ReactNode; wide?: boolean }) {
  return (
    <figure className={[css.state, wide && css.wide].filter(Boolean).join(' ')}>
      <figcaption className={css.stateName}><bdi dir="ltr">{name}</bdi></figcaption>
      <div className={css.stateBody}>{children}</div>
    </figure>
  )
}

function Group({ id, title, children }: { id: string; title: string; children: ReactNode }) {
  return (
    <section className={css.group} aria-labelledby={`g-${id}`} id={`c-${id}`}>
      <h2 className={css.groupTitle} id={`g-${id}`}><bdi dir="ltr">{title}</bdi></h2>
      <div className={css.states}>{children}</div>
    </section>
  )
}

const ICONS: IconName[] = ['home', 'system', 'problems', 'change', 'inbox', 'search', 'chevron', 'chevronDown', 'back', 'arrow', 'copy', 'check',
  'more', 'sun', 'moon', 'globe', 'file', 'folder', 'book', 'clock', 'x', 'pulse', 'command', 'gallery', 'opKeep', 'opModify', 'opRebuild', 'opDelete', 'opMerge', 'opIntroduce']
const SWATCHES = ['bg-canvas', 'bg-surface', 'bg-raised', 'bg-sunken', 'bg-hover', 'bg-selected', 'border-subtle', 'border-default', 'border-strong',
  'text-primary', 'text-secondary', 'text-tertiary', 'accent-solid', 'accent-button', 'accent-subtle', 'accent-text',
  'status-good', 'status-warning', 'status-serious', 'status-critical', 'sev-1', 'sev-2', 'sev-3', 'sev-4',
  'op-keep', 'op-modify', 'op-rebuild', 'op-introduce', 'op-merge', 'op-delete', 'seq-100', 'seq-300', 'seq-500', 'seq-700']

function Specimens() {
  const { t, lang } = usePrefs()
  const toast = useToast()
  const [sheet, setSheet] = useState(false)
  const [seg, setSeg] = useState<'a' | 'b' | 'c'>('a')
  const [query, setQuery] = useState('خطة')
  const ar = lang === 'ar'
  const sevs: Severity[] = ['low', 'medium', 'high', 'critical']
  const ops: Relation[] = ['retain', 'modify', 'rebuild', 'introduce', 'merge', 'delete']
  const fresh: Freshness[] = ['fresh', 'branch_moved', 'eaos_updated', 'unknown']
  return (
    <>
      <Group id="tokens-colour" title="Tokens · colour">
        <div className={css.swatches}>
          {SWATCHES.map((name) => (
            <div key={name} className={css.swatch}><span className={css.chipColour} style={{ background: `var(--${name})` }} /><Id value={`--${name}`} /></div>
          ))}
        </div>
      </Group>
      <Group id="tokens-type" title="Tokens · type, space, radius, elevation">
        <State name="display / large title / headline / section / body / meta / caption" wide>
          <div className={css.typeStack}>
            <span style={{ fontSize: 'var(--text-display)', fontWeight: 600, lineHeight: 1 }}><N value={58} /></span>
            <span style={{ fontSize: 'var(--text-large-title)', fontWeight: 600 }}>{ar ? 'المشاكل' : 'Problems'}</span>
            <span style={{ fontSize: 'var(--text-headline)', fontWeight: 500 }}><Txt>{ar ? '217 مشكلة، منها 165 يصلحها EAOS وحده.' : '217 problems, 165 of them EAOS fixes on its own.'}</Txt></span>
            <span style={{ fontSize: 'var(--text-section)', fontWeight: 600 }}>{ar ? 'هل تعتمد البنية المستهدفة؟' : 'Do you approve the target architecture?'}</span>
            <span>{ar ? 'نص أساسي بحجم 15 على الجوال، بلا تباعد حروف.' : 'Body text, 15 on the phone, 14 on desktop.'}</span>
            <span style={{ fontSize: 'var(--text-meta)', color: 'var(--text-secondary)' }}>{ar ? 'نص ثانوي' : 'Secondary text'}</span>
            <span style={{ fontSize: 'var(--text-caption)', color: 'var(--text-tertiary)' }}>{ar ? 'تعليق' : 'Caption'} · <Id value="src/components/account" /></span>
          </div>
        </State>
        <State name="space 2–56">
          <div className={css.spaces}>{[2, 4, 8, 12, 16, 20, 24, 32, 40, 56].map((n) => <span key={n} style={{ inlineSize: `var(--space-${n})` }} title={String(n)} />)}</div>
        </State>
        <State name="radius 4 / 8 / 12 / 16 / full">
          <div className={css.radii}>{['4', '8', '12', '16', 'full'].map((r) => <span key={r} style={{ borderRadius: `var(--radius-${r})` }}><bdi dir="ltr">{r}</bdi></span>)}</div>
        </State>
        <State name="elevation: hairline / float"><div className={css.radii}><span /><span style={{ boxShadow: 'var(--shadow-float)', borderColor: 'transparent' }} /></div></State>
      </Group>

      <Group id="icons" title="Icon (mirror flag on chevron, back, arrow)">
        <div className={css.icons}>{ICONS.map((name) => <span key={name} className={css.icon} title={name}><Icon name={name} /><Id value={name} /></span>)}</div>
      </Group>

      <Group id="button" title="Button · primary / secondary / ghost">
        {(['primary', 'secondary', 'ghost'] as const).map((variant) => (
          <State key={variant} name={`${variant}: default · hover · pressed · focus · loading`} wide>
            <div className={css.row}>
              <Button variant={variant} icon="check">{ar ? 'نعم' : 'Yes'}</Button>
              <Force state="hover"><Button variant={variant}>{ar ? 'تمرير' : 'Hover'}</Button></Force>
              <Force state="pressed"><Button variant={variant}>{ar ? 'ضغط' : 'Pressed'}</Button></Force>
              <Force state="focus"><Button variant={variant}>{ar ? 'تركيز' : 'Focus'}</Button></Force>
              <Button variant={variant} busy>{ar ? 'يحمّل' : 'Loading'}</Button>
            </div>
          </State>
        ))}
        <State name="large · block (wraps on narrow widths)" wide>
          <Button variant="primary" large block icon="check">{ar ? 'نعم، يتولاها المساعد ويعرض عليك ما يحتاج قرارك' : 'Yes, the assistant takes them on and shows you what needs your decision'}</Button>
        </State>
        <State name="icon button: default · hover · focus · small">
          <div className={css.row}>
            <IconButton icon="search" label={t('search')} />
            <Force state="hover"><IconButton icon="more" label={t('more')} /></Force>
            <Force state="focus"><IconButton icon="x" label={t('close')} /></Force>
            <IconButton icon="back" label={t('back')} small />
          </div>
        </State>
        <State name="copy request (tool tag) · toast">
          <div className={css.col}>
            <CopyRequestButton request="Run fix_start" tool="fix_start" />
            <CopyRequestButton request="Run audit" tool="audit" variant="primary" label={t('copyShort')} />
            <Button variant="ghost" onPress={() => toast(t('copied'))}>Toast</Button>
          </div>
        </State>
      </Group>

      <Group id="chip" title="Chip · status, freshness, severity, operation, badge">
        <State name="tones">
          <div className={css.row}>
            <Chip>{t('stateOpen')}</Chip><Chip tone="good">{t('bandGood')}</Chip><Chip tone="warning">{t('bandFair')}</Chip>
            <Chip tone="serious">{t('bandWeak')}</Chip><Chip tone="critical">{t('bandCritical')}</Chip><Chip tone="accent">{t('waiting')}</Chip>
          </div>
        </State>
        <State name="freshness: fresh · branch moved · EAOS updated · unknown · focus">
          <div className={css.row}>
            {fresh.map((f) => <FreshnessChip key={f} freshness={f} onPress={() => toast(f)} />)}
            <Force state="focus"><FreshnessChip freshness="unknown" /></Force>
          </div>
        </State>
        <State name="severity glyph: with word · bars only">
          <div className={css.row}>{sevs.map((s) => <SeverityGlyph key={s} severity={s} />)}{sevs.map((s) => <SeverityGlyph key={`b${s}`} severity={s} word={false} />)}</div>
        </State>
        <State name="operation: six reserved hues · with target" wide>
          <div className={css.row}>{ops.map((op) => <OperationChip key={op} relation={op} />)}<OperationChip relation="rebuild" to="features" /></div>
        </State>
        <State name="badge"><div className={css.row}><Badge count={2} /><Badge count={14} /></div></State>
      </Group>

      <Group id="controls" title="SegmentedControl · SearchField">
        <State name="segmented: 2 options · 3 options · focus">
          <div className={css.col}>
            <Segmented label="lang" value="ar" onChange={() => {}} options={[{ id: 'ar', label: 'عربي', lang: 'ar' }, { id: 'en', label: 'English', lang: 'en' }]} />
            <Segmented label="who" value={seg} onChange={setSeg} options={[{ id: 'a', label: t('allProblems') }, { id: 'b', label: t('needsYou') }, { id: 'c', label: t('eaosFixes') }]} />
          </div>
        </State>
        <State name="search: filled · empty">
          <div className={css.col}>
            <SearchField label={t('search')} value={query} onChange={setQuery} placeholder={t('searchPlaceholder')} />
            <SearchField label={t('search')} value="" onChange={() => {}} placeholder={t('searchPlaceholder')} />
          </div>
        </State>
      </Group>

      <Group id="rows" title="Panel · Section · RowLink · RowButton · FoldList · Props">
        <State name="rows: default · hover · current · end value">
          <Panel>
            <RowLink to="/_gallery" icon="book" title={t('documents')} sub={ar ? 'ما كتبه EAOS، مرتّبًا للقراءة' : 'What EAOS wrote, in reading order'} end={<N value={292} />} />
            <Force state="hover"><RowButton icon="clock" title={ar ? 'السجل' : 'History'} sub={ar ? 'فحص واحد' : 'One scan'} end={<N value={1} />} onPress={() => {}} /></Force>
            <RowButton title={<Id value="src/components/account" />} sub={<OperationChip relation="rebuild" to="feature:account" />} pressed onPress={() => {}} />
          </Panel>
        </State>
        <State name="fold list: first 6, then show all">
          <Section title={ar ? 'المكوّنات' : 'Components'} count={9}>
            <Panel><FoldList items={Array.from({ length: 9 }, (_, i) => `src/components/part-${i + 1}`)} render={(name) => <RowButton title={<Id value={name} />} onPress={() => {}} />} /></Panel>
          </Section>
        </State>
        <State name="props: value · not recorded">
          <Panel pad><Props rows={[[t('files'), <N value={279} />], [t('branch'), t('notRecorded'), true], [t('eaosVersion'), <Id value="0.0.2" />]]} /></Panel>
        </State>
      </Group>

      <Group id="states" title="Loading · empty · error">
        <State name="loading (skeleton)"><Panel><Skeleton label={t('loading')} /></Panel></State>
        <State name="empty"><Panel><StateMessage icon="inbox" title={t('nothingWaits')} sub={t('nothingWaitsSub')} /></Panel></State>
        <State name="error"><Panel><StateMessage kind="error" title={t('errorTitle')} sub={t('errorSub')} /></Panel></State>
      </Group>

      <Group id="health" title="HealthBlock · Meter · StatTile · StatLink">
        <State name="health: weak · excellent · not measured" wide>
          <div className={css.grid3}>
            <Panel><HealthBlock score={{ value: 0.58, src: 'gallery' }} history={1} /></Panel>
            <Panel><HealthBlock score={{ value: 0.93, src: 'gallery' }} history={3} /></Panel>
            <Panel><HealthBlock score={{ value: null, src: 'gallery' }} history={0} /></Panel>
          </div>
        </State>
        <State name="meter: 0 · 39 · 74 · 100">
          <div className={css.col}>{[0, 39, 74, 100].map((n) => <Meter key={n} score={n} ticks={n === 74} />)}</div>
        </State>
        <State name="stat tiles: score with meter · count · not measured">
          <Tiles>
            <StatTile value={58} of="/100" label={t('health')} meter={58} onPress={() => {}} />
            <StatTile value={52} label={t('needCheck')} to="/_gallery" />
            <StatTile value={null} label={t('highSeverity')} to="/_gallery" />
          </Tiles>
        </State>
        <State name="stat links">
          <StatLinks>
            <StatLink icon={<SeverityGlyph severity="high" word={false} />} value={26} label={t('sevHigh')} to="/_gallery" />
            <StatLink icon={<SeverityGlyph severity="low" word={false} />} value={150} label={t('sevLow')} to="/_gallery" />
          </StatLinks>
        </State>
      </Group>

      <Group id="story" title="Headline · DecisionCard · NextStep · Journey · PlanStrip">
        <State name="headline: numbers are links" wide>
          <Headline parts={ar ? [{ value: 217, to: '/_gallery', word: 'مشكلة' }, '، منها ', { value: 165, to: '/_gallery', word: 'يصلحها' }, ' EAOS وحده.']
            : [{ value: 217, to: '/_gallery', word: 'problems' }, ', ', { value: 165, to: '/_gallery', word: 'of them' }, ' EAOS fixes on its own.']} />
        </State>
        <State name="decision: two answers"><DecisionCard decision={decisionTwo} cardsTo={{ to: '/_gallery' }} /></State>
        <State name="decision: several long answers"><DecisionCard decision={decisionMany} /></State>
        <State name="decision: answered"><DecisionCard decision={decisionAnswered} /></State>
        <State name="next step: with tool · without">
          <div className={css.col}>
            <NextStep action={ar ? 'ابدأ دفعة إصلاح تشمل 165 بطاقة' : 'Start a fix batch for 165 cards'} sub={ar ? 'بعد إجابتك أعلاه' : 'After your answer above'} tool="fix_start" request="fix_start" />
            <NextStep action={ar ? 'راجع البنية المستهدفة' : 'Review the target architecture'} tool={null} request="review" />
          </div>
        </State>
        <State name="journey: values · not measured" wide>
          <div className={css.col}>
            <Journey label="journey" stages={[{ key: t('today'), value: 47, unit: t('componentsInCode'), to: '/_gallery' }, { key: t('changeStage'), value: 35, unit: t('componentsChange'), to: '/_gallery' }, { key: t('target'), value: 29, unit: t('componentsInTarget'), to: '/_gallery' }]} />
            <Journey label="journey" stages={[{ key: t('today'), value: 47, unit: t('componentsInCode'), to: '/_gallery' }, { key: t('changeStage'), value: null, unit: '', to: '/_gallery' }, { key: t('target'), value: null, unit: '', to: '/_gallery' }]} />
          </div>
        </State>
        <State name="plan strip: not started · active">
          <div className={css.col}><PlanStrip plan={plan(0)} to="/_gallery" /><PlanStrip plan={plan(60)} to="/_gallery" /></div>
        </State>
      </Group>

      <Group id="finding" title="FindingRow · EvidenceCard">
        <State name="rows: needs you · EAOS fixes · selected · long path" wide>
          <Panel><ul>{cards.map((card, i) => <li key={card.id}><FindingRow card={card} to="/_gallery" search={{ card: card.id }} current={i === 2} /></li>)}</ul></Panel>
        </State>
        <State name="evidence: with code (own LTR scroll) · sentence only" wide>
          <div className={css.col}><EvidenceCard fact={facts[0]} code={code} /><EvidenceCard fact={facts[1]} /></div>
        </State>
      </Group>

      <Group id="overlays" title="Sheet · CommandPalette (⌘K) · Toast">
        <State name="sheet: bottom on phone, centred dialog on desktop">
          <Button onPress={() => setSheet(true)}>{ar ? 'افتح ورقة' : 'Open a sheet'}</Button>
          <Sheet isOpen={sheet} onOpenChange={setSheet} title={t('isScanCurrent')}>
            <SheetLead>{t('freshUnknownLead')}</SheetLead>
            <Props rows={[[t('branch'), t('notRecorded'), true]]} />
          </Sheet>
        </State>
        <State name="palette: ⌘K / Ctrl-K anywhere, or the search button">
          <p className={css.note}><Txt>{ar ? 'اضغط ⌘K أو Ctrl-K. البحث يطبّع الألف والتاء المربوطة والياء والتشكيل والتطويل.' : 'Press ⌘K or Ctrl-K. Search folds alef forms, ta marbuta, ya, diacritics and tatweel.'}</Txt></p>
        </State>
      </Group>

      <Group id="bidi" title="Bidi · Txt and Id">
        <State name="Latin runs and number groups inside Arabic" wide>
          <p><Txt>{'ابدأ دفعة إصلاح بأداة fix_start من EAOS على الفرع develop (الخطوات 1 · 3 · 35، والأسطر 1–47).'}</Txt></p>
        </State>
        <State name="path: whole · start-truncated (full value in the title)" wide>
          <div className={css.col}>
            <Id value="src/components/maintenance/workorder/forms/WorkOrderAttachmentsUploader.tsx" />
            <Id value="src/components/maintenance/workorder/forms/WorkOrderAttachmentsUploader.tsx" keep={2} />
          </div>
        </State>
        <State name="link in a sentence">
          <p>{ar ? 'افتح ' : 'Open '}<Go to="/_gallery" className={css.link}>{ar ? 'قائمة المشاكل' : 'the problems list'}</Go>.</p>
        </State>
      </Group>

      <Group id="data-map" title="Data paths map · infrastructure lens (fixture)">
        <State name="data paths: today (a store written from two places, focused)" wide><DataFixture mode="current" /></State>
        <State name="data paths: change" wide><DataFixture mode="change" /></State>
        <State name="data paths: the seven links and one write's chain" wide><DataChainFixture /></State>
        <State name="infrastructure: today" wide><InfraFixture mode="current" /></State>
        <State name="infrastructure: target (keep, introduce, silent)" wide><InfraFixture mode="target" /></State>
      </Group>
    </>
  )
}

const FRAMES: [Lang, Theme][] = [['ar', 'light'], ['ar', 'dark'], ['en', 'light'], ['en', 'dark']]

export function GalleryPage() {
  const { t } = usePrefs()
  const { view } = useSearch({ strict: false }) as { view?: string }
  usePageChrome(t('gallery'))
  const matrix = view === 'matrix'
  return (
    <div className={layout.page}>
      <PageTitle title={t('gallery')} lead={t('galleryLead')} />
      <nav className={css.views} aria-label={t('gallery')}>
        <Go to="/_gallery" search={{}} className={css.viewLink} current={!matrix}>{t('galleryThisMode')}</Go>
        <Go to="/_gallery" search={{ view: 'matrix' }} className={css.viewLink} current={matrix}><bdi dir="ltr">ar · en × light · dark</bdi></Go>
      </nav>
      {matrix ? (
        <div className={css.matrix}>
          {FRAMES.map(([lang, theme]) => (
            <PrefsScope key={`${lang}-${theme}`} lang={lang} theme={theme} className={css.frame}>
              <p className={css.frameName}><bdi dir="ltr">{lang} · {theme}</bdi></p>
              <Specimens />
            </PrefsScope>
          ))}
        </div>
      ) : <Specimens />}
    </div>
  )
}
