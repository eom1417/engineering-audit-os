"""What the assistant used, from what each call leaves: a check stage by stage, a run, a run still going."""
import json
import os
import unittest
from pathlib import Path

from eaos import usage
from shared_fixture import scratch

CLAUDE_RESULT = {'type': 'result', 'total_cost_usd': 0.34, 'duration_ms': 60000, 'num_turns': 3, 'modelUsage': {'claude-opus-5-5': {}},
                 'usage': {'input_tokens': 4, 'cache_creation_input_tokens': 27701, 'cache_read_input_tokens': 16794,
                           'output_tokens': 5889, 'output_tokens_details': {'thinking_tokens': 2117}}}


class UsageTests(unittest.TestCase):
    def test_a_check_is_counted_by_stage_and_a_run_still_going_by_its_messages(self):
        # EAOS, 2026-10-14: batch 5 cost $48 at API prices, 138 of 140 million tokens the conversation read again; no page said so
        report = Path(scratch()) / 'technical'
        node = report / 'nodes/card_triage/runs/now/decide'
        node.mkdir(parents=True)
        (report / 'run-manifest.json').write_text(json.dumps({'started_at': '2000-01-01T00:00:00+00:00'}))
        (node / 'stream.jsonl').write_text(json.dumps({'type': 'system'}) + '\n' + json.dumps(CLAUDE_RESULT) + '\n')
        (report / usage.FILE).write_text(json.dumps({**usage.row({'input_tokens': 10, 'output_tokens': 5}, cost=0.01), 'stage': 'translate'}) + '\n')
        found = usage.of_check(report)
        self.assertEqual({k: (v['cost_usd'], v['cache_read'], v['thinking']) for k, v in found['stages'].items()},
                         {'card_triage': (0.34, 16794, 2117), 'translate': (0.01, 0, 0)})
        self.assertEqual((found['total']['cost_usd'], found['total']['calls']), (0.35, 2))
        old = report / 'nodes/visual_reviewer/runs/old/decide'
        old.mkdir(parents=True)
        (old / 'stream.jsonl').write_text(json.dumps(CLAUDE_RESULT))
        os.utime(old / 'stream.jsonl', (0, 0))
        (report / 'run-manifest.json').write_text(json.dumps({'started_at': '2001-01-01T00:00:00+00:00'}))
        self.assertNotIn('visual_reviewer', usage.of_check(report)['stages'], "an older check's call is not this one's")
        going = [{'type': 'assistant', 'message': {'id': 'a', 'model': 'm', 'usage': {'input_tokens': 1, 'cache_read_input_tokens': 100, 'output_tokens': 2}}},
                 {'type': 'assistant', 'message': {'id': 'a', 'model': 'm', 'usage': {'input_tokens': 1, 'cache_read_input_tokens': 100, 'output_tokens': 9}}},
                 {'type': 'assistant', 'message': {'id': 'b', 'model': 'm', 'usage': {'input_tokens': 1, 'cache_read_input_tokens': 300, 'output_tokens': 4}}}]
        live = usage.from_stream([json.dumps(e) for e in going])
        self.assertEqual((live['cache_read'], live['output'], live['cost_usd']), (400, 13, None), 'each message once, its last count; no cost yet')
        # a run resumed with the person's answer, then tried again: one process, one result event, per turn
        turns = usage.from_stream([json.dumps(CLAUDE_RESULT), json.dumps({'type': 'system'}), json.dumps(CLAUDE_RESULT)])
        self.assertEqual((turns['cost_usd'], turns['output'], turns['calls']), (0.68, 11778, 2), 'every turn counts, not the last')
