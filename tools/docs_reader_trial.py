"""A trial of the document reader (docs/STUDIO.md, Library): the shipped Studio opened from a file on a real report's
data, every document holding a Mermaid diagram read in the pinned Playwright, and what the reader drew counted.

    python tools/docs_reader_trial.py <report>/studio [--name <project>]

Each document is opened in Arabic, light, at 1440 and at 390; the trial waits until no diagram is still drawing,
then counts the ```mermaid blocks of its text, the figures the reader drew with an <svg> of real size, the figures
that fell back to their source, its tables, and the page's horizontal overflow at 390.

Writes $EAOS_MEASURE/docs-reader/trial.json:
  {diagrams, diagrams_drawn, diagrams_failed, tables, document, documents: [{path, diagrams, drawn, failed, tables,
   overflow_390}], data, shipped, minutes}
`document` is the gate's {doc_diagram}: the first document in reading order with a diagram and a table.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import dev_paths  # noqa: E402
import studio_gates  # noqa: E402
from eaos import toolchain  # noqa: E402

SHIPPED = ROOT / 'eaos/data/studio'
MERMAID = re.compile(r'^\s{0,3}```+\s*mermaid\s*$', re.M)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('data', type=Path, help="a report's studio/ folder")
    args = parser.parse_args()
    started = time.time()
    library = json.loads((args.data / 'library.json').read_text(encoding='utf-8'))
    texts = {d['id']: d.get('text') or '' for d in library.get('documents') or []}
    docs = [{'path': path, 'blocks': len(MERMAID.findall(text))} for path, text in sorted(texts.items()) if MERMAID.search(text)]
    document = studio_gates.studio_placeholders(args.data)['doc_diagram']
    with tempfile.TemporaryDirectory(prefix='eaos-docs-reader-') as folder:
        site = Path(folder) / 'studio'
        shutil.copytree(SHIPPED, site)
        for script in args.data.glob('*.js'):
            shutil.copy(script, site / script.name)
        config = Path(folder) / 'config.json'
        config.write_text(json.dumps({'folder': str(site), 'docs': docs, 'modules': str(toolchain.node_modules('playwright'))}), encoding='utf-8')
        done = subprocess.run(['node', str(ROOT / 'tools/docs_reader_trial.mjs'), str(config)], capture_output=True, text=True, timeout=1800,
                              env={**os.environ, 'PLAYWRIGHT_BROWSERS_PATH': str(toolchain.browsers())})
    lines = [line for line in done.stdout.splitlines() if line.startswith('{')]
    if done.returncode or not lines:
        sys.exit(f'docs_reader_trial.mjs exited {done.returncode}: {(done.stderr or done.stdout)[-1500:]}')
    rows = json.loads(lines[-1])['documents']
    result = {'diagrams': sum(r['diagrams'] for r in rows), 'diagrams_drawn': sum(r['drawn'] for r in rows),
              'diagrams_failed': sum(r['failed'] for r in rows), 'tables': sum(r['tables'] for r in rows),
              'document': document, 'documents': rows, 'data': str(args.data), 'shipped': json.loads((SHIPPED / 'SOURCE.json').read_text())['source_sha256'],
              'minutes': round((time.time() - started) / 60, 2)}
    out = dev_paths.MEASURE / 'docs-reader' / 'trial.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in result.items() if k != 'documents'}, ensure_ascii=False))
    print(f'wrote {out}')


if __name__ == '__main__':
    main()
