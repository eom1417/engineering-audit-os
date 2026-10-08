"""The Studio shipped in the package (eaos/data/studio) is built from today's source, offline, and ships nothing that
reaches the network (NS37.T1). Runs without Node: it recomputes the source fingerprint studio/scripts/ship.mjs
recorded, so a change to studio/ without a rebuild fails here."""
import hashlib
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STUDIO = ROOT / 'studio'
SHIPPED = ROOT / 'eaos/data/studio'
# Keep in step with SOURCES in studio/scripts/ship.mjs
SOURCES = ['index.html', 'package.json', 'package-lock.json', 'tsconfig.json', 'vite.config.ts', '.stylelintrc.json', 'public',
           'scripts/ship.mjs', 'src']
NAMESPACES = {'http://www.w3.org/1998/Math/MathML', 'http://www.w3.org/1999/xlink', 'http://www.w3.org/2000/svg',
              'http://www.w3.org/XML/1998/namespace', 'http://www.w3.org/1999/xhtml', 'https://react.dev/errors/',
              # TanStack Router's base for parsing a URL when the page's origin is opaque (file://): never requested
              'http://localhost'}


def source_digest():
    files = []
    for entry in SOURCES:
        path = STUDIO / entry
        files += [path] if path.is_file() else [p for p in path.rglob('*') if p.is_file()]
    digest = hashlib.sha256()
    for name in sorted(p.relative_to(STUDIO).as_posix() for p in files):
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

    def test_a_classic_script_with_fixed_names_opens_from_a_file(self):
        page = (SHIPPED / 'index.html').read_text(encoding='utf-8')
        self.assertIn('<script defer src="./assets/studio.js">', page)
        self.assertIn('<script src="./boot.js">', page)
        self.assertNotIn('type="module"', page)
        self.assertIn('href="./assets/style.css"', page)

    def test_the_content_security_policy_forbids_the_network(self):
        page = (SHIPPED / 'index.html').read_text(encoding='utf-8')
        policy = re.search(r'http-equiv="Content-Security-Policy" content="([^"]+)"', page).group(1)
        rules = dict((part.split()[0], part.split()[1:]) for part in policy.split(';') if part.strip())
        self.assertEqual(rules['default-src'], ["'none'"])
        self.assertEqual(rules['connect-src'], ["'none'"])
        for name in ('script-src', 'font-src', 'style-src', 'img-src'):
            self.assertTrue(all(source in ("'self'", "'unsafe-inline'", 'data:') for source in rules[name]), name)

    def test_no_asset_names_an_address_outside_the_studio(self):
        for name in ('index.html', 'boot.js', 'assets/studio.js', 'assets/style.css'):
            self.assertEqual(urls((SHIPPED / name).read_text(encoding='utf-8')), set(), name)

    def test_the_fonts_ship_with_their_licence(self):
        fonts = sorted(p.name for p in (SHIPPED / 'assets').glob('*.woff2'))
        self.assertTrue(any('arabic-arabic' in name for name in fonts) and any('mono' in name for name in fonts), fonts)
        self.assertIn('SIL Open Font License', (SHIPPED / 'assets/FONT-LICENSE.txt').read_text(encoding='utf-8'))
        style = (SHIPPED / 'assets/style.css').read_text(encoding='utf-8')
        for font in fonts:
            self.assertIn(font, style)


class Source(unittest.TestCase):
    """What the build's own linters enforce, checked again without Node so the suite catches a bypass."""

    def test_no_physical_left_or_right_in_the_studios_styles(self):
        physical = re.compile(r'(?<![\w-])(margin|padding|border)-(left|right)\b|(?<![\w-])(left|right)\s*:|text-align\s*:\s*(left|right)|float\s*:\s*(left|right)')
        found = [f'{p.relative_to(STUDIO)}:{n}' for p in (STUDIO / 'src').rglob('*.css')
                 for n, line in enumerate(p.read_text(encoding='utf-8').splitlines(), 1) if physical.search(line)]
        self.assertEqual(found, [])

    def test_colours_come_only_from_the_tokens(self):
        found = [f'{p.relative_to(STUDIO)}:{n}' for p in (STUDIO / 'src').rglob('*.css') if p.name != 'tokens.css'
                 for n, line in enumerate(p.read_text(encoding='utf-8').splitlines(), 1) if re.search(r'#[0-9a-fA-F]{3,8}\b|\brgba?\(|\bhsla?\(', line)]
        self.assertEqual(found, [])

    def test_every_dependency_is_pinned_to_one_version(self):
        package = json.loads((STUDIO / 'package.json').read_text(encoding='utf-8'))
        for name, version in {**package['dependencies'], **package['devDependencies']}.items():
            self.assertRegex(version, r'^\d+\.\d+\.\d+$', name)


if __name__ == '__main__':
    unittest.main()
