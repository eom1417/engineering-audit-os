// The Studio's sections (docs/STUDIO-REDESIGN.md §3): Overview, Checks, Problems, Fixes and System (its maps folded under
// it, shell/Shell.tsx), then the footer's places. The phone's tab bar shows the first four and More.
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
  /** Reached from the top bar (Waiting for you), not from the sidebar */
  topbar?: boolean
  /** On the phone's tab bar (four, then More) */
  tabbar: boolean
  count?: (counts: Counts) => number
  /** The report section the count is read from: no count is shown while it is still being read */
  countFrom?: SectionName
  badge?: (counts: Counts) => number
}

export const SECTIONS: SectionDef[] = [
  { id: 'home', to: '/', icon: 'home', tab: 'home', nav: 'overview', tabbar: true },
  { id: 'checks', to: '/checks', icon: 'live', tab: 'checks', nav: 'checks', tabbar: true },
  { id: 'problems', to: '/problems', icon: 'problems', tab: 'problems', nav: 'problems', tabbar: true, count: (c) => c.cards, countFrom: 'cards' },
  { id: 'change', to: '/change', icon: 'change', tab: 'fixes', nav: 'fixes', tabbar: true },
  { id: 'system', to: '/system', icon: 'system', tab: 'system', nav: 'system', tabbar: false, count: (c) => c.components, countFrom: 'story' },
  { id: 'library', to: '/library', icon: 'book', tab: 'library', nav: 'documents', group: 'groupFooter', tabbar: false, count: (c) => c.docs, countFrom: 'docs' },
  { id: 'decisions', to: '/decisions', icon: 'inbox', tab: 'decisions', nav: 'waitingForYou', topbar: true, tabbar: false },
  { id: 'settings', to: '/settings', icon: 'settings', tab: 'settings', nav: 'settings', group: 'groupFooter', tabbar: false },
]

/** Pages under another section's address: the System maps' pages to System, evidence to Problems, a run and a past
 * check to Checks, a plan's pages and the branches to Fixes, the sign-in page to Waiting for you. */
const UNDER: Record<string, string> = { '/flows': '/system', '/screens': '/system', '/evidence': '/problems', '/runs': '/checks', '/history': '/checks',
  '/plans': '/change', '/tasks': '/change', '/ops': '/change', '/branches': '/change', '/sign-in': '/decisions' }

/** The most specific section a path belongs to ("/system/paths" → paths, "/problems?card=…" → problems) */
export function sectionOf(pathname: string): SectionDef | undefined {
  const under = Object.keys(UNDER).find((prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`))
  const path = under ? UNDER[under] : pathname
  if (path === '/') return SECTIONS[0]
  return SECTIONS.filter((s) => s.to !== '/' && (path === s.to || path.startsWith(s.to + '/'))).sort((a, b) => b.to.length - a.to.length)[0]
}

/** The phone tab a section shows under: its own, else none (it is reached from the tab bar's More). */
export function tabOf(section?: SectionDef): SectionDef | undefined {
  return section?.tabbar ? section : undefined
}
