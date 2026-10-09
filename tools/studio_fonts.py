"""Subset the Studio's fonts into the unicode-range files of studio/src/design/fonts/.

The design's families and weights stay as they are (DESIGN.md §2.3: IBM Plex Sans Arabic 400/500/600, IBM Plex Mono
400/500). Each Fontsource file is cut into the ranges a page actually draws, so the browser downloads only the ranges
of the text it shows (the @font-face unicode-range of src/design/fonts.css). Everything else is kept as it is: the
outlines, the TrueType hinting (dropping it saves about a third more, but Chrome on Linux and Windows then rounds
glyphs and advances differently, so lines wrap differently), advances, kerning and every OpenType feature (Arabic
shaping). Phone and desktop screenshots of Home, Problems and Decisions in both languages are pixel-identical to the
Fontsource files.

  plex-arabic-<weight>      the Arabic block, ZWNJ/ZWJ and the marks Arabic text uses
  plex-arabic-ext-<weight>  Arabic Supplement, Extended-A/B and the presentation forms (read only when text has them)
  plex-latin-<weight>       Basic Latin, Latin-1 and general punctuation (digits are Latin in both languages)
  plex-mono-<weight>        IBM Plex Mono, Latin

The files are committed; studio/src/design/fonts/SOURCE.json records the digests of the Fontsource files they were
cut from and of each output. Regenerate after a Fontsource update (needs the pinned fontTools, tools/dev_setup.sh):

  .venv/bin/python tools/studio_fonts.py          # write the files
  .venv/bin/python tools/studio_fonts.py --check  # the sources are unchanged and the outputs match the record
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FONTSOURCE = ROOT / 'studio/node_modules/@fontsource'
OUT = ROOT / 'studio/src/design/fonts'
RECORD = OUT / 'SOURCE.json'
FONTTOOLS = '4.60.1'

# name -> (Fontsource file, unicode ranges). The ranges are the @font-face unicode-range of fonts.css.
ARABIC = 'U+0600-06FF, U+200C-200E, U+2010-2011, U+204F, U+2E41'
ARABIC_EXT = 'U+0750-077F, U+0870-088E, U+0890-0891, U+0897-08E1, U+08E3-08FF, U+FB50-FDFF, U+FE70-FE74, U+FE76-FEFC'
LATIN = ('U+0000-00FF, U+0131, U+0152-0153, U+02BB-02BC, U+02C6, U+02DA, U+02DC, U+0304, U+0308, U+0329, U+2000-206F, '
         'U+20AC, U+2122, U+2191, U+2193, U+2212, U+2215, U+FEFF, U+FFFD')


def faces() -> dict[str, tuple[str, str]]:
    found: dict[str, tuple[str, str]] = {}
    for weight in (400, 500, 600):
        arabic = f'ibm-plex-sans-arabic/files/ibm-plex-sans-arabic-arabic-{weight}-normal.woff2'
        found[f'plex-arabic-{weight}'] = (arabic, ARABIC)
        found[f'plex-arabic-ext-{weight}'] = (arabic, ARABIC_EXT)
        found[f'plex-latin-{weight}'] = (f'ibm-plex-sans-arabic/files/ibm-plex-sans-arabic-latin-{weight}-normal.woff2', LATIN)
    for weight in (400, 500):
        found[f'plex-mono-{weight}'] = (f'ibm-plex-mono/files/ibm-plex-mono-latin-{weight}-normal.woff2', LATIN)
    return found


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def subset(source: Path, ranges: str, target: Path) -> None:
    from fontTools import subset as ft
    from fontTools.ttLib import TTFont
    options = ft.Options()
    options.layout_features = ['*']   # every shaping and kerning feature, as the source has them
    options.hinting = True            # the glyphs render pixel-identical to the source files
    options.flavor = 'woff2'
    options.name_IDs = ['*']          # the licence and copyright names stay in the file
    options.notdef_outline = True
    font = TTFont(source, recalcTimestamp=False)  # the same bytes on every run
    sub = ft.Subsetter(options)
    sub.populate(unicodes=ft.parse_unicodes(ranges.replace(' ', '')))
    sub.subset(font)
    font.flavor = 'woff2'
    font.save(target)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--check', action='store_true', help='verify the sources and outputs against SOURCE.json')
    args = parser.parse_args()
    record = json.loads(RECORD.read_text(encoding='utf-8')) if RECORD.is_file() else {}
    if args.check:
        problems = []
        for name, (source, _) in faces().items():
            entry = record.get('files', {}).get(name)
            if not entry:
                problems.append(f'{name}: not recorded')
                continue
            if (FONTSOURCE / source).is_file() and digest(FONTSOURCE / source) != entry['source_sha256']:
                problems.append(f'{name}: {source} changed; regenerate')
            if digest(OUT / f'{name}.woff2') != entry['sha256']:
                problems.append(f'{name}: the committed file differs from the record')
        print('\n'.join(problems) or 'fonts OK')
        return 1 if problems else 0
    import fontTools
    if fontTools.version != FONTTOOLS:
        print(f'fontTools {FONTTOOLS} is pinned (found {fontTools.version}); run tools/dev_setup.sh', file=sys.stderr)
        return 1
    OUT.mkdir(parents=True, exist_ok=True)
    files = {}
    for name, (source, ranges) in faces().items():
        target = OUT / f'{name}.woff2'
        subset(FONTSOURCE / source, ranges, target)
        files[name] = {'source': f'@fontsource/{source}', 'source_sha256': digest(FONTSOURCE / source),
                       'unicode_range': ranges, 'sha256': digest(target), 'bytes': target.stat().st_size}
        print(f'{name}: {(FONTSOURCE / source).stat().st_size} -> {target.stat().st_size} bytes')
    RECORD.write_text(json.dumps({'tool': f'fonttools=={FONTTOOLS}', 'files': files}, indent=1) + '\n', encoding='utf-8')
    return 0


if __name__ == '__main__':
    sys.exit(main())
