// Builds the console into the EAOS package (eaos/data/studio), what `eaos studio` serves and what a read-only copy
// opens from a file. Plain JavaScript modules and CSS, bundled by esbuild into classic scripts (a page opened from a
// file runs no module script):
//   assets/studio.js         the core (src/core, src/data): the shell, the router, sheets, search, the data layer
//   assets/<place>.js        one per folder of src/places, read when one of its addresses or sheets first opens; it
//                            reaches the core only through `import … from 'eaos'` (self.EAOS)
//   assets/words-<lang>.js   the dictionary of one language (src/words/*.js hold every key as [Arabic, English])
//   assets/style.css         tokens, components and every place's styles, with the fonts beside it
// Then SOURCE.json (the fingerprint of the source, which tests/guards/test_studio_assets.py recomputes without Node, and the
// list of files shipped) and the weight budgets: a build that grows past one fails and says by how much.
import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import zlib from 'node:zlib';
import { fileURLToPath, pathToFileURL } from 'node:url';
import * as esbuild from 'esbuild';

const HERE = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const SRC = path.join(HERE, 'src');
const OUT = path.resolve(HERE, '../eaos/data/studio');
// Keep in step with SOURCES in tests/guards/test_studio_assets.py
export const SOURCES = ['package.json', 'package-lock.json', 'scripts/build.mjs', 'src', '../docs/studio-actions.json', '../eaos/data/words.json'];
const KB = 1024;
const BUDGETS = [
  { name: 'first page script (gzip)', files: ['boot.js', 'assets/studio.js', 'assets/words-ar.js', 'assets/status.js'], gzip: true, max: 240 * KB, target: 200 * KB },
  { name: 'stylesheet (gzip)', files: ['assets/style.css'], gzip: true, max: 48 * KB },
  { name: 'whole Studio on disk', files: null, gzip: false, max: 6 * KB * KB },
];

const walk = dir => fs.readdirSync(dir, { withFileTypes: true }).flatMap(e => (e.isDirectory() ? walk(path.join(dir, e.name)) : [path.join(dir, e.name)]));
const fail = message => { console.error(message); process.exit(1); };

/** The keys the Studio takes from the one words catalog (eaos/data/words.json, M3.5), the engine's too: each check stage's
 *  title and what it does, each path's name, each kind of problem's name for one card. */
const CATALOG = path.resolve(HERE, '../eaos/data/words.json');
function catalogWords() {
  const catalog = JSON.parse(fs.readFileSync(CATALOG, 'utf8'));
  const table = {};
  for (const [id, stage] of Object.entries(catalog.stages)) { table[`ac.stage.${id}`] = stage.title; table[`ac.stage.${id}.does`] = stage.does; }
  for (const [id, p] of Object.entries(catalog.paths)) table[`ac.path.${id}`] = p.name;
  for (const [id, kind] of Object.entries(catalog.kinds)) table[`kind.${id}`] = kind.one;
  return table;
}

/** Every src/words/*.js and the catalog's keys as one dictionary per language; a key twice, a missing language or a
 *  plural without its forms stops the build. */
async function words() {
  const out = { ar: {}, en: {} }, seen = {};
  const tables = [['eaos/data/words.json', catalogWords()]];
  for (const file of fs.readdirSync(path.join(SRC, 'words')).filter(f => f.endsWith('.js')).sort()) {
    tables.push([file, (await import(pathToFileURL(path.join(SRC, 'words', file)).href)).default]);
  }
  for (const [file, table] of tables) {
    for (const [key, pair] of Object.entries(table)) {
      if (seen[key]) fail(`words: ${key} is in ${seen[key]} and ${file}`);
      seen[key] = file;
      if (!Array.isArray(pair) || pair.length !== 2 || pair.some(v => v == null || v === '')) fail(`words: ${file} ${key} needs [Arabic, English]`);
      const [ar, en] = pair;
      if (typeof ar !== typeof en) fail(`words: ${file} ${key}: one language is a plural and the other is not`);
      if (typeof ar === 'object' && !(ar.other && en.one && en.other)) fail(`words: ${file} ${key}: a plural needs Arabic other and English one and other`);
      out.ar[key] = ar; out.en[key] = en;
    }
  }
  return out;
}

/** Which place holds each sheet: every `sheet('<name>'` in a place's sources. */
function sheetsOf(places) {
  const owner = {};
  for (const place of places) {
    for (const file of walk(path.join(SRC, 'places', place)).filter(f => f.endsWith('.js'))) {
      for (const m of fs.readFileSync(file, 'utf8').matchAll(/\b(?:sheet|outlineSheet)\(\s*'([\w-]+)'/g)) {
        if (owner[m[1]] && owner[m[1]] !== place) fail(`sheet ${m[1]} is registered in ${owner[m[1]]} and ${place}`);
        owner[m[1]] = place;
      }
    }
  }
  return owner;
}

/** A place reaches the core through 'eaos' (self.EAOS), its own folder and the kits (a folder of src/places without
 *  index.js: helpers several of one builder's places share, stateless, bundled into each); a second copy of the core in
 *  a place's bundle would hold a second state. */
const placeImports = place => ({
  name: 'eaos-place',
  setup(build) {
    build.onResolve({ filter: /^eaos$/ }, () => ({ path: 'eaos', namespace: 'eaos' }));
    build.onLoad({ filter: /.*/, namespace: 'eaos' }, () => ({ contents: 'module.exports = self.EAOS', loader: 'js' }));
    build.onResolve({ filter: /^\./ }, args => {
      const target = path.resolve(args.resolveDir, args.path);
      const folder = path.relative(path.join(SRC, 'places'), target).split(path.sep)[0];
      const kit = !folder.startsWith('..') && !fs.existsSync(path.join(SRC, 'places', folder, 'index.js'));
      if (folder !== place && !kit) return { errors: [{ text: `${place} imports ${args.path}: a place imports 'eaos', its own files and the kits only` }] };
      return undefined;
    });
  },
});

function digest() {
  const files = SOURCES.flatMap(entry => {
    const full = path.join(HERE, entry);
    return fs.statSync(full).isFile() ? [full] : walk(full);
  }).map(f => path.relative(HERE, f).split(path.sep).join('/')).sort();
  const hash = crypto.createHash('sha256');
  for (const name of files) { hash.update(`${name}\0`); hash.update(fs.readFileSync(path.join(HERE, name))); }
  return hash.digest('hex');
}

const common = { bundle: true, minify: true, format: 'iife', target: 'es2020', charset: 'utf8', legalComments: 'none', logLevel: 'warning' };

async function build() {
  const places = fs.readdirSync(path.join(SRC, 'places')).filter(d => fs.existsSync(path.join(SRC, 'places', d, 'index.js'))).sort();
  const dictionary = await words();
  fs.rmSync(OUT, { recursive: true, force: true });
  fs.mkdirSync(path.join(OUT, 'assets'), { recursive: true });
  await esbuild.build({ ...common, entryPoints: [path.join(SRC, 'core/main.js')], outfile: path.join(OUT, 'assets/studio.js'),
    define: { __EAOS_SHEETS__: JSON.stringify(sheetsOf(places)) } });
  await Promise.all(places.map(place => esbuild.build({ ...common, entryPoints: [path.join(SRC, 'places', place, 'index.js')],
    outfile: path.join(OUT, 'assets', `${place}.js`), plugins: [placeImports(place)] })));
  for (const lang of ['ar', 'en']) {
    fs.writeFileSync(path.join(OUT, `assets/words-${lang}.js`), `(self.EAOS_WORDS=self.EAOS_WORDS||{}).${lang}=${JSON.stringify(dictionary[lang])};\n`);
  }
  await esbuild.build({ ...common, format: undefined, target: undefined, entryPoints: [path.join(SRC, 'css/index.css')], outfile: path.join(OUT, 'assets/style.css'),
    loader: { '.woff2': 'file' }, assetNames: '[name]' });
  fs.copyFileSync(path.join(SRC, 'index.html'), path.join(OUT, 'index.html'));
  fs.copyFileSync(path.join(SRC, 'boot.js'), path.join(OUT, 'boot.js'));
  fs.copyFileSync(path.join(SRC, 'fonts/OFL-LICENSE.txt'), path.join(OUT, 'assets/FONT-LICENSE.txt'));
  const shipped = walk(OUT).map(f => path.relative(OUT, f).split(path.sep).join('/')).sort();
  fs.writeFileSync(path.join(OUT, 'SOURCE.json'), JSON.stringify({ source_sha256: digest(), files: shipped }, null, 1) + '\n');
  console.log(`shipped ${shipped.length} files to ${path.relative(process.cwd(), OUT) || OUT}: ${places.length} places, ${Object.keys(dictionary.ar).length} words`);
}

function budgets() {
  let over = 0;
  for (const b of BUDGETS) {
    const files = b.files ? b.files.map(f => path.join(OUT, f)) : walk(OUT);
    const total = files.reduce((sum, f) => sum + (b.gzip ? zlib.gzipSync(fs.readFileSync(f), { level: 9 }).length : fs.statSync(f).size), 0);
    const line = `${b.name}: ${(total / KB).toFixed(0)} KB of ${(b.max / KB).toFixed(0)} KB${b.target ? ` (target ${(b.target / KB).toFixed(0)} KB)` : ''}`;
    if (total > b.max) { over += 1; console.error(`over budget: ${line}`); } else console.log(line);
  }
  if (over) process.exit(1);
}

await build();
budgets();
