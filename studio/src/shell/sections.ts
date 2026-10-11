// The Studio's sections (DESIGN.md §3, D6): grouped in the desktop sidebar and, on the phone, in the "More" sheet in
// the same groups and order, five of them also on the phone's tab bar beside "More". A section whose page is not built
// yet is hidden unless the developer flag is on: the person never meets a "coming soon".
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
  /** On the phone's tab bar (exactly five, then "More") */
  tabbar: boolean
  built: boolean
  count?: (counts: Counts) => number
  /** The report section the count is read from: no count is shown while it is still being read */
  countFrom?: SectionName
  badge?: (counts: Counts) => number
}

export const SECTIONS: SectionDef[] = [
  { id: 'home', to: '/', icon: 'home', tab: 'home', nav: 'overview', tabbar: true, built: true },
  { id: 'system', to: '/system', icon: 'system', tab: 'system', nav: 'systemMap', group: 'groupCurrent', tabbar: true, built: true, count: (c) => c.components, countFrom: 'story' },
  { id: 'paths', to: '/system/paths', icon: 'pulse', tab: 'codePaths', nav: 'codePaths', group: 'groupCurrent', tabbar: false, built: true },
  { id: 'pipeline', to: '/system/pipeline', icon: 'flow', tab: 'pipeline', nav: 'pipeline', group: 'groupCurrent', tabbar: false, built: true },
  { id: 'functions', to: '/system/functions', icon: 'layers', tab: 'functions', nav: 'functions', group: 'groupCurrent', tabbar: false, built: true },
  { id: 'screens', to: '/screens', icon: 'eye', tab: 'screens', nav: 'screens', group: 'groupCurrent', tabbar: false, built: true },
  { id: 'problems', to: '/problems', icon: 'problems', tab: 'problems', nav: 'problems', group: 'groupProblems', tabbar: true, built: true, count: (c) => c.cards, countFrom: 'cards' },
  { id: 'change', to: '/change', icon: 'change', tab: 'change', nav: 'journeyAndPlan', group: 'groupChange', tabbar: true, built: true },
  { id: 'branches', to: '/branches', icon: 'branch', tab: 'branches', nav: 'branches', group: 'groupChange', tabbar: false, built: true },
  { id: 'scan', to: '/scan', icon: 'live', tab: 'liveCheck', nav: 'liveCheck', group: 'groupInbox', tabbar: false, built: true },
  { id: 'runs', to: '/runs', icon: 'pulse', tab: 'runs', nav: 'runs', group: 'groupInbox', tabbar: false, built: true },
  { id: 'decisions', to: '/decisions', icon: 'inbox', tab: 'decisions', nav: 'waitingForYou', group: 'groupInbox', tabbar: false, built: true, count: (c) => c.decisionsWaiting, countFrom: 'decisions', badge: (c) => c.decisionsWaiting },
  { id: 'library', to: '/library', icon: 'book', tab: 'documents', nav: 'documents', group: 'groupLibrary', tabbar: true, built: true, count: (c) => c.docs, countFrom: 'docs' },
  { id: 'history', to: '/history', icon: 'clock', tab: 'history', nav: 'history', group: 'groupLibrary', tabbar: false, built: true },
  { id: 'quality', to: '/quality', icon: 'verify', tab: 'eaosQuality', nav: 'eaosQuality', group: 'groupLibrary', tabbar: false, built: true },
]

export function visibleSections(dev: boolean): SectionDef[] {
  return SECTIONS.filter((section) => section.built || dev)
}

/** The sections in their sidebar groups: a run of sections with the same group heading, or one without a heading. */
export function grouped(sections: SectionDef[]): SectionDef[][] {
  const groups: SectionDef[][] = []
  for (const s of sections) {
    const last = groups[groups.length - 1]
    if (last && s.group && last[0].group === s.group) last.push(s)
    else groups.push([s])
  }
  return groups
}

/** The section a path belongs to ("/problems?card=…" → problems) */
export function sectionOf(pathname: string): SectionDef | undefined {
  const first = '/' + (pathname.split('/')[1] ?? '')
  const head = first === '/flows' || first === '/screens' ? '/system' : first === '/evidence' ? '/problems' : ['/plans', '/tasks', '/ops'].includes(first) ? '/change' : first   // a code path belongs to System, evidence to Problems
  return SECTIONS.find((section) => section.to === head) ?? (head === '/' ? SECTIONS[0] : undefined)
}
