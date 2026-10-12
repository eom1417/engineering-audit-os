"""The Studio shipped in the package (eaos/data/studio) is built from today's source, offline, and ships nothing that
reaches the network. Runs without Node: it recomputes the source fingerprint studio/scripts/ship.mjs
recorded, so a change to studio/ without a rebuild fails here."""
import hashlib
import json
import os
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STUDIO = ROOT / 'studio'
SHIPPED = ROOT / 'eaos/data/studio'
# Keep in step with SOURCES in studio/scripts/ship.mjs
SOURCES = ['index.html', 'package.json', 'package-lock.json', 'tsconfig.json', 'vite.config.ts', '.stylelintrc.json', 'public',
           'scripts/ship.mjs', 'src', '../docs/studio-actions.json']
NAMESPACES = {'http://www.w3.org/1998/Math/MathML', 'http://www.w3.org/1999/xlink', 'http://www.w3.org/2000/svg',
              'http://www.w3.org/XML/1998/namespace', 'http://www.w3.org/2000/xmlns/', 'http://www.w3.org/1999/xhtml', 'https://react.dev/errors/',
              # TanStack Router's base for parsing a URL when the page's origin is opaque (file://): never requested
              'http://localhost'}


def source_digest():
    files = []
    for entry in SOURCES:
        path = STUDIO / entry
        files += [path] if path.is_file() else [p for p in path.rglob('*') if p.is_file()]
    digest = hashlib.sha256()
    for name in sorted(Path(os.path.relpath(p, STUDIO)).as_posix() for p in files):
        digest.update(f'{name}\0'.encode('utf-8'))
        digest.update((STUDIO / name).read_bytes())
    return digest.hexdigest()


def urls(text):
    found = set(re.findall(r'https?://[^\s"\'`)<>\\]+', text))
    return {u for u in found if u.rstrip('/') not in {n.rstrip('/') for n in NAMESPACES} and not any(u.startswith(n) for n in NAMESPACES)}


class Shipped(unittest.TestCase):
    def test_the_shipped_studio_is_built_from_todays_source(self):
        recorded = json.loads((SHIPPED / 'SOURCE.json').read_text(encoding='utf-8'))
        self.assertEqual(recorded['source_sha256'], source_digest(),
                         'studio/ changed since the last build: run npm run build in studio/ and commit eaos/data/studio')
        shipped = sorted(p.relative_to(SHIPPED).as_posix() for p in SHIPPED.rglob('*') if p.is_file() and p.name != 'SOURCE.json')
        self.assertEqual(shipped, recorded['files'])

    def test_it_opens_from_a_file_as_classic_scripts_and_nothing_in_it_reaches_the_network(self):
        page = (SHIPPED / 'index.html').read_text(encoding='utf-8')
        for needle in ('<script defer src="./assets/studio.js">', '<script src="./boot.js">', 'href="./assets/style.css"'):
            self.assertIn(needle, page)
        self.assertNotIn('type="module"', page)
        policy = re.search(r'http-equiv="Content-Security-Policy" content="([^"]+)"', page).group(1)
        rules = dict((part.split()[0], part.split()[1:]) for part in policy.split(';') if part.strip())
        self.assertEqual((rules['default-src'], rules['connect-src']), (["'none'"], ["'none'"]))
        for name in ('script-src', 'font-src', 'style-src', 'img-src'):
            self.assertTrue(all(source in ("'self'", "'unsafe-inline'", 'data:') for source in rules[name]), name)
        # vite.config.ts classicChunks: the entry runs at once, every other chunk only registers its body
        entry = (SHIPPED / 'assets/studio.js').read_text(encoding='utf-8')
        self.assertIn('(function(){var chunks=self.EAOS_CHUNKS', entry, 'the entry carries the chunk loader')
        self.assertNotIn('import(', entry)
        names = sorted(p.name for p in (SHIPPED / 'assets').glob('*.js') if p.name != 'studio.js')
        self.assertTrue(names, 'pages other than Home and Problems are their own chunks')
        for name in names:
            body = (SHIPPED / 'assets' / name).read_text(encoding='utf-8')
            self.assertTrue(body.startswith(f'(self.EAOS_CHUNKS=self.EAOS_CHUNKS||{{}})["{name}"]=function(require,exports,module){{'), name)
            self.assertNotIn('import(', body, name)
        for name in ('index.html', 'boot.js', 'assets/style.css', 'assets/studio.js', *(f'assets/{n}' for n in names)):
            self.assertEqual(urls((SHIPPED / name).read_text(encoding='utf-8')), set(), name)

    def test_the_fonts_ship_with_their_licence_and_boot_preloads_only_fonts_the_stylesheet_uses(self):
        fonts = sorted(p.name for p in (SHIPPED / 'assets').glob('*.woff2'))
        self.assertTrue(any(name.startswith('plex-arabic-') for name in fonts) and any('mono' in name for name in fonts), fonts)
        self.assertIn('SIL Open Font License', (SHIPPED / 'assets/FONT-LICENSE.txt').read_text(encoding='utf-8'))
        style = (SHIPPED / 'assets/style.css').read_text(encoding='utf-8')
        for font in fonts:
            self.assertIn(font, style)
        preloaded = re.findall(r"'(plex-[a-z]+-[0-9]+)'", (SHIPPED / 'boot.js').read_text(encoding='utf-8'))
        self.assertGreaterEqual(len(preloaded), 4, preloaded)
        for name in preloaded:
            self.assertTrue((SHIPPED / 'assets' / f'{name}.woff2').is_file(), name)
            self.assertIn(f'{name}.woff2', style)


class Source(unittest.TestCase):
    """What the build's own linters enforce, checked again without Node so the suite catches a bypass."""

    def test_styles_are_direction_neutral_colours_come_from_the_tokens_and_dependencies_and_fonts_are_pinned(self):
        physical = re.compile(r'(?<![\w-])(margin|padding|border)-(left|right)\b|(?<![\w-])(left|right)\s*:|text-align\s*:\s*(left|right)|float\s*:\s*(left|right)')
        colour = re.compile(r'#[0-9a-fA-F]{3,8}\b|\brgba?\(|\bhsla?\(')
        sides, colours = [], []
        for p in (STUDIO / 'src').rglob('*.css'):
            for n, line in enumerate(p.read_text(encoding='utf-8').splitlines(), 1):
                if physical.search(line): sides.append(f'{p.relative_to(STUDIO)}:{n}')
                if p.name != 'tokens.css' and colour.search(line): colours.append(f'{p.relative_to(STUDIO)}:{n}')
        self.assertEqual((sides, colours), ([], []))
        package = json.loads((STUDIO / 'package.json').read_text(encoding='utf-8'))
        for name, version in {**package['dependencies'], **package['devDependencies']}.items():
            self.assertRegex(version, r'^\d+\.\d+\.\d+$', name)
        # tools/studio_fonts.py cuts each Fontsource face into unicode ranges; fonts.css declares each file once with
        # the range it was cut to, so a page downloads only what its text uses
        done = subprocess.run([sys.executable, str(ROOT / 'tools/studio_fonts.py'), '--check'], capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        record = json.loads((STUDIO / 'src/design/fonts/SOURCE.json').read_text(encoding='utf-8'))['files']
        css = (STUDIO / 'src/design/fonts.css').read_text(encoding='utf-8')
        for name, entry in record.items():
            self.assertIn(f"url('./fonts/{name}.woff2') format('woff2'); unicode-range: {entry['unicode_range']};", css, name)


if __name__ == '__main__':
    unittest.main()
