"""NS46.T20 owner-request acceptance (eaos-dev/planning/live-scan-map/PLAN.md), planned 2026-10-09: a real check of a
real project, watched live in the shipped Studio.

The evidence is $EAOS_MEASURE/live-scan-map/trial.json, written by tools/live_scan_map_trial.py from the progress file
and manifest of a real `eaos start` and from what tools/live_scan_map_trial.mjs saw in Chromium while it ran. A replay
of a recorded file never counts. Every case must pass live, and every view of each moment (early, middle, done) at
390, 768 and 1440 px, Arabic and English, light and dark, must pass the screen gates with its screenshot on disk.
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'acceptance'))
sys.path.insert(0, str(ROOT / 'tools'))
import north_star_measure as measure
from test_branch_control import VIEWS, judge

CASES = (
    'progress_file_written_by_the_pipeline', 'every_stage_ends_exactly_once', 'folded_state_equals_the_manifest',
    'stages_come_from_the_declaration', 'engines_steps_from_the_tool_registry', 'facts_steps_per_extractor',
    'absent_stages_carry_their_reason', 'studio_followed_the_run_live', 'page_opened_mid_run_shows_the_full_state',
    'glow_and_moving_light_mid_run', 'reduced_motion_stops_all_motion', 'banner_on_other_pages_while_running',
    'record_kept_after_the_run',
)


def moments(path):
    """(missing) views per moment: each of the 12 views must pass in each of the three moments."""
    import json
    try: trial = json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError): return ['no trial']
    rows = [r for r in trial.get('views') or [] if isinstance(r, dict)]
    missing = [f"failing view {r.get('moment')} {r.get('viewport')} {r.get('lang')} {r.get('theme')}" for r in rows if r.get('pass') is not True]
    for moment in ('early', 'middle', 'done'):
        shown = {(r.get('viewport'), r.get('lang'), r.get('theme')) for r in rows if r.get('moment') == moment and r.get('pass') is True}
        missing += [f'{moment} view {w} {l} {t}' for w, l, t in sorted(VIEWS - shown)]
    return missing


class LiveScanMap(unittest.TestCase):
    def test_a_real_check_is_watched_live_in_the_shipped_studio(self):
        path = measure.REPORTS / 'live-scan-map' / 'trial.json'
        missing = judge(path, CASES) + moments(path)
        self.assertEqual(missing, [], 'the live scan map is not proven live: ' + '; '.join(missing))


class ProgressContract(unittest.TestCase):
    """Live scan map v2, phase 1 (eaos-dev/planning/live-scan-map/PLAN-v2.md section 5), planned 2026-10-09: the
    progress contract holds on real recorded checks (tests/fixtures/progress/: one that ended, one stopped with Ctrl-C,
    one killed), read here with nothing but the schema and the fold.

    I1: every declared stage ends exactly once in a run that ended (also the stopped one), and never twice in the
    killed one. I4 (Python half): the fold of each recording is its committed expected JSON. I5: done <= total on
    every step, and a counted step that ends ok ends with done == total. Every line validates against
    eaos/data/schemas/progress.json."""

    def recordings(self):
        import json
        found = {p.stem: [json.loads(line) for line in p.read_text(encoding='utf-8').splitlines() if line.strip()]
                 for p in sorted((ROOT / 'tests/fixtures/progress').glob('*.jsonl'))}
        self.assertEqual(set(found), {'complete', 'stopped', 'killed'}, 'the three recorded real checks')
        return found

    def test_every_line_validates_against_the_versioned_schema(self):
        import json
        import jsonschema
        schema = json.loads((ROOT / 'eaos/data/schemas/progress.json').read_text(encoding='utf-8'))
        check = jsonschema.Draft202012Validator(schema, format_checker=jsonschema.Draft202012Validator.FORMAT_CHECKER)
        for name, rows in self.recordings().items():
            self.assertEqual([(r.get('seq'), e.message) for r in rows for e in check.iter_errors(r)], [], name)
            self.assertEqual(rows[0]['schema'], schema['x-version'], name)

    def test_one_end_per_declared_stage(self):
        for name, rows in self.recordings().items():
            declared = sorted(s['name'] for s in rows[0]['stages'])
            ends = [r['stage'] for r in rows if r['event'] == 'stage.ended']
            if name == 'killed':
                self.assertNotEqual(rows[-1]['event'], 'run.ended')
                self.assertEqual(len(ends), len(set(ends)), name)
            else:
                self.assertEqual((rows[-1]['event'], sorted(ends)), ('run.ended', declared), name)
        self.assertEqual(self.recordings()['stopped'][-1]['status'], 'STOPPED')

    def test_counted_steps_are_bounded(self):
        for name, rows in self.recordings().items():
            steps = [r for r in rows if r['event'] == 'stage.step']
            self.assertTrue(steps, name)
            self.assertEqual([r['seq'] for r in steps if not 0 <= r['done'] <= r['total']], [], name)
            self.assertEqual([r['seq'] for r in steps if r.get('kind') == 'count' and r['status'] == 'ok' and r['done'] != r['total']], [], name)

    def test_the_python_fold_of_each_recording_is_its_expected_json(self):
        import json
        sys.path.insert(0, str(ROOT))
        from eaos.progress import fold
        for name, rows in self.recordings().items():
            expected = json.loads((ROOT / f'tests/fixtures/progress/{name}.fold.json').read_text(encoding='utf-8'))
            self.assertEqual(fold(rows), expected, name)
