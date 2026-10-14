// The Studio's sections (DESIGN.md §3, D6): five on the phone's tab bar, grouped in the desktop sidebar.
import type { Counts } from '../data/context'
import type { SectionName } from '../data/types'
import type { WordKey } from '../i18n/catalog'
import type { IconName } from '../components/Icon'

export interface SectionDef {
  id: string
  to: string
  icon: IconName
  /** The tab bar's word, and the sidebar's word for the same place */
  tab: WordKey
  nav: WordKey
  /** The sidebar group heading, if any */
  group?: WordKey
  /** On the phone's tab bar (exactly five) */
  tabbar: boolean
  count?: (counts: Counts) => number
  /** The report section the count is read from: no count is shown while it is still being read */
  countFrom?: SectionName
  badge?: (counts: Counts) => number
}

export const SECTIONS: SectionDef[] = [
  { id: 'home', to: '/', icon: 'home', tab: 'home', nav: 'overview', tabbar: true },
  { id: 'system', to: '/system', icon: 'system', tab: 'system', nav: 'systemMap', group: 'groupCurrent', tabbar: true, count: (c) => c.components, countFrom: 'story' },
  { id: 'paths', to: '/system/paths', icon: 'pulse', tab: 'codePaths', nav: 'codePaths', group: 'groupCurrent', tabbar: false },
  { id: 'pipeline', to: '/system/pipeline', icon: 'flow', tab: 'pipeline', nav: 'pipeline', group: 'groupCurrent', tabbar: false },
  { id: 'functions', to: '/system/functions', icon: 'layers', tab: 'functions', nav: 'functions', group: 'groupCurrent', tabbar: false },
  { id: 'screens', to: '/screens', icon: 'eye', tab: 'screens', nav: 'screens', group: 'groupCurrent', tabbar: false },
  { id: 'problems', to: '/problems', icon: 'problems', tab: 'problems', nav: 'problems', group: 'groupProblems', tabbar: true, count: (c) => c.cards, countFrom: 'cards' },
  { id: 'change', to: '/change', icon: 'change', tab: 'change', nav: 'journeyAndPlan', group: 'groupChange', tabbar: true },
  { id: 'branches', to: '/branches', icon: 'branch', tab: 'branches', nav: 'branches', group: 'groupChange', tabbar: false },
  { id: 'scan', to: '/scan', icon: 'live', tab: 'liveCheck', nav: 'liveCheck', group: 'groupInbox', tabbar: false },
  { id: 'runs', to: '/runs', icon: 'pulse', tab: 'runs', nav: 'runs', group: 'groupInbox', tabbar: false },
  { id: 'assistant', to: '/assistant', icon: 'assistant', tab: 'assistant', nav: 'assistant', group: 'groupInbox', tabbar: false },
  { id: 'decisions', to: '/decisions', icon: 'inbox', tab: 'decisions', nav: 'waitingForYou', group: 'groupInbox', tabbar: true, count: (c) => c.decisionsWaiting, countFrom: 'decisions', badge: (c) => c.decisionsWaiting },
  { id: 'library', to: '/library', icon: 'book', tab: 'library', nav: 'documents', group: 'groupLibrary', tabbar: false, count: (c) => c.docs, countFrom: 'docs' },
  { id: 'history', to: '/history', icon: 'clock', tab: 'history', nav: 'history', group: 'groupLibrary', tabbar: false },
]

/** Pages under another section's address: a code path belongs to Code paths, evidence to Problems, the tools to the
 * live check, a plan's pages to Change. */
const UNDER: Record<string, string> = { '/flows': '/system/paths', '/evidence': '/problems', '/tools': '/scan', '/plans': '/change', '/tasks': '/change', '/ops': '/change' }

/** The most specific section a path belongs to ("/system/paths" → paths, "/problems?card=…" → problems) */
export function sectionOf(pathname: string): SectionDef | undefined {
  const path = UNDER['/' + (pathname.split('/')[1] ?? '')] ?? pathname
  if (path === '/') return SECTIONS[0]
  return SECTIONS.filter((s) => s.to !== '/' && (path === s.to || path.startsWith(s.to + '/'))).sort((a, b) => b.to.length - a.to.length)[0]
}

/** The phone tab a section shows under: its own, else the tab of its sidebar group. */
export function tabOf(section?: SectionDef): SectionDef | undefined {
  return section?.tabbar ? section : SECTIONS.find((s) => s.tabbar && s.group && s.group === section?.group)
}
