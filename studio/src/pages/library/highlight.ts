// The code highlighter: highlight.js's grammars through lowlight (docs/adoption/docs-reader.md), read only when a
// document holding a code block in a known language is opened (its own chunk). lowlight returns a tree of spans
// (hast), which the reader draws as React elements: no HTML string is injected.
import bash from 'highlight.js/lib/languages/bash'
import csharp from 'highlight.js/lib/languages/csharp'
import cssLang from 'highlight.js/lib/languages/css'
import diff from 'highlight.js/lib/languages/diff'
import dockerfile from 'highlight.js/lib/languages/dockerfile'
import go from 'highlight.js/lib/languages/go'
import ini from 'highlight.js/lib/languages/ini'
import java from 'highlight.js/lib/languages/java'
import javascript from 'highlight.js/lib/languages/javascript'
import json from 'highlight.js/lib/languages/json'
import kotlin from 'highlight.js/lib/languages/kotlin'
import markdown from 'highlight.js/lib/languages/markdown'
import php from 'highlight.js/lib/languages/php'
import python from 'highlight.js/lib/languages/python'
import ruby from 'highlight.js/lib/languages/ruby'
import rust from 'highlight.js/lib/languages/rust'
import shell from 'highlight.js/lib/languages/shell'
import sql from 'highlight.js/lib/languages/sql'
import typescript from 'highlight.js/lib/languages/typescript'
import xml from 'highlight.js/lib/languages/xml'
import yaml from 'highlight.js/lib/languages/yaml'
import { createLowlight } from 'lowlight'
import type { Language } from './code'

const lowlight = createLowlight({ bash, csharp, css: cssLang, diff, dockerfile, go, ini, java, javascript, json, kotlin, markdown, php, python, ruby, rust, shell, sql, typescript, xml, yaml })

export type Highlighted = ReturnType<typeof lowlight.highlight>

export function highlight(code: string, language: Language): Highlighted {
  return lowlight.highlight(language, code)
}
