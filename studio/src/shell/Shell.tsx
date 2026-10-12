// The frame every page sits in (DESIGN.md §3, §4). Phone (< 768): top bar, content, a fixed tab bar with the five
// sections, sheets from the bottom, pages pushed onto a stack with a back button. Tablet (768–1199): a 56px rail.
// Desktop (≥ 1200): the 232px sidebar, breadcrumb top bar, Cmd/Ctrl-K palette, split panes and inspector.
import { Outlet, useRouterState } from '@tanstack/react-router'
import { lazy, Suspense, useEffect, useMemo, useState } from 'react'
import { Button as AriaButton } from 'react-aria-components'
import { IconButton } from '../components/Button'
import buttonCss from '../components/Button.module.css'
import { Badge, FreshnessChip } from '../components/Chip'
import { Segmented } from '../components/Controls'
import { Go } from '../components/Go'
import { Icon } from '../components/Icon'
import { Props } from '../components/Panel'
import { Sheet, SheetSub } from '../components/Sheet'
import { BranchLiveProvider, useFreshView } from '../branches/live'
import { ScanSheet } from '../branches/ScanSheet'
import { BranchChip, BranchSwitcher } from '../branches/Switcher'
import { useBranchWords } from '../branches/words'
import { CommandProvider } from '../command/command'
import { CommandHost } from '../command/CommandHost'
import { useActions } from '../data/actions/store'
import { counts, useLoaded, useSections, useStudio, type Counts } from '../data/context'
import { COUNT_NEEDS } from '../data/stages'
import { deviceZone, usePrefs } from '../i18n/prefs'
import { Id, N, When } from '../i18n/text'
import { useChrome } from './chrome'
import { useOpenedOnce, whenIdle } from './later'
import { ScanBanner } from './ScanBanner'
import { grouped, sectionOf, visibleSections, type SectionDef } from './sections'
import css from './Shell.module.css'
import { SystemViews } from '../pages/system/SystemViews'

// The palette is its own chunk (shell/later.ts): read once the report is drawn, drawn from its first opening
const loadPalette = () => import('./Palette')
const Palette = lazy(() => loadPalette().then((module) => ({ default: module.Palette })))

function useCounts(): Counts | null {
  const data = useStudio()
  const { decisions } = useActions()
  return useMemo(() => {
    if (!data) return null
    const result = counts(data)
    result.decisionsWaiting -= (data.decisions?.decisions ?? []).filter((d) => d.state === 'waiting' && decisions.some((r) => r.id === d.id && r.response)).length
    return result
  }, [data, decisions])
}

/** The command centre's counts beside the report's: questions from runs join the inbox, and runs that are not over. */
function useLiveCounts(): Record<string, number> {
  const { questions, runs } = useActions()
  return { decisions: questions.length, runs: runs.filter((run) => !['done', 'failed', 'stopped'].includes(run.state)).length }
}

function LanguageAndTheme({ comfortable }: { comfortable?: boolean }) {
  const { t, lang, theme, setLang, setTheme } = usePrefs()
  return (
    <>
      <Segmented label={t('language')} value={lang} onChange={setLang} comfortable={comfortable}
        options={[{ id: 'ar', label: lang === 'en' ? 'Arabic' : 'عربي', lang: 'ar' }, { id: 'en', label: 'English', lang: 'en' }]} />
      <Segmented label={t('appearance')} value={theme} onChange={setTheme} comfortable={comfortable}
        options={[
          { id: 'light', label: comfortable ? <><Icon name="sun" />{t('light')}</> : <Icon name="sun" />, aria: comfortable ? undefined : t('light') },
          { id: 'dark', label: comfortable ? <><Icon name="moon" />{t('dark')}</> : <Icon name="moon" />, aria: comfortable ? undefined : t('dark') },
        ]} />
    </>
  )
}

/** What a section's link carries: the count beside its name (null while it is still being read, or none), and the
 * badge of things waiting for the person. */
function useNavNumbers(): (s: SectionDef) => { count: number | null; badge: number } {
  const c = useCounts()
  const live = useLiveCounts()
  const pending = useStudio()?.pending ?? []
  return (s) => {
    const read = c && !(s.countFrom && pending.includes(s.countFrom)) ? c : null
    const count = s.count ? (read ? s.count(read) + (live[s.id] ?? 0) : null) : live[s.id] || null
    const badge = s.badge ? (read ? s.badge(read) : 0) + (live[s.id] ?? 0) : 0
    return { count, badge }
  }
}

function Sidebar({ project, current, onPalette, onProject }: { project: string; current?: SectionDef; onPalette: () => void; onProject: () => void }) {
  const { t, dev } = usePrefs()
  const numbers = useNavNumbers()
  const data = useStudio()
  const item = (s: SectionDef) => {
    const { count } = numbers(s)
    return (
      <Go key={s.id} to={s.to} className={css.navItem} current={current?.id === s.id} label={t(s.nav)}>
        <Icon name={s.icon} />
        <span className={css.navLabel}>{t(s.nav)}</span>
        {count !== null && <N value={count} className={css.navCount} />}
      </Go>
    )
  }
  const groups = grouped(visibleSections(dev))
  return (
    <aside className={css.sidebar} aria-label={t('navigation')}>
      <AriaButton className={css.proj} onPress={onProject} data-open="project" aria-label={`${project}: ${t('projectAndDisplay')}`}>
        <span className={css.projMark} aria-hidden="true">{project.slice(0, 1).toUpperCase()}</span>
        <span className={css.projText}><span className={css.projName} title={project} data-truncate>{project}</span><span className={css.projSub}>{t('studio')}</span></span>
        <Icon name="chevronDown" className={css.projChev} />
      </AriaButton>
      <AriaButton className={css.navSearch} onPress={onPalette} aria-label={t('searchCommands')}>
        <Icon name="search" /><span>{t('searchCommands')}</span><kbd>⌘K</kbd>
      </AriaButton>
      <nav className={css.nav} aria-label={t('navigation')}>
        {groups.map((group, i) => group[0].group ? (
          <div key={i} className={css.navGroup}>
            <div className={css.navGroupTitle}>{t(group[0].group)}</div>
            {group.map(item)}
          </div>
        ) : group.map(item))}
        {dev && <div className={css.navGroup}><div className={css.navGroupTitle}>dev</div>
          <Go to="/_gallery" className={css.navItem} current={current === undefined} label={t('gallery')}><Icon name="gallery" /><span className={css.navLabel}>{t('gallery')}</span></Go></div>}
      </nav>
      <div className={css.sideFoot}>
        <LanguageAndTheme />
        <div className={css.version}>
          <Id value={`EAOS ${data?.manifest.built.version ?? ''} · contract ${data?.manifest.contract ?? 1}`.replace('  ', ' ')} />
        </div>
      </div>
    </aside>
  )
}

/** The phone's tab bar: the five sections most used, then "More", which holds them all and is marked while the page
 * open is one of the others. Its badge sums the badges of the sections it holds. */
function TabBar({ current, onMore }: { current?: SectionDef; onMore: () => void }) {
  const { t } = usePrefs()
  const numbers = useNavNumbers()
  const sections = visibleSections(false)
  const tabs = sections.filter((s) => s.tabbar)
  const more = sections.filter((s) => !s.tabbar).reduce((sum, s) => sum + numbers(s).badge, 0)
  const mark = (badge: number) => badge > 0 && <span className={css.tabBadge}><Badge count={badge} /></span>
  const said = (badge: number) => badge > 0 && <span className="sr"> ({badge})</span>
  return (
    <nav className={css.tabbar} aria-label={t('mainTabs')}>
      {tabs.map((s) => {
        const { badge } = numbers(s)
        return (
          <Go key={s.id} to={s.to} className={css.tab} current={current?.id === s.id}>
            <span className={css.tabIcon}><Icon name={s.icon} size={22} />{mark(badge)}</span>
            <span className={css.tabLabel}>{t(s.tab)}{said(badge)}</span>
          </Go>
        )
      })}
      <AriaButton className={css.tab} onPress={onMore} data-open="more" data-current={current && !current.tabbar ? '' : undefined}>
        <span className={css.tabIcon}><Icon name="gallery" size={22} />{mark(more)}</span>
        <span className={css.tabLabel}>{t('more')}{said(more)}</span>
      </AriaButton>
    </nav>
  )
}

/** The phone's "More": every section in the sidebar's groups and order with its count, search, and the display. */
function MoreSheet({ isOpen, onOpenChange, current, onPalette, onProject, project }:
  { isOpen: boolean; onOpenChange: (open: boolean) => void; current?: SectionDef; onPalette: () => void; onProject: () => void; project: string }) {
  const { t, dev } = usePrefs()
  const numbers = useNavNumbers()
  const close = () => onOpenChange(false)
  return (
    <Sheet isOpen={isOpen} onOpenChange={onOpenChange} title={t('allSections')}>
      <AriaButton className={css.moreSearch} onPress={onPalette}><Icon name="search" /><span>{t('searchEverything')}</span></AriaButton>
      {grouped(visibleSections(dev)).map((group) => (
        <div key={group[0].id} className={css.moreGroup}>
          {group[0].group && <SheetSub>{t(group[0].group)}</SheetSub>}
          <div className={css.moreGrid}>
            {group.map((s) => {
              const { count, badge } = numbers(s)
              return (
                <Go key={s.id} to={s.to} className={css.moreItem} current={current?.id === s.id} onClick={close}>
                  <span className={css.moreIcon}><Icon name={s.icon} size={20} /></span>
                  <span className={css.moreLabel}>{t(s.nav)}</span>
                  {badge > 0 ? <Badge count={badge} /> : count !== null && <N value={count} className={css.navCount} />}
                </Go>
              )
            })}
          </div>
        </div>
      ))}
      <SheetSub>{t('display')}</SheetSub>
      <div className={css.rowSet}><LanguageAndTheme comfortable /></div>
      <AriaButton className={css.moreProject} onPress={onProject} data-open="project">
        <span className={css.projMark} aria-hidden="true">{project.slice(0, 1).toUpperCase()}</span>
        <span className={css.moreLabel}>{t('projectAndDisplay')}</span><Icon name="chevron" />
      </AriaButton>
    </Sheet>
  )
}

function Freshness({ onScan }: { onScan: () => void }) {
  const loaded = useLoaded()
  const view = useFreshView()
  if (loaded.kind !== 'ready' || !view) return null
  return <span className={css.freshChip} data-live={view.live ? '' : undefined}><FreshnessChip freshness={view.state} count={view.count} onPress={onScan} /></span>
}

function TopBar({ project, current, onPalette, onScan, onBranches }:
  { project: string; current?: SectionDef; onPalette: () => void; onScan: () => void; onBranches: () => void }) {
  const { t } = usePrefs()
  const chrome = useChrome()
  const systemWorkspace = useRouterState({ select: (s) => s.location.pathname.startsWith('/system') || s.location.pathname.startsWith('/screens') || s.location.pathname.startsWith('/flows') })
  const back = systemWorkspace ? undefined : chrome.back
  const sectionTitle = current ? t(current.nav) : t('gallery')
  return (
    <header className={css.topbar}>
      <div className={css.desk}>
        <nav className={css.crumbs} aria-label={t('breadcrumb')}>
          <Go to="/" className={css.crumb}>{project}</Go>
          {current?.id !== 'home' && <><span className={css.crumbSep} aria-hidden="true">/</span>
            {back ? <Go to={back.to} search={back.search} className={css.crumb}>{sectionTitle}</Go> : <span aria-current="page">{sectionTitle}</span>}</>}
          {back && <><span className={css.crumbSep} aria-hidden="true">/</span><span aria-current="page" className={css.crumbLast} title={chrome.title} data-truncate>{chrome.title}</span></>}
        </nav>
        <div className={css.deskEnd}>
          <BranchChip onPress={onBranches} />
          <Freshness onScan={onScan} />
          <AriaButton className={css.cmdk} onPress={onPalette} aria-label={t('searchEverything')} data-truncate>
            <Icon name="search" /><span>{t('searchEverything')}</span><kbd>⌘K</kbd>
          </AriaButton>
        </div>
      </div>
      <div className={css.phone}>
        {back
          ? <Go to={back.to} search={back.search} className={css.back}><Icon name="back" size={20} /><span>{back.label}</span></Go>
          : <span className={css.phoneChips}><BranchChip onPress={onBranches} /><Freshness onScan={onScan} /></span>}
        <span className={css.phoneSpacer} />
        <Go to="/scan" className={[buttonCss.iconBtn, css.liveLink].join(' ')} label={t('liveCheck')} current={current?.id === 'scan'}><Icon name="live" /></Go>
        <IconButton icon="search" label={t('search')} onPress={onPalette} />
      </div>
    </header>
  )
}

/** Settings: the time zone every time is shown in; the device's unless the person chooses one, and remembered. */
function TimeZoneSetting() {
  const { zone, zoneChoice, setZone } = usePrefs()
  const w = useBranchWords()
  const device = deviceZone()
  const zones = (Intl as unknown as { supportedValuesOf?: (key: string) => string[] }).supportedValuesOf?.('timeZone') ?? []
  const options = [...new Set([...(zoneChoice ? [zoneChoice] : []), 'UTC', ...zones])]
  return (
    <label className={css.zone}>
      <span>{w('timeZone')}</span>
      <select value={zoneChoice ?? ''} onChange={(event) => setZone(event.target.value || null)} data-zone={zone}>
        <option value="">{w('timeZoneDevice', { z: device })}</option>
        {options.map((name) => <option key={name} value={name}>{name}</option>)}
      </select>
      <small>{w('timeZoneLead')}</small>
    </label>
  )
}

function ProjectSheet({ isOpen, onOpenChange, project }: { isOpen: boolean; onOpenChange: (open: boolean) => void; project: string }) {
  const { t } = usePrefs()
  return (
    <Sheet isOpen={isOpen} onOpenChange={onOpenChange} title={project}>
      <ProjectFacts />
      <SheetSub>{t('display')}</SheetSub>
      <div className={css.rowSet}><LanguageAndTheme comfortable /></div>
      <TimeZoneSetting />
    </Sheet>
  )
}

/** The project's facts, drawn only while its sheet is open (a closed sheet renders nothing of its body). */
function ProjectFacts() {
  const { t } = usePrefs()
  const data = useStudio()
  const rows: [React.ReactNode, React.ReactNode, boolean?][] = []
  if (data?.meta) {
    rows.push([t('files'), data.meta.files.value === null ? t('notMeasured') : <N value={data.meta.files.value} />, data.meta.files.value === null])
    rows.push([t('lines'), data.meta.lines.value === null ? t('notMeasured') : <N value={data.meta.lines.value} />, data.meta.lines.value === null])
    rows.push([t('languages'), <bdi dir="ltr">{data.meta.languages.map((l) => `${l.name} ${Math.round(l.share * 100)}%`).join(', ')}</bdi>])
  }
  if (data) {
    rows.push([t('scanned'), data.manifest.scanned.at ? <When iso={data.manifest.scanned.at} /> : t('notRecorded'), !data.manifest.scanned.at])
    rows.push([t('branch'), data.manifest.scanned.branch ? <Id value={data.manifest.scanned.branch} /> : t('notRecorded'), !data.manifest.scanned.branch])
    rows.push([t('eaosVersion'), <Id value={data.manifest.built.version} />])
  }
  return rows.length > 0 ? <Props rows={rows} /> : null
}

declare global { interface Window { EAOS_REPORTS?: { name: string; href: string }[] } }

function WorkspaceReportPicker({ project, pathname }: { project: string; pathname: string }) {
  const { lang } = usePrefs()
  const reports = window.EAOS_REPORTS ?? []
  if (reports.length < 2) return null
  return <label className={css.reportPicker}>
    <span>{lang === 'ar' ? 'المشروع' : 'Project'}</span>
    <select aria-label={lang === 'ar' ? 'المشروع' : 'Project'} value={project} onChange={(event) => {
      const report = reports.find((entry) => entry.name === event.target.value)
      if (report) window.location.assign(`${report.href}#${pathname}`)
    }}>{reports.map((report) => <option key={report.name} value={report.name}>{report.name}</option>)}</select>
  </label>
}

export function Shell() {
  const { t } = usePrefs()
  const data = useStudio()
  const loaded = useLoaded()
  const pathname = useRouterState({ select: (s) => s.location.pathname })
  const systemWorkspace = pathname.startsWith('/system') || pathname.startsWith('/screens') || pathname.startsWith('/flows')
  // Only the lens: selecting the whole search object would draw the frame again on every keystroke of a page's search
  const lens = useRouterState({ select: (s) => (s.location.search as { lens?: string }).lens })
  const systemView = pathname === '/system' ? (lens === 'infra' ? 'infra' : 'map') : pathname.startsWith('/screens') ? 'screens' : pathname.startsWith('/flows') ? 'paths' : pathname.startsWith('/system/f/') ? 'functions' : pathname.split('/')[2] ?? 'map'
  const current = pathname.startsWith('/_') ? undefined : sectionOf(pathname)
  const [palette, setPalette] = useState(false)
  const [projectSheet, setProjectSheet] = useState(false)
  const [scanSheet, setScanSheet] = useState(false)
  const [branchSheet, setBranchSheet] = useState(false)
  const [moreSheet, setMoreSheet] = useState(false)
  const project = data?.manifest.project.name ?? t('studio')
  // The frame's counts are read once the first page is drawn (data/stages.ts COUNT_NEEDS), and so is the palette
  useSections(COUNT_NEEDS, 'idle')
  const ready = loaded.kind === 'ready'
  useEffect(() => (ready ? whenIdle(() => { void loadPalette() }) : undefined), [ready])
  const paletteOpened = useOpenedOnce(palette)

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') { event.preventDefault(); setPalette((open) => !open) }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])
  // A new view opens at its top, as a pushed screen does
  useEffect(() => { if (!systemWorkspace) window.scrollTo(0, 0) }, [pathname, systemWorkspace])

  return (
    <CommandProvider>
    <BranchLiveProvider>
      <a className={css.skip} href="#main" onClick={(e) => { e.preventDefault(); document.getElementById('main')?.focus() }}>{t('skip')}</a>
      <div className={css.shell}>
        <Sidebar project={project} current={current} onPalette={() => setPalette(true)} onProject={() => setProjectSheet(true)} />
        <div className={css.frame}>
          <TopBar project={project} current={current} onPalette={() => setPalette(true)}
            onScan={() => setScanSheet(true)} onBranches={() => setBranchSheet(true)} />
          <ScanBanner />
          <main id="main" tabIndex={-1} className={css.main}>
            {systemWorkspace ? <div className={css.workspace}>
              <div className={css.workspaceTabs}><WorkspaceReportPicker project={project} pathname={pathname} /><SystemViews current={systemView} persistent /></div>
              <div id="system-workspace-panel" role="tabpanel" aria-labelledby={`system-tab-${systemView}`}><Outlet /></div>
            </div> : <Outlet />}
          </main>
        </div>
      </div>
      <TabBar current={current} onMore={() => setMoreSheet(true)} />
      {paletteOpened && <Suspense fallback={null}><Palette isOpen={palette} onOpenChange={setPalette} /></Suspense>}
      <MoreSheet isOpen={moreSheet} onOpenChange={setMoreSheet} current={current} project={project}
        onPalette={() => { setMoreSheet(false); setPalette(true) }} onProject={() => { setMoreSheet(false); setProjectSheet(true) }} />
      <ProjectSheet isOpen={projectSheet} onOpenChange={setProjectSheet} project={project} />
      <ScanSheet isOpen={scanSheet} onOpenChange={setScanSheet} />
      <BranchSwitcher isOpen={branchSheet} onOpenChange={setBranchSheet} />
      <CommandHost />
    </BranchLiveProvider>
    </CommandProvider>
  )
}
