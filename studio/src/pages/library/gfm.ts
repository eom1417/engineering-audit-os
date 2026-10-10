// What GitHub adds to Markdown beyond marked's lexer, read here as plain text so the reader can draw it: alerts
// (> [!NOTE]), footnotes ([^1] and [^1]: …), and the columns of a table that hold numbers.

export const ALERTS = ['note', 'tip', 'important', 'warning', 'caution'] as const
export type AlertKind = typeof ALERTS[number]

/** An alert's kind and the quote's text without its marker, or null for an ordinary quote. */
export function alertOf(text: string): { kind: AlertKind; body: string } | null {
  const match = /^\s*\[!(note|tip|important|warning|caution)\][ \t]*(?:\n|$)/i.exec(text)
  return match ? { kind: match[1].toLowerCase() as AlertKind, body: text.slice(match[0].length) } : null
}

export interface Footnotes {
  /** The text with the definitions taken out */
  text: string
  /** label -> its text, in the order the definitions are written */
  notes: Map<string, string>
}

/** Takes footnote definitions out of a document (outside code fences): `[^label]: text`, with indented lines after it. */
export function footnotes(source: string): Footnotes {
  const notes = new Map<string, string>()
  const out: string[] = []
  let fence: string | null = null
  let current: string | null = null
  for (const line of source.split('\n')) {
    const marker = /^\s{0,3}(`{3,}|~{3,})/.exec(line)
    if (marker && (!fence || marker[1].startsWith(fence))) {
      fence = fence ? null : marker[1]
      current = null
      out.push(line)
      continue
    }
    if (!fence) {
      const def = /^\s{0,3}\[\^([^\]\s]+)\]:[ \t]*(.*)$/.exec(line)
      if (def) {
        current = def[1]
        notes.set(current, def[2])
        continue
      }
      if (current && /^(\s{2,}|\t)\S/.test(line)) {
        notes.set(current, `${notes.get(current)}\n${line.trim()}`)
        continue
      }
    }
    current = null
    out.push(line)
  }
  return { text: notes.size ? out.join('\n') : source, notes }
}

/** A footnote reference in running text: [^label]. */
export const FOOTNOTE_REF = /\[\^([^\]\s]+)\]/g

const NUMBER = /^[-+−]?[$€£¥]?\s?[\d٠-٩][\d٠-٩,.٫٬\s]*\s?(%|٪|[kKmMgGtT]?[bB]|ms|s|x|×|[kKmM])?$/

/** A cell that reads as a number: 1,204 · −3.5% · 12 ms · ٣٫٥ · $40 · 2.1 MB. */
export function isNumeric(text: string): boolean {
  const value = text.trim()
  return value !== '' && NUMBER.test(value)
}

/** Which columns hold numbers: every filled cell of the column reads as one (and at least one is filled). */
export function numericColumns(rows: readonly (readonly string[])[], columns: number): boolean[] {
  return Array.from({ length: columns }, (_, j) => {
    const cells = rows.map((row) => (row[j] ?? '').trim()).filter((cell) => cell !== '' && cell !== '—' && cell !== '-')
    return cells.length > 0 && cells.every(isNumeric)
  })
}
