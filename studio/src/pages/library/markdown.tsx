// A report document drawn from Markdown: marked's lexer reads it (docs/adoption/ns46-t4-library-history-quality.md) and
// each token becomes a Studio element here, so no HTML string from a report is ever injected. Headings get anchors for
// the table of contents, card ids and links to other documents become Studio links, code and tables keep their own
// left-to-right scroll, and every block takes the direction of its own text.
import { lexer, type Token, type Tokens } from 'marked'
import { Fragment, type ReactNode } from 'react'
import { Go } from '../../components/Go'
import { dirOf } from '../../i18n/text'
import { docPath, imagePath, resolveLink, type LibraryImage } from './model'
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
  label: { table: (n: number) => string; code: (n: number) => string; diagram: string; diagramNote: string }
}

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

function inline(tokens: Token[] | undefined, ctx: Context, key: string): ReactNode[] {
  return (tokens ?? []).map((token, i) => {
    const k = `${key}.${i}`
    switch (token.type) {
      case 'text': case 'escape':
        return 'tokens' in token && token.tokens?.length ? <Fragment key={k}>{inline(token.tokens, ctx, k)}</Fragment>
          : <Fragment key={k}>{linked(unescape(token.text), ctx, k)}</Fragment>
      case 'strong': return <strong key={k}>{inline(token.tokens, ctx, k)}</strong>
      case 'em': return <em key={k} className={css.em}>{inline(token.tokens, ctx, k)}</em>
      case 'del': return <del key={k}>{inline(token.tokens, ctx, k)}</del>
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

/** The document drawn, and its headings (for the table of contents), in one walk. */
export function drawMarkdown(text: string, ctx: Context): Drawn {
  const tokens = lexer(text, { gfm: true })
  const headings: Heading[] = []
  let tables = 0
  let codes = 0
  let skippedTitle = false

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
        headings.push({ id, depth, text: name })
        const Tag = `h${depth}` as 'h2' | 'h3' | 'h4'
        return <Tag key={key} id={id} dir="auto" className={css[`h${depth}`]} tabIndex={-1}>{inline(h.tokens, ctx, key)}</Tag>
      }
      case 'paragraph': return <p key={key} dir="auto">{inline((token as Tokens.Paragraph).tokens, ctx, key)}</p>
      case 'text': return <p key={key} dir="auto">{'tokens' in token && token.tokens ? inline(token.tokens, ctx, key) : unescape(token.text)}</p>
      case 'blockquote': return <blockquote key={key} className={css.quote}>{blocks((token as Tokens.Blockquote).tokens, key)}</blockquote>
      case 'hr': return <hr key={key} className={css.hr} />
      case 'list': {
        const list = token as Tokens.List
        const items = list.items.map((item, j) => (
          <li key={j} className={item.task ? css.task : undefined}>
            {item.task && <span className={css.check} data-checked={item.checked ? '' : undefined} aria-hidden="true" />}
            {item.loose ? blocks(item.tokens, `${key}.${j}`) : item.tokens.map((t, n) => t.type === 'text'
              ? <Fragment key={n}>{'tokens' in t && t.tokens ? inline(t.tokens, ctx, `${key}.${j}.${n}`) : unescape(t.text)}</Fragment>
              : block(t, `${key}.${j}.${n}`))}
          </li>
        ))
        return list.ordered
          ? <ol key={key} dir={dirOf(list.raw)} className={css.list} start={typeof list.start === 'number' ? list.start : undefined}>{items}</ol>
          : <ul key={key} dir={dirOf(list.raw)} className={css.list}>{items}</ul>
      }
      case 'code': {
        const code = token as Tokens.Code
        codes += 1
        const pre = <pre className={css.pre} dir="ltr" tabIndex={0} aria-label={ctx.label.code(codes)}><code>{code.text}</code></pre>
        if ((code.lang ?? '').toLowerCase() !== 'mermaid') return <Fragment key={key}>{pre}</Fragment>
        return (
          <figure key={key} className={css.diagram}>
            <figcaption className={css.caption}>{ctx.label.diagram} · {ctx.label.diagramNote}</figcaption>
            {pre}
          </figure>
        )
      }
      case 'table': {
        const table = token as Tokens.Table
        tables += 1
        const align = (a: string | null) => (a === 'right' ? css.end : a === 'center' ? css.center : undefined)
        return (
          <div key={key} className={css.tableWrap} role="region" tabIndex={0} aria-label={ctx.label.table(tables)}>
            <table className={css.table}>
              <thead><tr>{table.header.map((cell, j) => <th key={j} dir="auto" className={align(cell.align)}>{inline(cell.tokens, ctx, `${key}.h${j}`)}</th>)}</tr></thead>
              <tbody>{table.rows.map((row, r) => (
                <tr key={r}>{row.map((cell, j) => <td key={j} dir="auto" className={align(cell.align)}>{inline(cell.tokens, ctx, `${key}.${r}.${j}`)}</td>)}</tr>
              ))}</tbody>
            </table>
          </div>
        )
      }
      case 'html': return <p key={key} dir="auto" className={css.raw}>{unescape(String((token as Tokens.HTML).text ?? ''))}</p>
      default: return 'tokens' in token && token.tokens ? <p key={key} dir="auto">{inline(token.tokens, ctx, key)}</p> : null
    }
  }

  const body = blocks(tokens, 'b')
  return { body, headings }
}
