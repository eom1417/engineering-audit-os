"""Regenerate golden fact snapshots after a deliberate extractor change."""
import json
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from eaos.facts.run import collect
from eaos.facts.store import read_set
from test_golden_facts import FIXTURE, GOLDEN, SETS  # noqa: E402

with tempfile.TemporaryDirectory() as tmp:
    collect(FIXTURE, Path(tmp) / 'out', SETS)
    for name in SETS:
        (GOLDEN / f'{name}.json').write_text(json.dumps(read_set(Path(tmp) / 'out', name), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print('regenerated:', ', '.join(SETS))
