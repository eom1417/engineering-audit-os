"""The Studio shipped in the package (eaos/data/studio) is built from today's console source (console/), opens from a
file as classic scripts, ships nothing that reaches the network, and keeps its weight budgets. Runs without Node: it
recomputes the source fingerprint console/scripts/build.mjs recorded, so a change to console/ without a rebuild fails
here."""
import gzip
import hashlib
import json
import os
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONSOLE = ROOT / 'console'
SHIPPED = ROOT / 'eaos/data/studio'
# Keep in step with SOURCES in console/scripts/build.mjs
SOURCES = ['package.json', 'package-lock.json', 'scripts/build.mjs', 'src', '../docs/studio-actions.json']
NAMESPACES = {'http://www.w3.org/2000/svg'}


def source_digest():
    files = []
    for entry in SOURCES:
        path = CONSOLE / entry
        files += [path] if path.is_file() else [p for p in path.rglob('*') if p.is_file()]
    digest = hashlib.sha256()
    for name in sorted(Path(os.path.relpath(p, CONSOLE)).as_posix() for p in files):
        digest.update(f'{name}\0'.encode('utf-8'))
        digest.update((CONSOLE / name).read_bytes())
    return digest.hexdigest()


def urls(text):
    return {u for u in re.findall(r'https?://[^\s"\'`)<>\\]+', text) if u.rstrip('/') not in NAMESPACES}


def gzipped(*names):
    return sum(len(gzip.compress((SHIPPED / name).read_bytes(), 9)) for name in names)


class Shipped(unittest.TestCase):
    def test_the_shipped_studio_is_built_from_todays_console(self):
        recorded = json.loads((SHIPPED / 'SOURCE.json').read_text(encoding='utf-8'))
        self.assertEqual(recorded['source_sha256'], source_digest(),
                         'console/ changed since the last build: run npm run build in console/ and commit eaos/data/studio')
        shipped = sorted(p.relative_to(SHIPPED).as_posix() for p in SHIPPED.rglob('*') if p.is_file() and p.name != 'SOURCE.json')
        self.assertEqual(shipped, recorded['files'])

    def test_it_opens_from_a_file_as_classic_scripts_and_nothing_in_it_reaches_the_network(self):
        page = (SHIPPED / 'index.html').read_text(encoding='utf-8')
        for needle in ('<script defer src="./assets/studio.js">', '<script src="./boot.js"></script>', 'href="./assets/style.css"'):
            self.assertIn(needle, page)
        self.assertNotIn('type="module"', page)
        policy = re.search(r'http-equiv="Content-Security-Policy" content="([^"]+)"', page).group(1)
        rules = dict((part.split()[0], part.split()[1:]) for part in policy.split(';') if part.strip())
        self.assertEqual((rules['default-src'], rules['connect-src']), (["'none'"], ["'none'"]))
        for name in ('script-src', 'font-src', 'style-src', 'img-src'):
            self.assertTrue(all(source in ("'self'", "'unsafe-inline'", 'data:') for source in rules[name]), name)
        scripts = sorted(p.name for p in (SHIPPED / 'assets').glob('*.js'))
        self.assertIn('studio.js', scripts)
        self.assertTrue({'words-ar.js', 'words-en.js', 'status.js', 'waiting.js', 'problems.js'} <= set(scripts), scripts)
        for name in scripts:
            body = (SHIPPED / 'assets' / name).read_text(encoding='utf-8')
            self.assertNotIn('import(', body, name)
            if name not in ('studio.js', 'words-ar.js', 'words-en.js'):
                self.assertIn('self.EAOS', body, f'{name} reaches the core through self.EAOS only')
        for path in [SHIPPED / 'index.html', SHIPPED / 'boot.js', SHIPPED / 'assets/style.css', *(SHIPPED / 'assets').glob('*.js')]:
            self.assertEqual(urls(path.read_text(encoding='utf-8')), set(), path.name)

    def test_one_dictionary_per_language_with_the_same_words(self):
        words = {}
        for lang in ('ar', 'en'):
            text = (SHIPPED / f'assets/words-{lang}.js').read_text(encoding='utf-8')
            words[lang] = json.loads(text.split(f').{lang}=', 1)[1].rstrip().rstrip(';'))
        self.assertEqual(set(words['ar']), set(words['en']))
        self.assertGreater(len(words['ar']), 1000)

    def test_the_fonts_ship_with_their_licence_and_the_stylesheet_uses_each(self):
        fonts = sorted(p.name for p in (SHIPPED / 'assets').glob('*.woff2'))
        self.assertTrue(any('arabic' in name for name in fonts) and any('mono' in name for name in fonts), fonts)
        self.assertIn('SIL Open Font License', (SHIPPED / 'assets/FONT-LICENSE.txt').read_text(encoding='utf-8'))
        style = (SHIPPED / 'assets/style.css').read_text(encoding='utf-8')
        for font in fonts:
            self.assertIn(font, style)
        boot = (SHIPPED / 'boot.js').read_text(encoding='utf-8')
        for name in re.findall(r"'(ibm-plex-[a-z-]+-\d+-normal)'", boot):
            self.assertTrue((SHIPPED / 'assets' / f'{name}.woff2').is_file(), name)

    def test_the_weight_budgets_hold(self):
        # console/scripts/build.mjs BUDGETS, checked again without Node so the suite catches a bypass
        self.assertLessEqual(gzipped('boot.js', 'assets/studio.js', 'assets/words-ar.js', 'assets/status.js'), 240 * 1024)
        self.assertLessEqual(gzipped('assets/style.css'), 48 * 1024)
        self.assertLessEqual(sum(p.stat().st_size for p in SHIPPED.rglob('*') if p.is_file()), 6 * 1024 * 1024)


class Source(unittest.TestCase):
    """What the build relies on, checked without Node."""

    def test_styles_are_direction_neutral_colours_come_from_the_tokens_and_the_build_tool_is_pinned(self):
        physical = re.compile(r'(?<![\w-])(margin|padding|border)-(left|right)\b|(?<![\w-])(left|right)\s*:|text-align\s*:\s*(left|right)|float\s*:\s*(left|right)')
        colour = re.compile(r'#[0-9a-fA-F]{3,8}\b|\brgba?\(|\bhsla?\(')
        sides, colours = [], []
        for p in (CONSOLE / 'src/css').rglob('*.css'):
            for n, line in enumerate(p.read_text(encoding='utf-8').splitlines(), 1):
                if physical.search(line): sides.append(f'{p.name}:{n}')
                if p.name != 'tokens.css' and colour.search(line): colours.append(f'{p.name}:{n}')
        self.assertEqual((sides, colours), ([], []))
        package = json.loads((CONSOLE / 'package.json').read_text(encoding='utf-8'))
        for name, version in {**package.get('dependencies', {}), **package['devDependencies']}.items():
            self.assertRegex(version, r'^\d+\.\d+\.\d+$', name)

    def test_a_place_reaches_the_core_through_eaos_and_its_own_files_only(self):
        wrong = []
        for p in (CONSOLE / 'src/places').rglob('*.js'):
            for m in re.finditer(r"^import .*? from '([^']+)'|^import '([^']+)'", p.read_text(encoding='utf-8'), re.M):
                target = m.group(1) or m.group(2)
                if target != 'eaos' and not (target.startswith('./') and '..' not in target): wrong.append(f'{p.relative_to(CONSOLE)}: {target}')
        self.assertEqual(wrong, [])


if __name__ == '__main__':
    unittest.main()
