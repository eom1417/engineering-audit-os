"""NS46.T19 owner-request acceptance (STUDIO-COMPLETE.md, "Live scan freshness, local time and full governance"),
planned 2026-10-09: real repositories, the live command centre and the shipped Studio in a real browser.

The evidence is $EAOS_MEASURE/scan-freshness/trial.json. Every case must say it ran live; mocked clients and unit tests
never count. Time zones are pinned in the browser, at least two non-UTC ones including a half-hour offset.
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'acceptance'))
sys.path.insert(0, str(ROOT / 'tools'))
import north_star_measure as measure
from test_branch_control import judge

CASES = (
    'scan_records_branch_full_commit_dirty_and_times', 'legacy_report_labelled_with_rescan', 'fresh_state',
    'behind_commits_files_listed_without_reload', 'branch_switch', 'detached_head', 'dirty_tree', 'rewritten_branch',
    'refresh_on_focus_interval_and_run_completion', 'device_time_zone_non_utc', 'half_hour_offset_time_zone',
    'time_zone_override_persisted', 'relative_and_exact_zoned_times_everywhere', 'utc_storage_unchanged',
    'rescan_roundtrip_live_command_centre', 'rescan_this_branch', 'copy_fallback_complete',
    'static_snapshot_read_only_open_live', 'governance_current_actionable_direct',
)


class ScanFreshness(unittest.TestCase):
    def test_real_repositories_and_live_studio_cover_every_freshness_and_time_case(self):
        missing = judge(measure.REPORTS / 'scan-freshness' / 'trial.json', CASES)
        self.assertEqual(missing, [], 'scan freshness and local time are not proven live: ' + '; '.join(missing))
