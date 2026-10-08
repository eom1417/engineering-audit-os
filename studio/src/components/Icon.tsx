// The Studio's icons: Lucide drawn at 16 px with a 1.5 stroke, like the design's sprite. Only icons that point
// (chevrons, back, arrows) mirror in right-to-left; the rest never do.
import {
  ArrowLeftRight, ArrowRight, BookOpen, Check, ChevronDown, ChevronLeft, ChevronRight, Circle, Clock, Copy, Ellipsis,
  FileText, Folder, Globe, House, Inbox, LayoutGrid, Moon, Pencil, Plus, RefreshCw, Search, Sun, Trash2,
  TriangleAlert, Workflow, X, GitMerge, Activity, Command, Wrench, ShieldCheck, Lightbulb, ListOrdered, Play, Pause, Square,
  RotateCcw, GitBranch, ArrowUp, ArrowDown, SquareTerminal, Layers, CircleCheck, CircleX, FilePen, MessageSquare, Eye, Waypoints,
  type LucideIcon,
} from 'lucide-react'

const ICONS = {
  home: House, system: Workflow, problems: TriangleAlert, change: ArrowLeftRight, inbox: Inbox, search: Search,
  chevron: ChevronRight, chevronDown: ChevronDown, back: ChevronLeft, arrow: ArrowRight, copy: Copy, check: Check,
  more: Ellipsis, sun: Sun, moon: Moon, globe: Globe, file: FileText, folder: Folder, book: BookOpen, clock: Clock,
  x: X, pulse: Activity, command: Command, gallery: LayoutGrid, flow: Waypoints,
  fix: Wrench, verify: ShieldCheck, explain: Lightbulb, plan: ListOrdered, play: Play, pause: Pause, stop: Square, retry: RotateCcw,
  branch: GitBranch, up: ArrowUp, down: ArrowDown, terminal: SquareTerminal, layers: Layers, pass: CircleCheck, fail: CircleX,
  edit: FilePen, say: MessageSquare, eye: Eye,
  opKeep: Circle, opModify: Pencil, opRebuild: RefreshCw, opDelete: Trash2, opMerge: GitMerge, opIntroduce: Plus,
} satisfies Record<string, LucideIcon>

export type IconName = keyof typeof ICONS
const MIRRORED: ReadonlySet<IconName> = new Set(['chevron', 'back', 'arrow'])

export function Icon({ name, size = 16, className }: { name: IconName; size?: number; className?: string }) {
  const Drawn = ICONS[name]
  const classes = [MIRRORED.has(name) ? 'mirror' : '', className].filter(Boolean).join(' ') || undefined
  return <Drawn aria-hidden="true" focusable="false" size={size} strokeWidth={1.5} absoluteStrokeWidth className={classes} />
}
