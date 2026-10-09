// The sections a page shows first. public/boot.js reads these (its FIRST table, kept equal by stages.test.ts) for
// Home and Problems before the Studio's script arrives; every other section is read when something asks for it
// (context.tsx useSections), and a page waits, saying so, until every section it reads is there. A page that names
// no list waits for the whole report, as every page did before.
import type { SectionName } from './types'

/** What the frame shows on every page: the project's name and scan, the counts of its sections and the inbox. */
export const SHELL_NEEDS = ['meta', 'head', 'health', 'cards', 'decisions', 'docs', 'story'] as const satisfies readonly SectionName[]
/** Home: the frame's sections and the territory map. */
export const HOME_NEEDS = [...SHELL_NEEDS, 'system'] as const satisfies readonly SectionName[]
/** The Problems list: its facets read the plan's steps and the map's components. */
export const PROBLEMS_NEEDS = [...SHELL_NEEDS, 'system', 'plans'] as const satisfies readonly SectionName[]
/** One card's detail: its evidence and the hidden lines of its excerpts. */
export const CARD_NEEDS = [...PROBLEMS_NEEDS, 'evidence', 'hidden'] as const satisfies readonly SectionName[]
/** The selection sheet groups cards by area, component, gap, operation and plan step. */
export const GROUP_NEEDS = ['cards', 'story', 'system', 'plans'] as const satisfies readonly SectionName[]
