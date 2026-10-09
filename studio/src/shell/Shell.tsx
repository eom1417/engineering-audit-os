// The frame every page sits in (DESIGN.md §3, §4). Phone (< 768): top bar, content, a fixed tab bar with the five
// sections, sheets from the bottom, pages pushed onto a stack with a back button. Tablet (768–1199): a 56px rail.
// Desktop (≥ 1200): the 232px sidebar, breadcrumb top bar, Cmd/Ctrl-K palette, split panes and inspector.
import { Outlet, useRouterState } from '@tanstack/react-router'
import { useEffect, useMemo, useState } from 'react'
import { Button as AriaButton } from 'react-aria-components'
import { IconButton } from '../components/Button'
import { Badge, FreshnessChip } from '../components/Chip'
import { Segmented } from '../components/Controls'
import { Go } from '../components/Go'
import { Icon } from '../components/Icon'
import { Props } from '../components/Panel'
import { Sheet, SheetLead, SheetSub } from '../components/Sheet'
import { CopyRequestButton } from '../components/Button'
import { CommandProvider } from '../command/command'
import { CommandHost } from '../command/CommandHost'
import { useActions } from '../data/actions/store'
import { counts, useLoaded, useStudio, type Counts } from '../data/context'
import type { Freshness } from '../data/types'
import { usePrefs } from '../i18n/prefs'
import { Id, N } from '../i18n/text'
import { useChrome } from './chrome'
import { Palette } from './Palette'
import { sectionOf, visibleSections, type SectionDef } from './sections'
import css from './Shell.module.css'
import { SystemViews } from '../pages/system/SystemViews'

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

function Sidebar({ project, current, onPalette, onProject }: { project: string; current?: SectionDef; onPalette: () => void; onProject: () => void }) {
  const { t, dev } = usePrefs()
  const c = useCounts()
  const data = useStudio()
  const sections = visibleSections(dev)
  const live = useLiveCounts()
  const item = (s: SectionDef) => (
    <Go key={s.id} to={s.to} className={css.navItem} current={current?.id === s.id} label={t(s.nav)}>
      <Icon name={s.icon} />
      <span className={css.navLabel}>{t(s.nav)}</span>
      {c && s.count && <N value={s.count(c) + (live[s.id] ?? 0)} className={css.navCount} />}
      {!s.count && live[s.id] ? <N value={live[s.id]} className={css.navCount} /> : null}
    </Go>
  )
  const groups: SectionDef[][] = []
  for (const s of sections) {
    const last = groups[groups.length - 1]
    if (last && s.group && last[0].group === s.group) last.push(s)
    else groups.push([s])
  }
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

function TabBar({ current }: { current?: SectionDef }) {
  const { t } = usePrefs()
  const c = useCounts()
  const live = useLiveCounts()
  return (
    <nav className={css.tabbar} aria-label={t('mainTabs')}>
      {visibleSections(false).filter((s) => s.tabbar).map((s) => {
        const badge = (c && s.badge ? s.badge(c) : 0) + (s.badge ? live[s.id] ?? 0 : 0)
        return (
          <Go key={s.id} to={s.to} className={css.tab} current={current?.id === s.id}>
            <span className={css.tabIcon}><Icon name={s.icon} size={22} />{badge > 0 && <span className={css.tabBadge}><Badge count={badge} /></span>}</span>
            <span className={css.tabLabel}>{t(s.tab)}{badge > 0 && <span className="sr"> ({badge})</span>}</span>
          </Go>
        )
      })}
    </nav>
  )
}

function TopBar({ project, current, freshness, onPalette, onProject, onScan }:
  { project: string; current?: SectionDef; freshness: Freshness | null; onPalette: () => void; onProject: () => void; onScan: () => void }) {
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
          {freshness && <FreshnessChip freshness={freshness} onPress={onScan} />}
          <AriaButton className={css.cmdk} onPress={onPalette} aria-label={t('searchEverything')} data-truncate>
            <Icon name="search" /><span>{t('searchEverything')}</span><kbd>⌘K</kbd>
          </AriaButton>
        </div>
      </div>
      <div className={css.phone}>
        {back
          ? <Go to={back.to} search={back.search} className={css.back}><Icon name="back" size={20} /><span>{back.label}</span></Go>
          : freshness && <FreshnessChip freshness={freshness} onPress={onScan} />}
        <span className={css.phoneSpacer} />
        <IconButton icon="search" label={t('search')} onPress={onPalette} />
        <IconButton icon="more" label={t('projectAndDisplay')} onPress={onProject} data-open="project" />
      </div>
    </header>
  )
}

function ProjectSheet({ isOpen, onOpenChange, project }: { isOpen: boolean; onOpenChange: (open: boolean) => void; project: string }) {
  const { t, date } = usePrefs()
  const data = useStudio()
  const rows: [React.ReactNode, React.ReactNode, boolean?][] = []
  if (data?.meta) {
    rows.push([t('files'), data.meta.files.value === null ? t('notMeasured') : <N value={data.meta.files.value} />, data.meta.files.value === null])
    rows.push([t('lines'), data.meta.lines.value === null ? t('notMeasured') : <N value={data.meta.lines.value} />, data.meta.lines.value === null])
    rows.push([t('languages'), <bdi dir="ltr">{data.meta.languages.map((l) => `${l.name} ${Math.round(l.share * 100)}%`).join(', ')}</bdi>])
  }
  if (data) {
    rows.push([t('scanned'), data.manifest.scanned.at ? date(data.manifest.scanned.at) : t('notRecorded'), !data.manifest.scanned.at])
    rows.push([t('branch'), data.manifest.scanned.branch ? <Id value={data.manifest.scanned.branch} /> : t('notRecorded'), !data.manifest.scanned.branch])
    rows.push([t('eaosVersion'), <Id value={data.manifest.built.version} />])
  }
  return (
    <Sheet isOpen={isOpen} onOpenChange={onOpenChange} title={project}>
      {rows.length > 0 && <Props rows={rows} />}
      <SheetSub>{t('display')}</SheetSub>
      <div className={css.rowSet}><LanguageAndTheme comfortable /></div>
    </Sheet>
  )
}

const FRESH_LEAD = { fresh: 'freshFreshLead', branch_moved: 'freshMovedLead', eaos_updated: 'freshUpdatedLead', unknown: 'freshUnknownLead' } as const

function ScanSheet({ isOpen, onOpenChange }: { isOpen: boolean; onOpenChange: (open: boolean) => void }) {
  const { t, date, lang } = usePrefs()
  const data = useStudio()
  if (!data) return null
  const freshness = data.head?.freshness ?? 'unknown'
  const { scanned, built, project } = data.manifest
  const request = lang === 'ar'
    ? `أعد فحص ${project.name} بأداة audit من EAOS على الفرع الحالي.`
    : `Run the EAOS audit tool on ${project.name} again, on the current branch.`
  return (
    <Sheet isOpen={isOpen} onOpenChange={onOpenChange} title={t('isScanCurrent')}>
      <SheetLead>{t(FRESH_LEAD[freshness])}</SheetLead>
      <Props rows={[
        [t('scanned'), scanned.at ? date(scanned.at) : t('notRecorded'), !scanned.at],
        [t('reportBuilt'), date(built.built)],
        [t('branch'), scanned.branch ? <Id value={scanned.branch} /> : t('notRecorded'), !scanned.branch],
        ['Commit', scanned.commit ? <Id value={scanned.commit.slice(0, 12)} /> : t('notRecorded'), !scanned.commit],
      ]} />
      {freshness !== 'fresh' && (
        <div className={css.req}>
          <p>{t('askRecheck')}</p>
          <CopyRequestButton request={request} tool="audit" label={t('copyShort')} />
        </div>
      )}
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
  const loaded = useLoaded()
  const data = useStudio()
  const pathname = useRouterState({ select: (s) => s.location.pathname })
  const systemWorkspace = pathname.startsWith('/system') || pathname.startsWith('/screens') || pathname.startsWith('/flows')
  // Only the lens: selecting the whole search object would draw the frame again on every keystroke of a page's search
  const lens = useRouterState({ select: (s) => (s.location.search as { lens?: string }).lens })
  const systemView = pathname === '/system' ? (lens === 'infra' ? 'infra' : 'map') : pathname.startsWith('/screens') ? 'screens' : pathname.startsWith('/flows') ? 'paths' : pathname.startsWith('/system/f/') ? 'functions' : pathname.split('/')[2] ?? 'map'
  const current = pathname.startsWith('/_') ? undefined : sectionOf(pathname)
  const [palette, setPalette] = useState(false)
  const [projectSheet, setProjectSheet] = useState(false)
  const [scanSheet, setScanSheet] = useState(false)
  const project = data?.manifest.project.name ?? t('studio')

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
      <a className={css.skip} href="#main" onClick={(e) => { e.preventDefault(); document.getElementById('main')?.focus() }}>{t('skip')}</a>
      <div className={css.shell}>
        <Sidebar project={project} current={current} onPalette={() => setPalette(true)} onProject={() => setProjectSheet(true)} />
        <div className={css.frame}>
          <TopBar project={project} current={current} freshness={loaded.kind === 'ready' ? (data?.head?.freshness ?? 'unknown') : null}
            onPalette={() => setPalette(true)} onProject={() => setProjectSheet(true)} onScan={() => setScanSheet(true)} />
          <main id="main" tabIndex={-1} className={css.main}>
            {systemWorkspace ? <div className={css.workspace}>
              <div className={css.workspaceTabs}><WorkspaceReportPicker project={project} pathname={pathname} /><SystemViews current={systemView} persistent /></div>
              <div id="system-workspace-panel" role="tabpanel" aria-labelledby={`system-tab-${systemView}`}><Outlet /></div>
            </div> : <Outlet />}
          </main>
        </div>
      </div>
      <TabBar current={current} />
      <Palette isOpen={palette} onOpenChange={setPalette} />
      <ProjectSheet isOpen={projectSheet} onOpenChange={setProjectSheet} project={project} />
      <ScanSheet isOpen={scanSheet} onOpenChange={setScanSheet} />
      <CommandHost />
    </CommandProvider>
  )
}
