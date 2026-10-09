// The sections a page shows first. public/boot.js reads these (its FIRST table, kept equal by stages.test.ts) for
// Home and Problems before the Studio's script arrives; every other section is read when something asks for it
// (context.tsx useSections), and a page waits, saying so, until every section it reads is there. A page that names
// no list waits for the whole report, as every page did before.
import type { SectionName } from './types'

/** What the frame shows on every page: the project's name and scan, its health, the inbox and the documents. */
export const SHELL_NEEDS = ['meta', 'head', 'health', 'decisions', 'docs'] as const satisfies readonly SectionName[]
/** The counts of problems and components (the frame's navigation, Home's tiles and links). They are read after the
 * first page is drawn, the largest of the frame's sections: until they arrive each count says it is being counted. */
export const COUNT_NEEDS = ['cards', 'story'] as const satisfies readonly SectionName[]
/** Home: the frame's sections and the territory map; its counts follow (COUNT_NEEDS). */
export const HOME_NEEDS = [...SHELL_NEEDS, 'system'] as const satisfies readonly SectionName[]
/** The Problems list: the cards, its facets read the plan's steps and the map's components. */
export const PROBLEMS_NEEDS = [...SHELL_NEEDS, ...COUNT_NEEDS, 'system', 'plans'] as const satisfies readonly SectionName[]
/** One card's detail: its evidence and the hidden lines of its excerpts. */
export const CARD_NEEDS = [...PROBLEMS_NEEDS, 'evidence', 'hidden'] as const satisfies readonly SectionName[]
/** The selection sheet groups cards by area, component, gap, operation and plan step. */
export const GROUP_NEEDS = ['cards', 'story', 'system', 'plans'] as const satisfies readonly SectionName[]
