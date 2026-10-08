// Bidi helpers (DESIGN.md §5). Txt isolates every Latin run and every number group with punctuation inside Arabic
// text, and shows `backticked` spans as identifiers; Id shows one identifier or path. Never hand-wrap <bdi>.
import { Fragment, type ReactNode } from 'react'
import { usePrefs } from './prefs'

// A Latin run (words, paths, versions, ids) or a group of numbers joined by punctuation ("1 · 3 · 35", "1–47")
const RUN = /`([^`]+)`|([A-Za-z][\w.\-/:@]*(?:[ ][A-Za-z][\w.\-/:@]*)*)|(\d+(?:\s?[·–\-/:]\s?\d+)+)/g

export function isolate(text: string): ReactNode[] {
  const out: ReactNode[] = []
  let last = 0
  for (const match of text.matchAll(RUN)) {
    const at = match.index ?? 0
    if (at > last) out.push(text.slice(last, at))
    if (match[1] !== undefined) out.push(<Id key={at} value={match[1]} />)
    else out.push(<bdi key={at} dir="ltr">{match[0]}</bdi>)
    last = at + match[0].length
  }
  if (last < text.length) out.push(text.slice(last))
  return out
}

const ARABIC = /[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]/

/** The direction of a piece of report text: right to left when it holds any Arabic, else left to right. (A first
 * strong letter would misread an Arabic sentence that opens with "EAOS".) */
export function dirOf(text: string): 'rtl' | 'ltr' {
  return ARABIC.test(text) ? 'rtl' : 'ltr'
}

/**
 * Report or interface text: Latin runs and number groups isolated, `code` shown as an identifier. Text whose
 * direction differs from the page's (English report text in an Arabic page) sits in its own isolated run; with
 * block, in its own block aligned to its own start (DESIGN.md §5).
 */
export function Txt({ children, block }: { children: string | null | undefined; block?: boolean }) {
  const { dir } = usePrefs()
  if (!children) return null
  const own = dirOf(children)
  if (block) return <span dir={own} className="txt-block">{isolate(children)}</span>
  if (own !== dir) return <bdi dir={own}>{isolate(children)}</bdi>
  return <>{isolate(children)}</>
}

/** Splits a path after each '/', so it breaks there first and mid-name only as a last resort. */
function breakable(path: string): ReactNode[] {
  const parts = path.split(/(?<=\/)/)
  return parts.map((part, i) => <Fragment key={i}>{part}{i < parts.length - 1 ? <wbr /> : null}</Fragment>)
}

/**
 * An identifier, path, tool name, commit or id: LTR-isolated, mono. keep=N shows only the last N segments
 * ("…/a/b"), with the full value in the title.
 */
export function Id({ value, keep, className }: { value: string; keep?: number; className?: string }) {
  let shown = value
  if (keep && value.split('/').length > keep) shown = '…/' + value.split('/').slice(-keep).join('/')
  const cut = shown !== value
  return (
    <bdi dir="ltr" className={['id', className].filter(Boolean).join(' ')} title={cut ? value : undefined} data-truncate={cut ? '' : undefined}>
      {breakable(shown)}
    </bdi>
  )
}

/** A number: Western digits, the language's grouping, tabular */
export function N({ value, className }: { value: number; className?: string }) {
  const { num } = usePrefs()
  return <span className={['num', className].filter(Boolean).join(' ')}>{num(value)}</span>
}
