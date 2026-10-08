// Ships the built Studio into the EAOS package (eaos/data/studio), with SOURCE.json: the fingerprint of the source it
// was built from and the list of files shipped. tests/test_studio_assets.py recomputes the fingerprint without Node,
// so a source change without a rebuild fails the suite.
import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const studio = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const target = path.resolve(studio, '../eaos/data/studio')
// Keep in step with SOURCES in tests/test_studio_assets.py
export const SOURCES = ['index.html', 'package.json', 'package-lock.json', 'tsconfig.json', 'vite.config.ts', '.stylelintrc.json', 'public', 'scripts/ship.mjs', 'src']

function files(entry) {
  const full = path.join(studio, entry)
  if (fs.statSync(full).isFile()) return [entry]
  return fs.readdirSync(full).flatMap((name) => files(path.posix.join(entry, name)))
}

const hash = crypto.createHash('sha256')
for (const name of SOURCES.flatMap(files).sort()) {
  hash.update(`${name}\0`)
  hash.update(fs.readFileSync(path.join(studio, name)))
}
fs.rmSync(target, { recursive: true, force: true })
fs.cpSync(path.join(studio, 'dist'), target, { recursive: true })
fs.copyFileSync(path.join(studio, 'node_modules/@fontsource/ibm-plex-sans-arabic/LICENSE'), path.join(target, 'assets/FONT-LICENSE.txt'))
const shipped = fs.readdirSync(target, { recursive: true }).filter((name) => fs.statSync(path.join(target, name)).isFile()).map((name) => name.split(path.sep).join('/')).sort()
fs.writeFileSync(path.join(target, 'SOURCE.json'), JSON.stringify({ source_sha256: hash.digest('hex'), files: shipped }, null, 1) + '\n')
console.log(`shipped ${shipped.length} files to ${path.relative(process.cwd(), target)}`)
