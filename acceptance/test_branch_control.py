"""NS46.T18 owner-request acceptance (BRANCH-CONTROL.md), planned 2026-10-09: real repositories and the live Studio.

The evidence is $EAOS_MEASURE/branch-control/trial.json, written by a run against real temporary multi-branch git
repositories served by the live `eaos studio` command centre of the shipped build. Mocked clients, button presence and
unit tests never count: every case must say it ran live, and every view needs its screenshot on disk.
"""
import json
import sys
import unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import north_star_measure as measure
import north_star_studio as studio

CASES = (
    'inventory_local_remote_refs', 'detached_head_named_state', 'no_origin_valid_state', 'dirty_checkout_reported',
    'stale_remote_refs_last_known_until_fetch', 'ownership_known_and_unknown_by_provenance', 'worktree_status',
    'select_analysis_without_checkout_change', 'in_flight_runs_not_retargeted', 'run_branch_relation_restart_and_deleted_ref',
    'managed_wave_accept_report_ledger_exactly_once', 'isolated_merge_preview_expected_heads', 'stale_head_invalidates_preview',
    'dirty_target_refused', 'concurrent_mutation_locked', 'conflict_kept_and_resolution_proposal', 'failed_checks_block_merge',
    'protected_destination_refused_by_backend', 'invalid_names_and_cross_project_refused', 'auth_csrf_origin_failures_mutate_nothing',
    'merged_branch_deleted_with_recovery_ref', 'unmerged_delete_needs_extra_confirmation', 'remote_delete_separate_consent',
    'recovery_restores_branch', 'ui_selected_branch_report_consistency', 'ui_task_run_branch_links', 'ui_realtime_state',
    'ui_error_recovery', 'keyboard_and_44px_targets',
)
VIEWS = {(width, lang, theme) for width in (390, 768, 1440) for lang in ('ar', 'en') for theme in ('light', 'dark')}


def judge(path, cases, views=VIEWS):
    """(missing requirements) of one live trial file; [] when it passes."""
    try: trial = json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError): return [f'{path}: no trial']
    missing = []
    if trial.get('mocked') is not False or trial.get('kind') != 'live': missing.append('a live, explicitly unmocked run')
    if not trial.get('studio_source_sha256') or trial.get('studio_source_sha256') != studio.shipped(): missing.append('the shipped Studio digest')
    try: datetime.fromisoformat(str(trial.get('completed_at')))
    except ValueError: missing.append('a completed_at timestamp')
    rows = {row.get('id'): row for row in trial.get('cases') or [] if isinstance(row, dict)}
    for case in cases:
        row = rows.get(case) or {}
        if not (row.get('pass') is True and row.get('kind') == 'live' and str(row.get('evidence') or '').strip()):
            missing.append(f'case {case}')
    shown = set()
    for row in trial.get('views') or []:
        if not isinstance(row, dict): continue
        good = (row.get('pass') is True and row.get('width_equals_viewport') is True and row.get('initial_scroll_zero') is True
                and row.get('axe_violations') == 0 and row.get('small_targets') == 0
                and bool(row.get('screenshot')) and Path(str(row.get('screenshot'))).is_file())
        if good: shown.add((row.get('viewport'), row.get('lang'), row.get('theme')))
    missing += [f'view {width} {lang} {theme}' for width, lang, theme in sorted(views - shown)]
    return missing


class BranchControl(unittest.TestCase):
    def test_real_repositories_and_live_studio_cover_every_branch_control_case(self):
        missing = judge(measure.REPORTS / 'branch-control' / 'trial.json', CASES)
        self.assertEqual(missing, [], 'branch control is not proven live: ' + '; '.join(missing))
