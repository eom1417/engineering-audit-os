"""A real run of an AI node (NS46.T15, docs/STUDIO.md D11): the person's own assistant, headless, decides a node of a
project's latest check, and the result is recorded for the plan's acceptance.

    python tools/node_trial.py FleetManageWeb --report <a full report of its check> [--node card_triage]
                               [--assistant claude|codex] [--lang ar] [--seconds 3000] [--usd 15] [--limit N]

The report is copied once to $EAOS_MEASURE/nodes/<project>/report (its engines/ folder linked, not copied), so the run
never writes into the folder it was given. The project's code is read from the pinned corpus ($EAOS_CORPUS/<project>)
for the excerpts at each fact, as untrusted data; none of it runs. Then the Studio data is exported again from that
report, so studio/nodes.json and the inbox show the run.

Writes $EAOS_MEASURE/nodes/<project>/<node>.json:
  {project, node, assistant, model, at, real, state, method, why, seconds, cost_usd, cached, decisions, subjects,
   share_with_evidence, routes{decision: count}, dropped[], by_kind, omitted, batches, eaos}
and <node>.md beside it: the decisions, route by route, for a person to review.
"""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import dev_paths  # noqa: E402
from eaos.studio import export, ideal, nodes  # noqa: E402
from eaos.studio.actions import adapters as assistants  # noqa: E402
from eaos.studio.nodes import core, triage  # noqa: E402

MEASURE = dev_paths.MEASURE / 'nodes'


def prepare(source, folder):
    """The run's own copy of the report: everything but engines/, which is linked (it is only read)."""
    report = folder / 'report'
    if report.is_dir(): return report
    shutil.copytree(source, report, ignore=lambda where, names: ['engines'] if Path(where) == Path(source) else [])
    if (Path(source) / 'engines').is_dir(): (report / 'engines').symlink_to(Path(source).resolve() / 'engines')
    return report


def review(project, record, cards):
    lines = [f'# {project}: {record["title"]}', '',
             f"Decided by {record['assistant'] or 'the rules'} ({record['model'] or '-'}) at {record['at']}, "
             f"{record['method']}; {len(record['decisions'])} decisions, {len(record['dropped'])} dropped by the evidence check; "
             f"{record['seconds']} s, cost {record['cost_usd']} USD.", '']
    for route in record['routes']:
        lines += [f"## {route['decision']} -> {route['to']} ({len(route['subjects'])})", '', f"_{route['when']}_", '']
        by = {d['subject']: d for d in record['decisions']}
        for subject in route['subjects']:
            d, card = by[subject], cards.get(subject) or {}
            lines.append(f"- **{subject}** {card.get('title', '')} [{card.get('kind')}, {card.get('severity')}]: {d['why']} "
                         f"(confidence {d['confidence']}; evidence {', '.join(d['evidence'][:4])})")
        lines.append('')
    if record['dropped']:
        lines += ['## Dropped by the evidence check', '']
        lines += [f"- {row['subject']}: {row['why']} (cited {', '.join(row['evidence'][:4])})" for row in record['dropped']]
    return '\n'.join(lines) + '\n'


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('project')
    parser.add_argument('--report', required=True, help="a full report of the project's check (the folder holding plan.json)")
    parser.add_argument('--node', default='card_triage', choices=[n.name for n in nodes.NODES])
    parser.add_argument('--assistant', default='claude', choices=('claude', 'codex'))
    parser.add_argument('--lang', default='ar', choices=('ar', 'en'))
    parser.add_argument('--seconds', type=float, help="the node's time budget (its declared one by default)")
    parser.add_argument('--usd', type=float, help="the node's cost budget (its declared one by default)")
    parser.add_argument('--limit', type=int, help='the card triage reads at most this many cards, most severe first')
    parser.add_argument('--commit', help='the commit a frozen copy (no .git) was made from, for the record')
    args = parser.parse_args(argv)
    folder = MEASURE / args.project
    folder.mkdir(parents=True, exist_ok=True)
    report = prepare(Path(args.report).expanduser().resolve(), folder)
    adapter = assistants.installed()[args.assistant]
    if not adapter.available():
        print(f'{adapter.name} is not installed and logged in here', file=sys.stderr)
        return 2
    node = nodes.node(args.node)
    budget = nodes.Budget(args.seconds or node.budget.seconds, args.usd if args.usd is not None else node.budget.usd)
    corpus = dev_paths.CORPUS / args.project
    say = lambda en, ar: print(en, flush=True)
    extra = {'limit': args.limit} if args.limit else {}
    records = nodes.run(report, names=[args.node], adapters={args.assistant: adapter}, project=corpus if corpus.is_dir() else None,
                        lang=args.lang, budget=budget, fresh=True, say=say, **extra)
    record = records.get(args.node)
    if record is None:
        print(f'{args.node} had nothing to read in this report', file=sys.stderr)
        return 1
    exported = export.export(report, args.lang, args.project)
    known = ideal.known_ids(report)
    model_decisions = [d for d in record['decisions'] if d['source'] == 'model']
    data = triage.inputs(report, project=corpus if corpus.is_dir() else None, **extra) if args.node == 'card_triage' else None
    from eaos import build_info
    commit = subprocess.run(['git', '-C', str(ROOT), 'rev-parse', '--short', 'HEAD'], capture_output=True, text=True).stdout.strip()
    run = {'project': args.project, 'node': args.node, 'assistant': record['assistant'] or adapter.name, 'model': record['model'],
           'at': record['at'], 'real': True, 'state': record['state'], 'method': record['method'], 'why': record['why'],
           'seconds': record['seconds'], 'cost_usd': record['cost_usd'], 'cached': record['cached'], 'decisions': len(model_decisions),
           'subjects': len(record['decisions']), 'share_with_evidence': core.share(record['decisions'], known),
           'routes': {r['decision']: len(r['subjects']) for r in record['routes']}, 'dropped': record['dropped'],
           'by_kind': triage.precision(report) if args.node == 'card_triage' else None,
           'omitted': (data or {}).get('omitted'), 'batches': len(triage.batches(data)) if data else None,
           'budget': record['budget'], 'export_errors': exported['errors'],
           'eaos': {'commit': commit or args.commit or None, 'digest': build_info.digest()}, 'corpus_code': corpus.is_dir()}
    (folder / f'{args.node}.json').write_text(json.dumps(run, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    cards = {c['id']: c for c in ideal._cards(report)}
    (folder / f'{args.node}.md').write_text(review(args.project, record, cards), encoding='utf-8')
    print(f"wrote {folder / (args.node + '.json')}: {run['state']} by {run['method']}, {run['decisions']} decisions by the model, "
          f"routes {run['routes']}, share {run['share_with_evidence']}", flush=True)
    return 0 if record['method'] == 'model' else 1


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
