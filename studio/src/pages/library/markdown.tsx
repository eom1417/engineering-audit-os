// A report document drawn from Markdown: marked's lexer reads it (docs/adoption/ns46-t4-library-history-quality.md) and
// each token becomes a Studio element here, so no HTML string from a report is ever injected. Headings get anchors for
// the table of contents, card ids and links to other documents become Studio links, code and tables keep their own
// left-to-right scroll, and every block takes the direction of its own text. What GitHub adds is read too (gfm.ts):
// alerts, task lists, footnotes; code is highlighted (CodeBlock), Mermaid diagrams and charts are drawn (Diagram),
// tables align their number columns, and an image alone in its paragraph is a figure with its caption.
import { lexer, type Token, type Tokens } from 'marked'
import { Fragment, type ReactNode } from 'react'
import { Go } from '../../components/Go'
import { Icon, type IconName } from '../../components/Icon'
import { dirOf } from '../../i18n/text'
import { CodeBlock } from './CodeBlock'
import { Diagram } from './Diagram'
import { alertOf, footnotes, FOOTNOTE_REF, numericColumns, type AlertKind } from './gfm'
import { docPath, imagePath, resolveLink, type LibraryImage } from './model'
import type { LibraryWord } from './words'
import css from './library.module.css'

export interface Heading { id: string; depth: number; text: string }

export interface Context {
  /** The document's own path, which its relative links start from */
  path: string
  /** The document's title, so a first heading that repeats it is not drawn twice */
  title: string
  docs: ReadonlySet<string>
  cards: ReadonlySet<string>
  images: ReadonlyMap<string, LibraryImage>
  /** The reader's words in the person's language (words.ts) */
  w: (key: LibraryWord, vars?: Record<string, string | number>) => string
}

/** The footnotes of the document being drawn: their texts, and the number each takes at its first citation. */
interface Notes { texts: Map<string, string>; order: Map<string, number> }

export interface Drawn { body: ReactNode; headings: Heading[] }

/** The plain text of inline tokens, for a heading's name in the table of contents. */
export function plain(tokens: Token[] | undefined): string {
  return (tokens ?? []).map((t) => ('tokens' in t && t.tokens ? plain(t.tokens) : 'text' in t ? String(t.text) : '')).join('')
}

const ENTITIES: Record<string, string> = { amp: '&', lt: '<', gt: '>', quot: '"', '#39': "'", apos: "'", nbsp: ' ' }

/** marked leaves character references in text as written: show them as the characters they name. */
export function unescape(text: string): string {
  return text.replace(/&(amp|lt|gt|quot|#39|apos|nbsp);/g, (_, name: string) => ENTITIES[name])
}

const IDS = /\b(TASK-\d{1,6}|ADR-\d{1,4})\b/g

/** Moves to a footnote or back to where it is cited. */
function jump(id: string) {
  const el = document.getElementById(id)
  if (!el) return
  el.scrollIntoView({ block: 'center' })
  el.focus({ preventScroll: true })
}

/** Text with its footnote references drawn as numbered buttons, the rest linked by `linked`. */
function cited(text: string, ctx: Context, notes: Notes | undefined, key: string): ReactNode[] {
  if (!notes?.texts.size || !text.includes('[^')) return linked(text, ctx, key)
  const out: ReactNode[] = []
  let last = 0
  for (const match of text.matchAll(FOOTNOTE_REF)) {
    const label = match[1]
    if (!notes.texts.has(label)) continue
    const at = match.index ?? 0
    if (at > last) out.push(...linked(text.slice(last, at), ctx, `${key}-${at}t`))
    const first = !notes.order.has(label)
    if (first) notes.order.set(label, notes.order.size + 1)
    const n = notes.order.get(label)!
    out.push(<sup key={`${key}-${at}`} className={css.fnRef}>
      <button type="button" id={first ? `fnref-${n}` : undefined} aria-label={ctx.w('footnoteN', { n })} onClick={() => jump(`fn-${n}`)}>{n}</button>
    </sup>)
    last = at + match[0].length
  }
  if (last < text.length) out.push(...linked(text.slice(last), ctx, `${key}-end`))
  return out
}

/** Text with the ids it names linked: a card to its problem, an ADR to its document. */
function linked(text: string, ctx: Context, key: string): ReactNode[] {
  const out: ReactNode[] = []
  let last = 0
  for (const match of text.matchAll(IDS)) {
    const at = match.index ?? 0
    const id = match[1]
    const adr = id.startsWith('ADR-') ? [...ctx.docs].find((p) => p.endsWith(`/${id}.md`) || p === `${id}.md`) : undefined
    if (!adr && !ctx.cards.has(id)) continue
    if (at > last) out.push(text.slice(last, at))
    out.push(adr
      ? <Go key={`${key}-${at}`} to={docPath(adr)} className={css.idLink}><bdi dir="ltr">{id}</bdi></Go>
      : <Go key={`${key}-${at}`} to="/problems" search={{ card: id }} className={css.idLink}><bdi dir="ltr">{id}</bdi></Go>)
    last = at + id.length
  }
  if (last < text.length) out.push(text.slice(last))
  return out
}

function inline(tokens: Token[] | undefined, ctx: Context, key: string, notes?: Notes): ReactNode[] {
  return (tokens ?? []).map((token, i) => {
    const k = `${key}.${i}`
    switch (token.type) {
      case 'text': case 'escape':
        return 'tokens' in token && token.tokens?.length ? <Fragment key={k}>{inline(token.tokens, ctx, k, notes)}</Fragment>
          : <Fragment key={k}>{cited(unescape(token.text), ctx, notes, k)}</Fragment>
      case 'strong': return <strong key={k}>{inline(token.tokens, ctx, k, notes)}</strong>
      case 'em': return <em key={k} className={css.em}>{inline(token.tokens, ctx, k, notes)}</em>
      case 'del': return <del key={k}>{inline(token.tokens, ctx, k, notes)}</del>
      case 'codespan': {
        const text = unescape(token.text)
        const target = resolveLink(ctx.path, text).path
        const code = <code className={css.codespan} dir="ltr">{text}</code>
        // a document named as code (`CURRENT-STATE.md`) opens it
        return ctx.docs.has(target) && /\.md$/.test(text) ? <Go key={k} to={docPath(target)} className={css.link}>{code}</Go> : <Fragment key={k}>{code}</Fragment>
      }
      case 'br': return <br key={k} />
      case 'link': return link(token as Tokens.Link, ctx, k)
      case 'image': return image(token as Tokens.Image, ctx, k)
      default: return <Fragment key={k}>{unescape(String(token.raw ?? ''))}</Fragment>   // raw HTML is shown as text
    }
  })
}

function link(token: Tokens.Link, ctx: Context, key: string): ReactNode {
  const body = inline(token.tokens, ctx, key)
  if (/^(https?:|mailto:)/i.test(token.href)) return <a key={key} href={token.href} rel="noreferrer noopener" target="_blank" className={css.link}>{body}</a>
  const { path, hash } = resolveLink(ctx.path, token.href)
  if (ctx.docs.has(path)) return <Go key={key} to={docPath(path)} search={hash ? { h: hash } : undefined} className={css.link}>{body}</Go>
  if (ctx.images.has(path)) return <Go key={key} to={imagePath(path)} className={css.link}>{body}</Go>
  return <span key={key} className={css.deadLink} title={token.href}>{body}</span>   // a file the Studio does not carry
}

function image(token: Tokens.Image, ctx: Context, key: string): ReactNode {
  const { path } = resolveLink(ctx.path, token.href)
  const found = ctx.images.get(path)
  if (found?.data) return <img key={key} src={found.data} alt={token.text} className={css.inlineImage} />
  return <span key={key} className={css.deadLink}>{token.text || path}</span>
}

const ALERT_ICONS: Record<AlertKind, IconName> = { note: 'info', tip: 'explain', important: 'important', warning: 'problems', caution: 'caution' }

/** A paragraph that holds one image and nothing else: drawn as a figure with its caption. */
function soleImage(tokens: Token[] | undefined): Tokens.Image | null {
  const parts = (tokens ?? []).filter((t) => !(t.type === 'text' && !String(t.raw).trim()) && t.type !== 'br')
  return parts.length === 1 && parts[0].type === 'image' ? parts[0] as Tokens.Image : null
}

/** The document drawn, and its headings (for the table of contents), in one walk. */
export function drawMarkdown(source: string, ctx: Context): Drawn {
  const { text, notes: texts } = footnotes(source)
  const notes: Notes = { texts, order: new Map() }
  const tokens = lexer(text, { gfm: true })
  const headings: Heading[] = []
  let tables = 0
  let codes = 0
  let diagrams = 0
  let skippedTitle = false
  const ins = (list: Token[] | undefined, key: string) => inline(list, ctx, key, notes)

  function blocks(list: Token[], key: string): ReactNode[] {
    return list.map((token, i) => block(token, `${key}.${i}`)).filter((node) => node !== null)
  }

  function block(token: Token, key: string): ReactNode {
    switch (token.type) {
      case 'space': case 'def': return null
      case 'heading': {
        const h = token as Tokens.Heading
        const name = unescape(plain(h.tokens)).trim()
        if (!skippedTitle && h.depth === 1 && headings.length === 0 && name === ctx.title.trim()) { skippedTitle = true; return null }
        const depth = Math.min(4, Math.max(2, h.depth))
        const id = `h-${headings.length + 1}`
        headings.push({ id, depth, text: name.replace(FOOTNOTE_REF, '').trim() })
        const Tag = `h${depth}` as 'h2' | 'h3' | 'h4'
        return <Tag key={key} id={id} dir="auto" className={css[`h${depth}`]} tabIndex={-1}>{ins(h.tokens, key)}</Tag>
      }
      case 'paragraph': {
        const p = token as Tokens.Paragraph
        const alone = soleImage(p.tokens)
        if (alone) return figure(alone, key)
        return <p key={key} dir="auto">{ins(p.tokens, key)}</p>
      }
      case 'text': return <p key={key} dir="auto">{'tokens' in token && token.tokens ? ins(token.tokens, key) : unescape(token.text)}</p>
      case 'blockquote': {
        const quote = token as Tokens.Blockquote
        const alert = alertOf(quote.text)
        if (!alert) return <blockquote key={key} className={css.quote}>{blocks(quote.tokens, key)}</blockquote>
        const title = ctx.w(`alert_${alert.kind}`)
        return (
          <div key={key} className={css.alert} data-kind={alert.kind} role="note" aria-label={title} dir={dirOf(alert.body || title)}>
            <p className={css.alertTitle}><Icon name={ALERT_ICONS[alert.kind]} />{title}</p>
            {blocks(lexer(alert.body, { gfm: true }), key)}
          </div>
        )
      }
      case 'hr': return <hr key={key} className={css.hr} />
      case 'list': {
        const list = token as Tokens.List
        const items = list.items.map((item, j) => (
          <li key={j} className={item.task ? css.task : undefined}>
            {item.task && <span className={css.check} data-checked={item.checked ? '' : undefined} role="img"
              aria-label={ctx.w(item.checked ? 'taskDone' : 'taskOpen')} />}
            {item.loose ? blocks(item.tokens.filter((t) => t.type !== 'checkbox'), `${key}.${j}`) : item.tokens.map((t, n) => t.type === 'checkbox' ? null : t.type === 'text'
              ? <Fragment key={n}>{'tokens' in t && t.tokens ? ins(t.tokens, `${key}.${j}.${n}`) : unescape(t.text)}</Fragment>
              : block(t, `${key}.${j}.${n}`))}
          </li>
        ))
        return list.ordered
          ? <ol key={key} dir={dirOf(list.raw)} className={css.list} start={typeof list.start === 'number' ? list.start : undefined}>{items}</ol>
          : <ul key={key} dir={dirOf(list.raw)} className={css.list}>{items}</ul>
      }
      case 'code': {
        const code = token as Tokens.Code
        if ((code.lang ?? '').trim().toLowerCase() === 'mermaid') {
          diagrams += 1
          return <Diagram key={key} source={code.text} n={diagrams} />
        }
        codes += 1
        return <CodeBlock key={key} code={code.text} info={code.lang} label={ctx.w('codeN', { n: codes })} />
      }
      case 'table': {
        const table = token as Tokens.Table
        tables += 1
        const numbers = numericColumns(table.rows.map((row) => row.map((cell) => unescape(cell.text))), table.header.length)
        const align = (a: string | null, j: number) => [numbers[j] && css.num, a === 'right' ? css.end : a === 'center' ? css.center : a === 'left' ? css.start : undefined]
          .filter(Boolean).join(' ') || undefined
        const cell = (tokens: Token[], j: number, k: string) => (numbers[j] ? <bdi dir="ltr">{ins(tokens, k)}</bdi> : ins(tokens, k))
        return (
          <div key={key} className={css.tableWrap} role="region" tabIndex={0} aria-label={ctx.w('tableN', { n: tables })} dir={dirOf(table.raw)}>
            <table className={css.table}>
              <thead><tr>{table.header.map((head, j) => <th key={j} scope="col" dir={numbers[j] ? undefined : 'auto'} className={align(head.align, j)}>{ins(head.tokens, `${key}.h${j}`)}</th>)}</tr></thead>
              <tbody>{table.rows.map((row, r) => (
                <tr key={r}>{row.map((c, j) => <td key={j} dir={numbers[j] ? undefined : 'auto'} className={align(c.align, j)}>{cell(c.tokens, j, `${key}.${r}.${j}`)}</td>)}</tr>
              ))}</tbody>
            </table>
          </div>
        )
      }
      case 'html': return <p key={key} dir="auto" className={css.raw}>{unescape(String((token as Tokens.HTML).text ?? ''))}</p>
      default: return 'tokens' in token && token.tokens ? <p key={key} dir="auto">{ins(token.tokens, key)}</p> : null
    }
  }

  function figure(token: Tokens.Image, key: string): ReactNode {
    const caption = (token.title || token.text || '').trim()
    return (
      <figure key={key} className={css.figureInline}>
        {image(token, ctx, `${key}.img`)}
        {caption && <figcaption className={css.caption} dir="auto">{caption}</figcaption>}
      </figure>
    )
  }

  const body = blocks(tokens, 'b')
  // the notes in the order they are first cited, then any never cited
  const citations = notes.order.size
  for (const label of texts.keys()) if (!notes.order.has(label)) notes.order.set(label, notes.order.size + 1)
  const listed = [...notes.order].sort((a, b) => a[1] - b[1])
  if (listed.length) {
    body.push(
      <section key="footnotes" className={css.footnotes} aria-label={ctx.w('footnotes')}>
        <ol className={css.footnoteList}>
          {listed.map(([label, n]) => (
            <li key={label} id={`fn-${n}`} tabIndex={-1} dir={dirOf(texts.get(label) ?? '')}>
              <span className={css.footnoteN}>{n}</span>
              <div className={css.footnoteText}>{blocks(lexer(texts.get(label) ?? '', { gfm: true }), `fn${n}`)}</div>
              {n <= citations && <button type="button" className={css.footnoteBack} aria-label={ctx.w('footnoteBack', { n })} onClick={() => jump(`fnref-${n}`)}>↩</button>}
            </li>
          ))}
        </ol>
      </section>,
    )
  }
  return { body, headings }
}
