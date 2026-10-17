// The frame every page sits in (DESIGN.md §3, §4). Phone (< 768): top bar, content, a fixed tab bar with the five
// sections, sheets from the bottom, pages pushed onto a stack with a back button. Tablet (768–1199): a 56px rail.
// Desktop (≥ 1200): the 232px sidebar, breadcrumb top bar, Cmd/Ctrl-K palette, split panes and inspector.
import { Outlet, useRouterState } from '@tanstack/react-router'
import { lazy, Suspense, useEffect, useMemo, useState } from 'react'
import { Button as AriaButton } from 'react-aria-components'
import { IconButton } from '../components/Button'
import { Badge, Chip, FreshnessChip } from '../components/Chip'
import { Go } from '../components/Go'
import { Icon } from '../components/Icon'
import { Sheet, SheetLead, SheetSub } from '../components/Sheet'
import { Panel, RowButton, RowLink, Skeleton, StateMessage } from '../components/Panel'
import { BranchLiveProvider, useFreshView } from '../branches/live'
import { ScanSheet } from '../branches/ScanSheet'
import { BranchChip, BranchSwitcher } from '../branches/Switcher'
import { CommandProvider } from '../command/command'
import { CommandHost } from '../command/CommandHost'
import { ChatDock } from '../chat/ChatDock'
import { useActions } from '../data/actions/store'
import { TERMINAL, type ProjectRow } from '../data/actions/types'
import { counts, useLoaded, useSections, useStudio, type Counts } from '../data/context'
import { COUNT_NEEDS } from '../data/stages'
import { usePrefs } from '../i18n/prefs'
import { Id, N } from '../i18n/text'
import { useChrome } from './chrome'
import { useOpenedOnce, whenIdle } from './later'
import { LanguageAndTheme, ProjectFacts, TimeZoneSetting } from './Settings'
import { NoKeyNotice } from './Layout'
import { ScanBanner } from './ScanBanner'
import { useAwaitingApproval, useWaitingDecisions } from './waiting'
import { SECTIONS, sectionOf, tabOf, type SectionDef } from './sections'
import css from './Shell.module.css'
import { SYSTEM_VIEWS, SystemViews } from '../pages/system/SystemViews'
import { useJourneyWords } from '../pages/system/words'

// The palette is its own chunk (shell/later.ts): read once the report is drawn, drawn from its first opening
const loadPalette = () => import('./Palette')
const Palette = lazy(() => loadPalette().then((module) => ({ default: module.Palette })))

function useCounts(): Counts | null {
  const data = useStudio()
  const waiting = useWaitingDecisions(data)
  return useMemo(() => (data ? { ...counts(data), decisionsWaiting: waiting.length } : null), [data, waiting])
}

/** The command centre's counts beside the report's: questions from runs join the inbox, and runs that are not over. */
function useLiveCounts(): Record<string, number> {
  const { questions, runs } = useActions()
  return { decisions: questions.length, runs: runs.filter((run) => !TERMINAL.includes(run.state)).length }
}

/** Everything that waits for the person, in one count: the report's questions, the runs' questions, the branches
 * waiting for their approval and the sign-in a check waits for. */
function useWaitingCount(): number {
  const c = useCounts()
  const pending = useStudio()?.pending ?? []
  const live = useLiveCounts()
  const approvals = useAwaitingApproval().length
  const signIn = useActions().signIn?.asked ? 1 : 0
  return (c && !pending.includes('decisions') ? c.decisionsWaiting : 0) + (live.decisions ?? 0) + approvals + signIn
}

/** The top bar's way to what waits for the person, with its count: one click from anywhere, on the phone too. */
function WaitingButton({ current }: { current?: SectionDef }) {
  const { t } = usePrefs()
  const n = useWaitingCount()
  return (
    <Go to="/decisions" className={css.waiting} current={current?.id === 'decisions'} label={n ? `${t('waitingForYou')} (${n})` : t('waitingForYou')}>
      <Icon name="inbox" /><span className={css.waitingWord}>{t('waitingForYou')}</span>{n > 0 && <Badge count={n} />}
    </Go>
  )
}

/** System and its maps: the maps stay folded until the person opens them or is on one of them, by category. */
function SystemNav({ section, view, item }: { section: SectionDef; view: string | null; item: (s: SectionDef) => React.ReactNode }) {
  const { t } = usePrefs()
  const w = useJourneyWords()
  const inside = view !== null
  const [open, setOpen] = useState(inside)
  useEffect(() => { if (inside) setOpen(true) }, [inside])
  const categories = [...new Set(SYSTEM_VIEWS.map((v) => v.category))].map((category) => SYSTEM_VIEWS.filter((v) => v.category === category))
  return (
    <div className={css.navFold}>
      <div className={css.navFoldHead}>
        {item(section)}
        <AriaButton className={css.navFoldToggle} onPress={() => setOpen(!open)} aria-expanded={open} aria-controls="nav-system"
          aria-label={t(open ? 'foldSystem' : 'unfoldSystem')}><Icon name={open ? 'chevronUp' : 'chevronDown'} /></AriaButton>
      </div>
      {open && <div id="nav-system" className={css.navSub}>
        {categories.map((views) => (
          <div key={views[0].category} className={css.navSubGroup}>
            {views.length > 1 && <div className={css.navSubTitle}>{t(views[0].category)}</div>}
            {views.map((v) => <Go key={v.id} to={v.to} search={v.search} className={css.navSubItem} current={view === v.id}>{w(v.word)}</Go>)}
          </div>
        ))}
      </div>}
    </div>
  )
}

function Sidebar({ project, current, view, onPalette, onProject }:
  { project: string; current?: SectionDef; view: string | null; onPalette: () => void; onProject: () => void }) {
  const { t } = usePrefs()
  const c = useCounts()
  const data = useStudio()
  const live = useLiveCounts()
  const pending = data?.pending ?? []
  const item = (s: SectionDef) => (
    <Go key={s.id} to={s.to} className={css.navItem} current={current?.id === s.id && (s.id !== 'system' || view === 'map')} label={t(s.nav)}>
      <Icon name={s.icon} />
      <span className={css.navLabel}>{t(s.nav)}</span>
      {c && s.count && !(s.countFrom && pending.includes(s.countFrom)) && <N value={s.count(c) + (live[s.id] ?? 0)} className={css.navCount} />}
      {!s.count && live[s.id] ? <N value={live[s.id]} className={css.navCount} /> : null}
    </Go>
  )
  const main = SECTIONS.filter((s) => !s.group && !s.topbar)
  const footer = SECTIONS.filter((s) => s.group)
  return (
    <aside className={css.sidebar} aria-label={t('navigation')}>
      <AriaButton className={css.proj} onPress={onProject} data-open="project" aria-label={`${project}: ${t('projectAndDisplay')}`}>
        <span className={css.projMark} aria-hidden="true">{project.slice(0, 1).toUpperCase()}</span>
        <span className={css.projText}><span className={css.projName} title={project} dir="auto" data-truncate>{project}</span><span className={css.projSub}>{t('studio')}</span></span>
        <Icon name="chevronDown" className={css.projChev} />
      </AriaButton>
      <AriaButton className={css.navSearch} onPress={onPalette} aria-label={t('searchCommands')}>
        <Icon name="search" /><span>{t('searchCommands')}</span><kbd>⌘K</kbd>
      </AriaButton>
      <nav className={css.nav} aria-label={t('navigation')}>
        {main.map((s) => s.id === 'system' ? <SystemNav key={s.id} section={s} view={view} item={item} /> : item(s))}
        <div className={css.navGroup}>
          <div className={css.navGroupTitle}>{t('groupFooter')}</div>
          {footer.map(item)}
        </div>
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

/** Four sections and More: More opens the sheet with System's maps, the footer's places and the display. */
/** Four sections and More: More opens the sheet with System's maps, the footer's places and the display. */
function TabBar({ current, onMore }: { current?: SectionDef; onMore: () => void }) {
  const { t } = usePrefs()
  const tab = tabOf(current)
  return (
    <nav className={css.tabbar} aria-label={t('mainTabs')}>
      {SECTIONS.filter((s) => s.tabbar).map((s) => (
        <Go key={s.id} to={s.to} className={css.tab} current={tab?.id === s.id}>
          <span className={css.tabIcon}><Icon name={s.icon} size={22} /></span>
          <span className={css.tabLabel}>{t(s.tab)}</span>
        </Go>
      ))}
      <AriaButton className={css.tab} onPress={onMore} data-current={current && !tab && !current.topbar ? '' : undefined} data-open="more">
        <span className={css.tabIcon}><Icon name="more" size={22} /></span>
        <span className={css.tabLabel}>{t('more')}</span>
      </AriaButton>
    </nav>
  )
}

/** The phone's More: System's maps by category, then the footer's places, then the project and its display. */
function MoreSheet({ isOpen, onOpenChange, project }: { isOpen: boolean; onOpenChange: (open: boolean) => void; project: string }) {
  const { t } = usePrefs()
  const w = useJourneyWords()
  const close = () => onOpenChange(false)
  const categories = [...new Set(SYSTEM_VIEWS.map((v) => v.category))].map((category) => SYSTEM_VIEWS.filter((v) => v.category === category))
  return (
    <Sheet isOpen={isOpen} onOpenChange={onOpenChange} title={t('more')}>
      <SheetSub>{t('system')}</SheetSub>
      {categories.map((views) => (
        <div key={views[0].category} className={css.moreGroup} onClick={close}>
          {views.length > 1 && <div className={css.navSubTitle}>{t(views[0].category)}</div>}
          {views.map((v) => <Go key={v.id} to={v.to} search={v.search} className={css.moreItem}>{w(v.word)}</Go>)}
        </div>
      ))}
      <SheetSub>{t('groupFooter')}</SheetSub>
      <div className={css.moreGroup} onClick={close}>
        {SECTIONS.filter((s) => s.group).map((s) => <Go key={s.id} to={s.to} className={css.moreItem}><Icon name={s.icon} />{t(s.nav)}</Go>)}
      </div>
      <SheetSub>{project}</SheetSub>
      <ProjectFacts />
      <div className={css.rowSet}><LanguageAndTheme comfortable /></div>
      <TimeZoneSetting />
    </Sheet>
  )
}

function Freshness({ onScan }: { onScan: () => void }) {
  const loaded = useLoaded()
  const view = useFreshView()
  if (loaded.kind !== 'ready' || !view) return null
  return <span className={css.freshChip} data-live={view.live ? '' : undefined}><FreshnessChip freshness={view.state} count={view.count} onPress={onScan} /></span>
}

function TopBar({ project, current, onPalette, onProject, onScan, onBranches }:
  { project: string; current?: SectionDef; onPalette: () => void; onProject: () => void; onScan: () => void; onBranches: () => void }) {
  const { t } = usePrefs()
  const chrome = useChrome()
  const systemWorkspace = useRouterState({ select: (s) => s.location.pathname.startsWith('/system') || s.location.pathname.startsWith('/screens') || s.location.pathname.startsWith('/flows') })
  const back = systemWorkspace ? undefined : chrome.back
  const sectionTitle = t((current ?? SECTIONS[0]).nav)
  return (
    <header className={css.topbar}>
      <div className={css.desk}>
        <nav className={css.crumbs} aria-label={t('breadcrumb')}>
          <Go to="/" className={css.crumb}>{project}</Go>
          {current?.id !== 'home' && <><span className={css.crumbSep} aria-hidden="true">/</span>
            {back ? <Go to={back.to} search={back.search} className={css.crumb}>{sectionTitle}</Go> : <span aria-current="page">{sectionTitle}</span>}</>}
          {back && chrome.title !== sectionTitle && <><span className={css.crumbSep} aria-hidden="true">/</span><span aria-current="page" className={css.crumbLast} title={chrome.title} data-truncate>{chrome.title}</span></>}
        </nav>
        <div className={css.deskEnd}>
          <BranchChip onPress={onBranches} />
          <Freshness onScan={onScan} />
          <WaitingButton current={current} />
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
        <WaitingButton current={current} />
        <IconButton icon="search" label={t('search')} onPress={onPalette} />
        <IconButton icon="more" label={t('projectAndDisplay')} onPress={onProject} data-open="project" />
      </div>
    </header>
  )
}

/** The project button's sheet: every project EAOS knows on this computer, each opening its own Studio (a server of its
 * own, so one project never shows another's data), then the way to Settings. A static copy shows its project's facts. */
function ProjectSheet({ isOpen, onOpenChange, project }: { isOpen: boolean; onOpenChange: (open: boolean) => void; project: string }) {
  const { t, date } = usePrefs()
  const { client } = useActions()
  const [rows, setRows] = useState<ProjectRow[] | null>(null)
  const [opening, setOpening] = useState<string | null>(null)
  const [problem, setProblem] = useState<string | null>(null)
  useEffect(() => {
    if (!isOpen || !client?.projects) return
    setProblem(null)
    client.projects().then(setRows, () => setRows([]))
  }, [isOpen, client])
  const open = async (row: ProjectRow) => {
    if (row.current || !client?.openProject) { onOpenChange(false); return }
    setOpening(row.workspace)
    try { window.location.assign((await client.openProject(row.workspace)).studio) } catch (error) {
      setProblem(error instanceof Error ? error.message : String(error)); setOpening(null)
    }
  }
  return (
    <Sheet isOpen={isOpen} onOpenChange={onOpenChange} title={client?.projects ? t('projects') : project}>
      {client?.projects ? (
        <>
          <SheetLead>{t('projectsLead')}</SheetLead>
          {rows === null ? <Skeleton label={t('loading')} /> : (
            <Panel><ul>{rows.map((row) => (
              <li key={row.workspace}>
                <RowButton icon="folder" onPress={() => void open(row)} hook={`project:${row.workspace}`}
                  title={<span dir="auto">{row.name}</span>}
                  sub={<>{row.score === null ? t('notMeasured') : <><N value={Math.round(row.score * 100)} />/100</>}{row.checked ? <> · {date(row.checked, false)}</> : null}</>}
                  end={row.current ? <Chip tone="accent">{t('thisProject')}</Chip> : opening === row.workspace ? t('opening') : undefined} />
              </li>
            ))}</ul></Panel>
          )}
          {problem && <StateMessage kind="error" title={t('openProjectFailed')} sub={problem} />}
        </>
      ) : <ProjectFacts />}
      <div onClick={() => onOpenChange(false)}><Panel><RowLink to="/settings" icon="settings" title={t('settings')} /></Panel></div>
    </Sheet>
  )
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
  const [moreSheet, setMoreSheet] = useState(false)
  const [projectSheet, setProjectSheet] = useState(false)
  const [scanSheet, setScanSheet] = useState(false)
  const [branchSheet, setBranchSheet] = useState(false)
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
        <Sidebar project={project} current={current} view={systemWorkspace ? systemView : null} onPalette={() => setPalette(true)} onProject={() => setProjectSheet(true)} />
        <div className={css.frame}>
          <TopBar project={project} current={current} onPalette={() => setPalette(true)} onProject={() => setProjectSheet(true)}
            onScan={() => setScanSheet(true)} onBranches={() => setBranchSheet(true)} />
          <ScanBanner />
          <main id="main" tabIndex={-1} className={css.main}>
            <NoKeyNotice />
            {systemWorkspace ? <div className={css.workspace}>
              <div className={css.workspaceTabs}><WorkspaceReportPicker project={project} pathname={pathname} /><SystemViews current={systemView} persistent /></div>
              <div id="system-workspace-panel" role="tabpanel" aria-labelledby={`system-tab-${systemView}`}><Outlet /></div>
            </div> : <Outlet />}
          </main>
        </div>
      </div>
      <TabBar current={current} onMore={() => setMoreSheet(true)} />
      <MoreSheet isOpen={moreSheet} onOpenChange={setMoreSheet} project={project} />
      {paletteOpened && <Suspense fallback={null}><Palette isOpen={palette} onOpenChange={setPalette} /></Suspense>}
      <ProjectSheet isOpen={projectSheet} onOpenChange={setProjectSheet} project={project} />
      <ScanSheet isOpen={scanSheet} onOpenChange={setScanSheet} />
      <BranchSwitcher isOpen={branchSheet} onOpenChange={setBranchSheet} />
      <CommandHost />
      <ChatDock />
    </BranchLiveProvider>
    </CommandProvider>
  )
}
