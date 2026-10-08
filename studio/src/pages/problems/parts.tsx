// The pieces the Problems and Evidence pages share: the code excerpt with its line numbers and the fact's line
// marked, the evidence card that carries it, and the confidence in words with its meter and source.
import { Go } from '../../components/Go'
import { EvidenceCard } from '../../components/Finding'
import type { Fact } from '../../data/types'
import { usePrefs } from '../../i18n/prefs'
import { Id } from '../../i18n/text'
import { confidenceWord } from './model'
import { useProblemWords } from './words'
import css from './problems.module.css'

const SECRET = new Set(['secret', 'credential', 'hardcoded_secret'])

/** The lines around a fact's place, numbered, with its own line marked; always left to right with its own scroll. A
 * fact without code says why: a secret, no line recorded, or the file not read. */
export function CodeExcerpt({ fact }: { fact: Fact }) {
  const w = useProblemWords()
  const { num } = usePrefs()
  const code = fact.code
  if (!code) {
    const why = SECRET.has(fact.kind) ? w('noCodeSecret') : !fact.line && !fact.sites.some((s) => s.line) ? w('noCodeLine') : w('noCodeRead')
    return fact.path ? <p className={css.noCode}>{why}</p> : null
  }
  const where = `${fact.path}:${code.line}`
  // the indentation every shown line shares is dropped, so the fact's line starts at the left edge on a phone
  const indent = Math.min(...code.lines.filter((l) => l.trim()).map((l) => l.length - l.trimStart().length), 80)
  return (
    <figure className={css.codeFigure}>
      <figcaption className="sr">{w('codeAt', { where })}</figcaption>
      <pre className={css.code} data-scroll-x="" tabIndex={0} aria-label={w('codeAt', { where })}>
        <code>
          {code.lines.map((text, i) => {
            const n = code.start + i
            const hidden = code.hidden.includes(n)
            return (
              <span key={n} className={[css.codeLine, n === code.line && css.codeFocus].filter(Boolean).join(' ')} data-line={n}>
                <span className={css.lineNo} aria-hidden="true">{num(n)}</span>
                {hidden ? <span className={css.hiddenLine} dir="auto">{w('hiddenLine')}</span> : <span>{text.slice(Number.isFinite(indent) ? indent : 0) || ' '}</span>}
                {'\n'}
              </span>
            )
          })}
        </code>
      </pre>
    </figure>
  )
}

/** One fact as evidence: the shared evidence card, its code, and (unless this is its own page) the link to its page. */
export function Evidence({ fact, link = true }: { fact: Fact; link?: boolean }) {
  const w = useProblemWords()
  return (
    <EvidenceCard fact={fact}>
      <CodeExcerpt fact={fact} />
      {link && <Go to={`/evidence/${encodeURIComponent(fact.id)}`} className={css.inlineLink}>{w('openEvidence')}</Go>}
    </EvidenceCard>
  )
}

/** Confidence as a word and a meter, with where the number comes from. */
export function Confidence({ value }: { value: number | null | undefined }) {
  const w = useProblemWords()
  const word = confidenceWord(value)
  if (!word || typeof value !== 'number') return <span className={css.muted}>{w('noConfidence')}</span>
  return (
    <span className={css.confidence}>
      <span className={css.confidenceWord}>{w(word)}</span>
      <span className={css.meter} role="meter" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(value * 100)}
        aria-label={`${w('confidence')}: ${w(word)}`}>
        <i style={{ inlineSize: `${Math.round(value * 100)}%` }} />
      </span>
      <span className={css.source}>{w('confidenceSource')}</span>
    </span>
  )
}

export function Where({ path, line }: { path: string; line?: number | null }) {
  return <Id value={line ? `${path}:${line}` : path} />
}
