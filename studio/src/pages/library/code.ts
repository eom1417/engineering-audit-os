// Code blocks: the languages the highlighter knows (highlight.ts, a lazy chunk) under the names reports write, and
// highlight.js's scopes folded into the few colours the Studio's tokens define (--syntax-*).

export const LANGUAGES = ['bash', 'csharp', 'css', 'diff', 'dockerfile', 'go', 'ini', 'java', 'javascript', 'json', 'kotlin', 'markdown',
  'php', 'python', 'ruby', 'rust', 'shell', 'sql', 'typescript', 'xml', 'yaml'] as const
export type Language = typeof LANGUAGES[number]

const ALIASES: Record<string, Language> = {
  sh: 'bash', zsh: 'bash', console: 'shell', shellsession: 'shell', cs: 'csharp', 'c#': 'csharp', docker: 'dockerfile',
  golang: 'go', toml: 'ini', cfg: 'ini', conf: 'ini', env: 'ini', js: 'javascript', jsx: 'javascript', mjs: 'javascript', cjs: 'javascript',
  jsonc: 'json', json5: 'json', kt: 'kotlin', md: 'markdown', py: 'python', python3: 'python', rb: 'ruby', rs: 'rust',
  ts: 'typescript', tsx: 'typescript', mts: 'typescript', html: 'xml', svg: 'xml', xhtml: 'xml', vue: 'xml', yml: 'yaml',
  patch: 'diff', postgresql: 'sql', postgres: 'sql', mysql: 'sql', sqlite: 'sql',
}

/** The highlighter's name for a fence's language, or null when it is not one it knows (the block is shown plain). */
export function languageOf(info: string | undefined): Language | null {
  const name = (info ?? '').trim().split(/\s+/)[0].toLowerCase()
  if (!name) return null
  if ((LANGUAGES as readonly string[]).includes(name)) return name as Language
  return ALIASES[name] ?? null
}

export type TokenKind = 'keyword' | 'string' | 'number' | 'comment' | 'title' | 'type' | 'attr' | 'meta' | 'deletion' | 'addition'

const KINDS: Record<string, TokenKind> = {
  keyword: 'keyword', 'selector-tag': 'keyword', built_in: 'type', literal: 'number', operator: 'keyword',
  string: 'string', regexp: 'string', 'template-tag': 'string', 'selector-attr': 'string', char: 'string',
  number: 'number', symbol: 'number', bullet: 'number', link: 'string',
  comment: 'comment', quote: 'comment', doctag: 'meta',
  title: 'title', 'title.function': 'title', 'title.class': 'type', 'title.function.invoke': 'title', section: 'title', name: 'title',
  type: 'type', 'class': 'type', 'selector-class': 'type', 'selector-id': 'type', 'variable.language': 'keyword',
  attr: 'attr', attribute: 'attr', property: 'attr', params: 'attr', variable: 'attr', 'template-variable': 'attr', 'selector-pseudo': 'attr',
  meta: 'meta', 'meta.keyword': 'meta', 'meta.string': 'string', tag: 'meta', subst: 'attr',
  deletion: 'deletion', addition: 'addition',
}

/** The colour of a highlight.js span, from its class names (`hljs-title function_` is a function's title). */
export function tokenKind(classNames: readonly string[]): TokenKind | null {
  const parts = classNames.map((name) => name.replace(/^hljs-/, '').replace(/_+$/, ''))
  const scope = parts.join('.')
  return KINDS[scope] ?? KINDS[parts[0]] ?? null
}
