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
    round: tools/progress_determinism.py on a corpus project, without and with its engines, a check of it killed with
    SIGKILL while `engines` ran, and two whole checks of EAOS's own repository (progress on, then off). I2: the folded
    progress equals run-manifest.json on the corpus check and on the EAOS check. I6: the corpus check with progress on
    and off wrote the same bytes, timestamps, durations and run ids excluded; with the external engines, whose own
    files and facts differ between any two runs of the same check (revised 2026-10-09 after the first round showed
    it), every file that differs with progress switched also differs between two runs that both write progress. I7: on the EAOS check, the progress file is under
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
        record = self.record()
        i6, engines = record['I6'], record['I6_engines']
        self.assertGreater(i6['compared'], 100)
        self.assertEqual((i6['identical'], i6['differ'], i6['only_on'], i6['only_off']), (True, [], [], []))
        self.assertEqual((engines['engines'], engines['project']), (True, i6['project']))
        self.assertGreater(engines['compared'], i6['compared'])
        self.assertEqual((engines['progress_adds_no_difference'], engines['differ_only_with_progress_switched']), (True, []))

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


class ServerAndEntry(unittest.TestCase):
    """Live scan map v2, phase 3 (eaos-dev/planning/live-scan-map/PLAN-v2.md sections 3.7, 3.8 and 7.3), planned
    2026-10-09: the person reaches the live map from the assistant.

    The evidence is $EAOS_MEASURE/live-scan-map/watch.json, written by tools/watch_trial.py from one real headless
    Claude Code session (`claude -p`, EAOS's MCP server, the EAOS tools and Read only) asked in plain Arabic to check a
    corpus project. The session called `audit`; its answer carried `watch`, the live map's address on this computer
    (`#/scan` with the launch token, redacted in the record); the Studio at that address answered /api/progress with
    that token, giving the check's flow of 26 declared stages beside the setup, safety and fix flows."""

    def test_a_real_assistant_session_gets_the_live_map_address_from_audit(self):
        import json
        import re
        path = measure.REPORTS / 'live-scan-map' / 'watch.json'
        self.assertTrue(path.is_file(), f'no real session recorded at {path}')
        record = json.loads(path.read_text(encoding='utf-8'))
        self.assertTrue(record['session'] and Path(record['transcript']).is_file(), 'the session and its transcript')
        self.assertTrue(record['audit_answers'], 'the assistant called audit')
        self.assertRegex(record['watch'], r'^http://127\.0\.0\.1:\d+/#/scan\?token=<redacted>$')
        self.assertIn(record['watch'], [answer.get('watch') for answer in record['audit_answers']])
        progress = record['progress']
        self.assertEqual((progress['status'], progress['stages'], progress['flows']), (200, 26, ['check', 'fix', 'safety', 'setup']))
        self.assertIsNotNone(progress['check_run'], 'the map shows the check the session started')
        self.assertFalse(re.search(r'token=(?!<redacted>)', path.read_text(encoding='utf-8')), 'no launch token is kept')


class FrontEnd(unittest.TestCase):
    """Live scan map v2, phase 4 (eaos-dev/planning/live-scan-map/PLAN-v2.md sections 4, 3.9 and 5), planned
    2026-10-09: the page.

    The evidence is the real trial's `front_end` checks in $EAOS_MEASURE/live-scan-map/trial.json, from what Chromium
    saw while a real check ran in the shipped Studio: I9 (the finished check replayed at 30x in the page, every glow and
    light it drew matched to its line of run-progress.jsonl), the polling fallback (the stream held back, the page read
    /api/progress and kept up with the run), the map's toolbar covering no stage in any view, the journey's four steps
    on every map view, the phone's bottom sheet and a produced file read in its sheet, each view passing its gates.
    I4's TypeScript half (the page's fold equals the Python fold on the recorded runs), I3's page half (a stage added
    in a test drawn with no front-end change) and the motion rules (400 ms per change, at most 3 lights, every glow and
    light matched on the recorded runs) are the Studio's own tests, run here."""

    CHECKS = ('i9_every_light_and_glow_matched', 'polling_fallback_carries_the_run', 'toolbar_never_covers_a_stage',
              'journey_strip_on_every_map_view', 'phone_bottom_sheet', 'produced_file_read_in_its_sheet')

    def test_the_page_passes_its_checks_in_the_real_trial(self):
        import json
        path = measure.REPORTS / 'live-scan-map' / 'trial.json'
        self.assertTrue(path.is_file(), f'no real trial at {path}')
        checks = json.loads(path.read_text(encoding='utf-8')).get('front_end') or {}
        self.assertEqual(sorted(checks), sorted(self.CHECKS))
        self.assertEqual([name for name, check in checks.items() if check.get('pass') is not True], [])
        replay = checks['i9_every_light_and_glow_matched']
        self.assertEqual(replay['unmatched'], [])
        self.assertGreaterEqual(replay['glows'], 5)
        self.assertGreaterEqual(replay['lights'], 1)

    def test_the_studio_fold_and_motion_hold_on_the_recorded_runs(self):
        import subprocess
        studio = ROOT / 'studio'
        self.assertTrue((studio / 'node_modules/.bin/vitest').is_file(), 'the Studio is not installed (npm ci in studio/)')
        run = subprocess.run([str(studio / 'node_modules/.bin/vitest'), 'run', 'src/data/scan.test.ts', 'src/pages/scan/live.test.ts'],
                             cwd=studio, capture_output=True, text=True, timeout=300)
        self.assertEqual(run.returncode, 0, run.stdout[-3000:] + run.stderr[-2000:])


class RealAcceptance(unittest.TestCase):
    """Live scan map v2, phase 5 (eaos-dev/planning/live-scan-map/PLAN-v2.md section 7), planned 2026-10-09: real
    acceptance, end to end.

    The evidence is $EAOS_MEASURE/live-scan-map/acceptance.json, written by tools/live_scan_map_acceptance.py from real
    runs only: 7.1 a check of EAOS's own develop watched from start to end (I2, I7, I9 on the live page, counted steps
    shown in plan, transform and engines, the running program shown in engines, a light seen leaving facts, a photo every
    30 s); 7.3 the live map reached from a real Claude Code `audit`, from `eaos start` and from the Studio's button; 7.4
    a check killed with SIGKILL shown interrupted within 30 s and resumed keeping every finished stage; 7.5 setup,
    safety and fix run on a corpus web app, each screen a step with its picture, the fix card by card; 7.6 the gated
    views of the same check; 7.7 the page open for the whole check, its main thread idle over 95% and its heap grown
    under 20 MB. 7.2 (through the Remote sign-in) needs the owner's signed-in browser: until it is run it is pending,
    never passed."""

    def test_every_item_of_section_seven_passes_on_real_runs(self):
        import json
        path = measure.REPORTS / 'live-scan-map' / 'acceptance.json'
        self.assertTrue(path.is_file(), f'no real acceptance at {path}')
        record = json.loads(path.read_text(encoding='utf-8'))
        self.assertEqual((record.get('kind'), record.get('mocked')), ('live', False))
        items = record.get('items') or {}
        self.assertEqual(sorted(items), ['7.1', '7.2', '7.3', '7.4', '7.5', '7.6', '7.7'])
        self.assertEqual([k for k, v in items.items() if v.get('pass') is not True and not (k == '7.2' and v.get('pending') == 'owner')], [])
