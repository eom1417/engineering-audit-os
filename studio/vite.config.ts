/// <reference types="vitest/config" />
// The Studio builds to one classic script and one stylesheet with fixed names, so it opens from a file (a browser
// refuses module scripts there) and the package ships the same names every release (docs/STUDIO.md, D1).
import fs from 'node:fs'
import path from 'node:path'
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

// A classic, deferred script instead of a module one.
function classicScript(): Plugin {
  return {
    name: 'eaos-classic-script',
    apply: 'build',
    enforce: 'post',
    transformIndexHtml: (html) => html.replace(/<script type="module" crossorigin src=/g, '<script defer src=').replace(/ crossorigin/g, ''),
  }
}

export default defineConfig({
  base: './',
  plugins: [react(), reportData(), classicScript()],
  server: { host: '0.0.0.0', port: 5180, allowedHosts: ['.dev.remote.e-m.sa'] },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    assetsInlineLimit: 0,
    cssCodeSplit: false,
    modulePreload: false,
    rollupOptions: {
      output: {
        format: 'iife',
        entryFileNames: 'assets/studio.js',
        assetFileNames: 'assets/[name][extname]',
      },
    },
  },
  test: { include: ['src/**/*.test.ts'], environment: 'node' },
})
