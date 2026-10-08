// studio/journeys.json and studio/hidden.json (contract v2, schemas/artifacts/studio-journeys.schema.json and
// studio-hidden.schema.json): the user's journeys between screens, and what the user sees against what runs unseen.
// Written by eaos/studio/journeys.py and hidden.py; the Studio only draws them.
import type { Measure } from './measure'

export type ScreenKind = 'page' | 'layout' | 'redirect' | 'fallback'
export type ScreenFlag = 'no_way_in' | 'dead_end' | 'duplicate' | 'broken_link'
export type LinkVia = 'link' | 'redirect' | 'navigate' | 'menu' | 'menu_of'
export type FolderOp = 'retain' | 'modify' | 'rebuild' | 'delete'

export interface Evidence { file: string | null; line?: number | null; fact?: string | null }
export interface LinkSite { file: string; line?: number | null; fact?: string | null; via: string; target?: string | null }

export interface Screen {
  id: string
  route: string
  title: string
  kind: ScreenKind
  file: string | null
  router: string
  line?: number | null
  fact: string | null
  declared?: Evidence[]
  group?: string
  feature?: string | null
  component?: string | null
  op: FolderOp | null
  target?: string | null
  decided: boolean
  start?: boolean
  depth?: number | null
  menu?: string | null
  flags: ScreenFlag[]
  twins?: string[]
  shots?: string[]
  col: number
  row: number
  x: number
  y: number
}

export interface Menu { id: string; router: string; scope: string[]; root: string | null; files?: string[]; links: number; col?: number; row?: number; x: number; y: number }

export interface JourneyEdge { from: string; to: string; via: LinkVia; back?: boolean; evidence: LinkSite[]; count: number; d: string }

export interface BrokenLink { from: string; file: string; line?: number | null; fact?: string | null; via?: string; target: string; dynamic?: boolean }

export interface Task {
  id: string
  name: { ar: string; en: string }
  kind: 'route' | 'dialog'
  screen: string | null
  file?: string | null
  path: string[]
  hosts?: string[]
  dead: boolean
  src: string
}

export interface MapGap { id: string; state: string; step: string; count: Measure; detail: { ar: string; en: string } }

export interface Journeys {
  counts: Record<'screens' | 'hidden_screens' | 'links' | 'link_sites' | 'broken' | 'no_way_in' | 'dead_ends' | 'duplicates' | 'tasks' |
    'unowned_links' | 'without_target' | 'shots', Measure> & { unowned_dead?: Measure }
  src: Record<string, string>
  grid: { cols: number; rows: number; col_w: number; row_h: number; box_w: number; box_h: number; pad: number; width: number; height: number }
  starts: string[]
  screens: Screen[]
  menus: Menu[]
  edges: JourneyEdge[]
  broken: BrokenLink[]
  unowned?: (LinkSite & { dead: boolean })[]
  relative?: BrokenLink[]
  groups?: { id: string; screens: string[] }[]
  tasks: Task[]
  capped?: Record<string, number>
  missing: MapGap[]
}

export type HiddenGroupId = 'triggers' | 'screens' | 'server' | 'writes' | 'outside' | 'config' | 'build' | 'dead'
export const HIDDEN_GROUPS: HiddenGroupId[] = ['triggers', 'screens', 'server', 'writes', 'outside', 'config', 'build', 'dead']

export interface HiddenItem {
  id: string
  group: HiddenGroupId
  kind: string
  name: string
  file: string | null
  line?: number | null
  fact: string | null
  files?: string[]
  detail?: string | null
  card?: string | null
  areas: string[]
  no_screen: boolean
  component?: string | null
}

export interface Hidden {
  counts: Record<string, Measure>
  src: Record<string, string>
  seen: { id: string; name: string; screens: string[]; routes?: string[]; dialogs: string[]; dialog_count: number }[]
  groups: { id: HiddenGroupId; count: Measure; kinds: Record<string, number>; no_screen: number; items: string[]; capped?: number }[]
  items: HiddenItem[]
  links: { from: string; to: HiddenGroupId; count: number; items: string[] }[]
  components: Record<string, Partial<Record<HiddenGroupId, number>>>
  missing: MapGap[]
}
