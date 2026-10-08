"""The Studio shipped in the package (eaos/data/studio) is built from today's source, offline, and ships nothing that
reaches the network (NS37.T1). Runs without Node: it recomputes the source fingerprint studio/scripts/ship.mjs
recorded, so a change to studio/ without a rebuild fails here."""
import hashlib
import json
import os
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STUDIO = ROOT / 'studio'
SHIPPED = ROOT / 'eaos/data/studio'
# Keep in step with SOURCES in studio/scripts/ship.mjs
SOURCES = ['index.html', 'package.json', 'package-lock.json', 'tsconfig.json', 'vite.config.ts', '.stylelintrc.json', 'public',
           'scripts/ship.mjs', 'src', '../docs/studio-actions.json']
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


class GateMatrix(unittest.TestCase):
    """studio/gate-matrix.json: the Studio's routes for the one screen gate (tools/studio_gates.py --studio)."""

    @classmethod
    def setUpClass(cls):
        import sys
        sys.path.insert(0, str(ROOT / 'tools'))
        import studio_gates
        cls.gates = studio_gates
        cls.matrix = json.loads((STUDIO / 'gate-matrix.json').read_text(encoding='utf-8'))

    def test_every_page_is_named_once_and_audited_in_known_viewports_and_variants(self):
        pages = self.matrix['pages']
        self.assertEqual(len({p['name'] for p in pages}), len(pages))
        viewports = {v['name'] for v in self.matrix['viewports']}
        variants = {v['name'] for v in self.matrix['variants']}
        self.assertEqual({v['width'] for v in self.matrix['viewports']}, {390, 768, 1440})
        self.assertEqual(variants, {'ar-light', 'ar-dark', 'en-light', 'en-dark'})
        for page in pages:
            self.assertEqual(sum(k in page for k in ('path', 'file')), 1, page)
            self.assertLessEqual(set(page.get('viewports', viewports)), viewports, page)
            self.assertLessEqual(set(page.get('variants', variants)), variants, page)
        self.assertTrue(any('file' in p for p in pages), 'the Studio is also opened from a file')
        self.assertTrue(any(p.get('actions') for p in pages), 'an overlay is opened before it is measured')

    def test_every_variant_says_what_the_page_must_apply(self):
        for variant in self.matrix['variants']:
            lang, theme = variant['name'].split('-')
            self.assertEqual(variant['query'], {'lang': lang, 'theme': theme})
            self.assertEqual(variant['expect'], {'dir': 'rtl' if lang == 'ar' else 'ltr', 'attributes': {'lang': lang, 'data-theme': theme}})

    def test_placeholders_are_a_card_with_evidence_and_the_component_holding_most_cards(self):
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            data = Path(folder)
            cards = [{'id': 'TASK-1', 'evidence': [], 'paths': ['src/a/x.ts']},
                     {'id': 'TASK-2', 'evidence': ['FACT-1'], 'paths': ['src/b/y.ts', 'src/b/c/z.ts']},
                     {'id': 'TASK-3', 'evidence': [], 'paths': ['src/b/w.ts']}]
            (data / 'cards.json').write_text(json.dumps({'cards': cards}), encoding='utf-8')
            story = {'current': {'components': [{'name': n} for n in ('(root)', 'src', 'src/a', 'src/b', 'src/b/c')]}}
            (data / 'story.json').write_text(json.dumps(story), encoding='utf-8')
            self.assertEqual(self.gates.studio_placeholders(data), {'card': 'TASK-2', 'component': 'src/b', 'path': 'none'})
            paths = [{'id': 'p/short', 'reach': 3, 'steps': [1] * 4}, {'id': 'p/long', 'reach': 3, 'steps': [1] * 90},
                     {'id': 'p/a', 'reach': 3, 'steps': [1] * 70}, {'id': 'p/near', 'reach': 1, 'steps': [1] * 99}]
            (data / 'paths.json').write_text(json.dumps({'paths': paths}), encoding='utf-8')
            self.assertEqual(self.gates.studio_placeholders(data)['path'], 'p/a')   # furthest, then longest within 60
            (data / 'paths.json').unlink()
            pages = dict((e['name'], e) for e, _ in self.gates.studio_pages(self.matrix, data, 'http://127.0.0.1:1/', data))
        self.assertEqual(pages['system-focus']['url'], 'http://127.0.0.1:1/index.html#/system?focus=src%2Fb')
        self.assertEqual(pages['problem']['url'], 'http://127.0.0.1:1/index.html#/problems?card=TASK-2')
        self.assertTrue(pages['file-home']['url'].startswith('file://') and pages['file-home']['url'].endswith('/index.html#/'))
        self.assertNotIn('path', pages['home'])
