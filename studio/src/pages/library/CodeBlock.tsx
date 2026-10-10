// A code block in a document: its language named, a copy button, and its words coloured by the highlighter
// (highlight.ts, a chunk read the first time a document holds code in a language it knows). The highlighter's tree is
// drawn as React elements; until it arrives, and for a language it does not know, the code is shown plain.
import { Fragment, useEffect, useState, type ReactNode } from 'react'
import { copyText, IconButton } from '../../components/Button'
import { useToast } from '../../components/Toast'
import { languageOf, tokenKind, type Language } from './code'
import type { Highlighted } from './highlight'
import { useLibraryWords } from './words'
import css from './library.module.css'

const loadHighlighter = () => import('./highlight')

type Node = Highlighted['children'][number]

const KIND_CLASS = {
  keyword: css.tKeyword, string: css.tString, number: css.tNumber, comment: css.tComment, title: css.tTitle, type: css.tType,
  attr: css.tAttr, meta: css.tMeta, deletion: css.tDeletion, addition: css.tAddition,
}

/** The highlighter's tree as React elements: text, and spans coloured by their kind. */
function draw(nodes: Node[], key: string): ReactNode[] {
  return nodes.map((node, i) => {
    const k = `${key}.${i}`
    if (node.type === 'text') return <Fragment key={k}>{node.value}</Fragment>
    if (node.type !== 'element') return null
    const names = Array.isArray(node.properties?.className) ? node.properties.className.map(String) : []
    const kind = tokenKind(names)
    return <span key={k} className={kind ? KIND_CLASS[kind] : undefined}>{draw(node.children as Node[], k)}</span>
  })
}

export function CodeBlock({ code, info, label }: { code: string; info?: string; label: string }) {
  const w = useLibraryWords()
  const toast = useToast()
  const language: Language | null = languageOf(info)
  const [tree, setTree] = useState<Highlighted | null>(null)
  useEffect(() => {
    if (!language) return
    let live = true
    loadHighlighter().then((module) => { if (live) setTree(module.highlight(code, language)) }, () => undefined)
    return () => { live = false }
  }, [code, language])
  const name = (info ?? '').trim().split(/\s+/)[0]
  return (
    <div className={css.codeBlock}>
      <div className={css.codeBar}>
        <span className={css.codeLang} dir="ltr">{name || w('code')}</span>
        <IconButton small icon="copy" label={w('copyCode')} onPress={() => { void copyText(code).then((ok) => toast(ok ? w('copiedCode') : w('copyFailed'))) }} />
      </div>
      <pre className={css.pre} dir="ltr" tabIndex={0} aria-label={label}><code>{tree ? draw(tree.children, 'c') : code}</code></pre>
    </div>
  )
}
