// The Studio's weight budgets, checked at the end of every build (npm run build): what a person's browser reads before
// the first page shows, compressed as it travels, and the whole shipped folder. A change that grows past a budget fails
// the build and says by how much; lowering a budget after a page gets lighter keeps it from growing back.
import fs from 'node:fs'
import path from 'node:path'
import zlib from 'node:zlib'
import { fileURLToPath } from 'node:url'

const shipped = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../eaos/data/studio')
const KB = 1024
const BUDGETS = [
  { name: 'first page script (gzip)', files: ['boot.js', 'assets/studio.js'], gzip: true, max: 240 * KB },
  { name: 'stylesheet (gzip)', files: ['assets/style.css'], gzip: true, max: 48 * KB },
  { name: 'whole Studio on disk', files: null, gzip: false, max: 6 * KB * KB },
]

const all = (dir) => fs.readdirSync(dir, { recursive: true }).map((name) => path.join(dir, name)).filter((file) => fs.statSync(file).isFile())
const size = (file, gzip) => (gzip ? zlib.gzipSync(fs.readFileSync(file), { level: 9 }).length : fs.statSync(file).size)

let over = 0
for (const budget of BUDGETS) {
  const files = budget.files ? budget.files.map((name) => path.join(shipped, name)) : all(shipped)
  const total = files.reduce((sum, file) => sum + size(file, budget.gzip), 0)
  const line = `${budget.name}: ${(total / KB).toFixed(0)} KB of ${(budget.max / KB).toFixed(0)} KB`
  if (total > budget.max) { over += 1; console.error(`over budget: ${line}`) } else console.log(line)
}
if (over) process.exit(1)
