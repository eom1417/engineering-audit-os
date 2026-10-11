// The diagram engine: Mermaid (docs/adoption/docs-reader.md), read only when a document holding a ```mermaid block is
// opened. It and its diagram types are their own chunks (vite.config.ts classicChunks), each type read the first time
// a drawing of that type is asked for. Mermaid draws with strict security: labels are text, no script or click handler
// survives, and its output is sanitised by its own DOMPurify before the reader places it.
import mermaid from 'mermaid'
import { mermaidConfig, svgSize, type DiagramTheme, type Size } from './diagram'

export interface Drawing extends Size { svg: string; id: string }

let configured = ''
let count = 0

/** The fonts the drawing measures its words with, loaded before it is laid out. */
async function fonts(family: string | undefined) {
  if (!family || !document.fonts) return
  const first = family.split(',')[0].trim()
  await Promise.all([document.fonts.load(`14px ${first}`, 'Aa'), document.fonts.load(`14px ${first}`, 'ب')]).catch(() => undefined)
}

export async function draw(source: string, theme: DiagramTheme): Promise<Drawing> {
  const config = mermaidConfig(theme)
  const key = JSON.stringify(config)
  if (key !== configured) {
    mermaid.initialize(config)
    configured = key
  }
  await fonts(theme.tokens['--font-sans'])
  count += 1
  const id = `eaos-diagram-${count}`
  try {
    const { svg } = await mermaid.render(id, source)
    return { svg, id, ...svgSize(svg) }
  } finally {
    // Mermaid lays the drawing out in a hidden element of the page; a failed one can leave it behind
    document.getElementById(`d${id}`)?.remove()
    document.getElementById(`i${id}`)?.remove()
  }
}
