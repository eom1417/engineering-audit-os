/// <reference types="vitest/config" />
// The Studio builds to classic scripts and one stylesheet with fixed names, so it opens from a file (a browser refuses
// module scripts there) and the package ships the same names every release (docs/STUDIO.md, D1). assets/studio.js
// holds the frame, Home and Problems; every other page is a chunk beside it, read when it is opened (classicChunks).
import fs from 'node:fs'
import path from 'node:path'
import optimizeLocales from '@react-aria/optimize-locales-plugin'
import react from '@vitejs/plugin-react'
import { defineConfig, type Plugin } from 'vite'

// In development the data comes from a report's studio/ folder: STUDIO_DATA=/path/to/report/studio npm run dev
function reportData(): Plugin {
  const folder = process.env.STUDIO_DATA
  return {
    name: 'eaos-report-data',
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        const name = (req.url || '').split('?')[0].replace(/^\//, '')
        if (!folder || !/^[a-z]+\.js$/.test(name)) return next()
        const file = path.join(folder, name)
        if (!fs.existsSync(file)) return next()
        res.setHeader('Content-Type', 'text/javascript; charset=utf-8')
        res.end(fs.readFileSync(file))
      })
    },
  }
}

// No address outside the Studio is shipped (tests/test_studio_assets.py). The libraries name their repositories and
// documentation in error and warning messages only: marked's lexer, Mermaid and its parser (chevrotain, langium) and
// highlight.js never request them, so those words are taken out of the bundle; behaviour is unchanged. XML namespaces stay (test allowlist).
const NAMED = /https?:\/\/(github\.com|chevrotain\.io|langium\.org|en\.wikipedia\.org)\/[^\s"'`)<>\\]*/g
function noOutsideAddress(): Plugin {
  return {
    name: 'eaos-no-outside-address',
    transform(code, id) {
      if (id.includes('/node_modules/marked/')) return code.replace('\nPlease report this to https://github.com/markedjs/marked.', '')
      if (/\/node_modules\/(mermaid|@mermaid-js|chevrotain|@chevrotain|langium|highlight\.js)\//.test(id)) return code.replace(NAMED, '')
      return null
    },
  }
}

// Mermaid registers ELK as a layout it loads on demand: elkjs is 1.5 MB (EPL-2.0) for a layout the reports never ask
// for. Without it Mermaid falls back to its default layout, as its own small build does (docs/adoption/docs-reader.md).
const ELK = '      ...elkLayoutLoaders()\n'
function noElk(): Plugin {
  return {
    name: 'eaos-no-elk',
    transform(code, id) {
      if (!/\/node_modules\/mermaid\/dist\/chunks\/mermaid\.core\/chunk-[\w]+\.mjs$/.test(id) || !code.includes('var registerDefaultLayoutLoaders')) return null
      if (!code.includes(ELK)) this.error('Mermaid changed how it registers ELK: update noElk in vite.config.ts')
      return code.replace(ELK, '')
    },
  }
}

// Mermaid's own chunks (its diagram types, read when a document draws one) carry its name, apart from the Studio's.
function chunkName(chunk: { name: string; moduleIds: string[] }): string {
  const third = chunk.moduleIds.length > 0 && chunk.moduleIds.every((id) => id.includes('/node_modules/'))
  return third && chunk.moduleIds.some((id) => /\/node_modules\/(mermaid|@mermaid-js|cytoscape|katex|dagre-d3-es|d3-|khroma|roughjs|chevrotain|langium)/.test(id))
    ? 'assets/mermaid.[name].js' : 'assets/[name].js'
}

// A classic, deferred script instead of a module one.
function classicScript(): Plugin {
  return {
    name: 'eaos-classic-script',
    apply: 'build',
    enforce: 'post',
    transformIndexHtml: (html) => html.replace(/<script type="module" crossorigin src=/g, '<script defer src=').replace(/ crossorigin/g, ''),
  }
}

// Code splitting with classic scripts. Rolldown writes CommonJS chunks; each chunk becomes a classic script that
// registers its body under its file name, and the entry carries a small loader: a page's dynamic import reads that
// page's chunk and the chunks it shares from the entry's own folder (as boot.js reads the report's data), then runs
// them. Nothing is read from elsewhere, and a page opened from a file works as one served over HTTP.
function classicChunks(): Plugin {
  const DYNAMIC = /Promise\.resolve\(\)\.then\(\(\) => require\("\.\/([\w.-]+\.js)"\)\)/g
  return {
    name: 'eaos-classic-chunks',
    apply: 'build',
    renderChunk(code) {
      const next = code.replace(DYNAMIC, (_, name: string) => `self.EAOS_CHUNK(${JSON.stringify(name)})`)
      if (/Promise\.resolve\(\)\.then\(\(\) =>[^;]*require\(/.test(next)) this.error('a dynamic import the classic loader does not know')
      return next
    },
    // After Vite has gathered every chunk's styles into style.css: this hook removes the chunks the entry carries
    generateBundle: { order: 'post', handler(_, bundle) {
      const chunks = Object.values(bundle).filter((file) => file.type === 'chunk')
      const entry = chunks.find((chunk) => chunk.isEntry)
      if (!entry || chunks.some((chunk) => !/^assets\/[\w.-]+\.js$/.test(chunk.fileName))) this.error('every chunk must sit in assets/')
      const name = (file: string) => file.slice('assets/'.length)
      // For each chunk, every chunk its body requires, directly or through another (the entry is already there)
      const needs = (file: string, seen = new Set<string>()): Set<string> => {
        const chunk = bundle[file]
        if (chunk.type === 'chunk') for (const next of chunk.imports) if (next !== entry!.fileName && !seen.has(next)) { seen.add(next); needs(next, seen) }
        return seen
      }
      const register = (chunk: { fileName: string; code: string }) =>
        `(self.EAOS_CHUNKS=self.EAOS_CHUNKS||{})[${JSON.stringify(name(chunk.fileName))}]=function(require,exports,module){${chunk.code}\n};\n`
      // The chunks the entry itself requires (rolldown's shared helpers) travel inside assets/studio.js
      const inside = needs(entry!.fileName)
      // (every chunk is listed: one a page imports may also be imported statically by another, and rolldown then
      // does not mark it a dynamic entry)
      const all = Object.fromEntries(chunks.filter((chunk) => chunk !== entry && !inside.has(chunk.fileName))
        .map((chunk) => [name(chunk.fileName), [...needs(chunk.fileName)].filter((file) => !inside.has(file)).map(name)]))
      // A library's own chunks (mermaid.*, chunkName) are read only through the Studio chunk that imports the library:
      // their list travels in that chunk, which adds it to the loader when it runs, not in the entry every page reads
      const island = (file: string) => file.startsWith('mermaid.')
      const deps = Object.fromEntries(Object.entries(all).filter(([file]) => !island(file)))
      const islandDeps = Object.fromEntries(Object.entries(all).filter(([file]) => island(file)))
      const carriers = new Set(chunks.filter((chunk) => chunk !== entry && !island(name(chunk.fileName)) && chunk.dynamicImports.some((file) => island(name(file))))
        .map((chunk) => chunk.fileName))
      const carried = chunks.filter((chunk) => inside.has(chunk.fileName)).map(register).join('')
      for (const file of inside) delete bundle[file]
      for (const chunk of chunks) {
        if (inside.has(chunk.fileName)) continue
        if (chunk !== entry) {
          if (carriers.has(chunk.fileName)) chunk.code = `self.EAOS_CHUNK_DEPS(${JSON.stringify(islandDeps)});\n${chunk.code}`
          chunk.code = register(chunk)
          continue
        }
        chunk.code = `${carried}(function(){var chunks=self.EAOS_CHUNKS=self.EAOS_CHUNKS||{},ran={},reading={},deps=${JSON.stringify(deps)},
folder=document.currentScript?document.currentScript.src:location.href;
function require(path){var name=path.replace(/^\\.\\//,""),m=ran[name];if(m)return m.exports;
if(!chunks[name])throw new Error("EAOS Studio: "+name+" is not loaded");m=ran[name]={exports:{}};chunks[name](require,m.exports,m);return m.exports}
function read(name){return reading[name]||(reading[name]=new Promise(function(done,fail){if(chunks[name])return done();
var s=document.createElement("script");s.src=new URL(name,folder).href;
s.onload=function(){chunks[name]?done():fail(new Error("EAOS Studio: "+name+" is not a Studio chunk"))};
s.onerror=function(){delete reading[name];fail(new Error("EAOS Studio: "+name+" did not load"))};document.head.appendChild(s)}))}
self.EAOS_CHUNK_DEPS=function(more){for(var k in more)deps[k]=more[k]};
self.EAOS_CHUNK=function(name){return Promise.all([name].concat(deps[name]||[]).map(read)).then(function(){return require(name)})};
var module=ran[${JSON.stringify(name(entry!.fileName))}]={exports:{}};
(function(require,exports,module){${chunk.code}
})(require,module.exports,module)})();
`
      }
    } },
  }
}

export default defineConfig({
  base: './',
  // React Aria's strings only for the two languages the Studio speaks (docs/adoption/ns37-t1-finish.md)
  plugins: [optimizeLocales.vite({ locales: ['ar', 'en'] }), react(), reportData(), noOutsideAddress(), noElk(), classicScript(), classicChunks()],
  server: { host: '0.0.0.0', port: 5180, allowedHosts: ['.dev.remote.e-m.sa'] },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    assetsInlineLimit: 0,
    cssCodeSplit: false,
    modulePreload: false,
    rollupOptions: {
      output: {
        format: 'cjs',
        dynamicImportInCjs: false,
        entryFileNames: 'assets/studio.js',
        chunkFileNames: chunkName,
        // Everything the first page needs stays together (and travels inside assets/studio.js), in the order one
        // bundle would hold it, so style.css keeps the cascade it had before the pages were split off
        codeSplitting: { groups: [{ name: 'initial', tags: ['$initial'] }] },
        assetFileNames: 'assets/[name][extname]',
      },
    },
  },
  test: { include: ['src/**/*.test.ts'], environment: 'node' },
})
