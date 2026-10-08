// The Studio's search index (MiniSearch), shared by the Cmd/Ctrl-K palette and the phone search sheet. Every term
// passes through normalize(), on the indexed text and on the query alike.
import MiniSearch from 'minisearch'
import { normalize, terms, tokenize } from './normalize'

export type EntryKind = 'page' | 'component' | 'card' | 'decision' | 'doc'

export interface Entry {
  id: string
  kind: EntryKind
  /** What the row shows and the main field searched */
  title: string
  /** Identifiers and other words that should find it (paths, ids, the other language's title) */
  keywords?: string
  /** The route the row opens, as a hash path with its search params */
  to: string
}

export interface SearchIndex {
  search(query: string, limit?: number): Entry[]
  readonly size: number
}

export function buildIndex(entries: Entry[]): SearchIndex {
  const byId = new Map(entries.map((entry) => [entry.id, entry]))
  const mini = new MiniSearch<Entry>({
    fields: ['title', 'keywords'],
    storeFields: [],
    tokenize,
    processTerm: (term) => { const word = normalize(term); return word ? terms(word) : null },
    // The query keeps only the bare form of each word: the index holds both, so one form always meets the other
    searchOptions: { processTerm: (term) => { const word = normalize(term); return word ? terms(word).at(-1)! : null }, boost: { title: 2 }, prefix: true, fuzzy: (term) => (term.length > 4 ? 0.15 : 0), combineWith: 'AND' },
  })
  mini.addAll(entries)
  return {
    size: entries.length,
    search(query, limit = 40) {
      if (!normalize(query)) return entries.filter((entry) => entry.kind === 'page').slice(0, limit)
      return mini.search(query).slice(0, limit).map((hit) => byId.get(hit.id as string)!).filter(Boolean)
    },
  }
}
