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
