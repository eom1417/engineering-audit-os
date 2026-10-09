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


class BackendCoverage(unittest.TestCase):
    """Live scan map v2, phase 2 (eaos-dev/planning/live-scan-map/PLAN-v2.md sections 2, 3 and 5), planned 2026-10-09:
    every long piece of work says where it is, measured on real checks.

    The evidence is $EAOS_MEASURE/live-scan-map/backend.json, written by tools/progress_trial.py collect from one real
    round: tools/progress_determinism.py on a corpus project with its engines, a check of it killed with SIGKILL while
    `engines` ran, and two whole checks of EAOS's own repository (progress on, then off). I2: the folded progress equals
    run-manifest.json on the corpus check and on the EAOS check. I6: the corpus check with progress on and off wrote
    the same bytes, timestamps, durations and run ids excluded. I7: on the EAOS check, the progress file is under
    1 MB and its cost is under 2% of the run, both as measured (on against off) and as bounded (lines written and
    programs sampled, each at its measured cost). I8: the killed run reads `interrupted` within 30 s on the same
    machine, and `stalled` within 31 s (30 s of silence, read every 0.25 s) for a reader that cannot see the process.
    Counted steps are seen in `plan` and `transform` of the EAOS check, each ending at its total."""

    def record(self):
        import json
        path = measure.REPORTS / 'live-scan-map' / 'backend.json'
        self.assertTrue(path.is_file(), f'no real round recorded at {path}')
        return json.loads(path.read_text(encoding='utf-8'))

    def test_the_folded_progress_equals_the_manifest_on_real_checks(self):
        record = self.record()
        for name in ('I2_corpus', 'I2_develop'):
            self.assertEqual(((record.get(name) or {}).get('equal'), (record.get(name) or {}).get('differences')), (True, []), name)
            self.assertGreaterEqual(record[name]['stages'], 26, name)

    def test_progress_changes_no_byte_of_the_report(self):
        i6 = self.record()['I6']
        self.assertTrue(i6['engines'], 'the corpus check ran its engines')
        self.assertGreater(i6['compared'], 100)
        self.assertEqual((i6['identical'], i6['differ'], i6['only_on'], i6['only_off']), (True, [], [], []))

    def test_the_cost_of_progress_on_a_check_of_eaos_itself(self):
        i7 = self.record()['I7']
        self.assertIn('engineering-audit-os', i7['project'])
        self.assertEqual({k: v['exit'] for k, v in i7['runs'].items()}, {'on': 0, 'off': 0})
        self.assertLess(i7['file_bytes'], 1_000_000)
        self.assertLess(i7['overhead_bound'], 0.02)
        self.assertLess(i7['overhead_measured'], 0.02)

    def test_a_killed_check_is_shown_stopped_within_thirty_seconds(self):
        i8 = self.record()['I8']
        self.assertEqual((i8['state_before_kill'], i8['running_stage_at_kill']), ('running', i8['stage']))
        self.assertIsNotNone(i8['seconds_to_interrupted_same_machine'])
        self.assertLessEqual(i8['seconds_to_interrupted_same_machine'], 30)
        self.assertIsNotNone(i8['seconds_to_stalled_other_machine'])
        self.assertLessEqual(i8['seconds_to_stalled_other_machine'], 31)

    def test_counted_steps_inside_plan_and_transform(self):
        counted = self.record()['counted_steps']
        for stage in ('plan', 'transform'):
            self.assertTrue(counted.get(stage), stage)
            self.assertTrue(all(0 <= done <= total and (status != 'ok' or done == total) for _, done, total, status in counted[stage]), stage)
            self.assertTrue(any(total > 0 and status == 'ok' for _, _, total, status in counted[stage]), stage)
