"""A real planning run of the ideal (NS46.T14, docs/STUDIO.md D10): the person's own assistant, headless, plans every
Target/Ideal view of a project's latest check on top of the rules, and the result is recorded for the plan's acceptance.

    python tools/ideal_trial.py FleetManageWeb --report <a full report of its check> [--assistant claude|codex] [--lang ar]

The report is copied once to $EAOS_MEASURE/ideal/<project>/report (its engines/ folder linked, not copied), so the run
never writes into the folder it was given. The project's own documents are read from the pinned corpus
($EAOS_CORPUS/<project>) as untrusted data; none of the project's code runs. Then the Studio data is exported again from
that report, so studio/ideal.json and every section's provenance show the run.

Writes $EAOS_MEASURE/ideal/<project>/run.json:
  {project, assistant, model, at, real, state, message, passes, seconds, share_with_evidence, raw_share, draft_share,
   elements, views{<view>: {rules, planned, departures, questions, method}}, dropped[], departures[], open_questions[],
   critique{missed, risks, order}, bundle_bytes, eaos}
and comparison.md beside it: the rules' target against the planned ideal, view by view.
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
from eaos.studio import export, ideal  # noqa: E402
from eaos.studio.actions import adapters as assistants  # noqa: E402

MEASURE = dev_paths.MEASURE / 'ideal'


def prepare(source, folder):
    """The run's own copy of the report: everything but engines/, which is linked (it is only read)."""
    report = folder / 'report'
    if report.is_dir(): return report
    shutil.copytree(source, report, ignore=lambda where, names: ['engines'] if Path(where) == Path(source) else [])
    if (Path(source) / 'engines').is_dir(): (report / 'engines').symlink_to(Path(source).resolve() / 'engines')
    return report


def comparison(project, body, record):
    lines = [f'# {project}: the rules\' target against the planned ideal', '',
             f"Planned by {record.get('assistant')} ({record.get('model')}) at {record.get('at')}; "
             f"{record.get('elements')} elements kept, {len(record.get('dropped') or [])} dropped by the evidence check; "
             f"share with evidence {record.get('share')} (before the check {record.get('raw_share')}, the draft {record.get('draft_share')}).", '',
             '| View | Rules elements | Planned elements | Same | Changed | Added | Departures | Questions |', '|---|---|---|---|---|---|---|---|']
    for name, view in body['views'].items():
        kinds = [d['kind'] for d in view['differences']]
        lines.append(f"| {name} | {view['rules']['count']['value']} | {(view['planned'] or {}).get('count', {}).get('value', '-')} | "
                     f"{kinds.count('same')} | {kinds.count('changed')} | {kinds.count('added')} | "
                     f"{len(view['provenance']['departures'])} | {len(view['provenance']['open_questions'])} |")
    for name, view in body['views'].items():
        if not view['planned']: continue
        lines += ['', f'## {name}', '', f"Rules: {view['rules']['summary']}", '', f"Planned: {view['planned']['summary']}", '']
        for element in view['planned']['elements']:
            lines.append(f"- **{element['operation']}** {element['title']} (subject {element.get('subject')}; cites {', '.join(element['cites'][:4])})")
        for departure in view['provenance']['departures']:
            lines.append(f"- departure on {departure.get('element')}: the rules say {departure['rule_says']}; the plan chose "
                         f"{departure['plan_chose']} because {departure['because']}")
    if body['evidence']['dropped']:
        lines += ['', '## Dropped by the evidence check', '']
        lines += [f"- {row['view']} / {row['id']}: {row.get('title')} ({row['why']})" for row in body['evidence']['dropped']]
    if body['questions']:
        lines += ['', '## Open questions (to the Decisions inbox)', '']
        lines += [f"- [{q['view']}] {q['question']} (recommendation: {q.get('recommendation')})" for q in body['questions']]
    return '\n'.join(lines) + '\n'


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('project')
    parser.add_argument('--report', required=True, help='a full report of the project\'s check (the folder holding target-architecture.json)')
    parser.add_argument('--assistant', default='claude', choices=('claude', 'codex'))
    parser.add_argument('--lang', default='ar', choices=('ar', 'en'))
    parser.add_argument('--timeout', type=int, default=ideal.TIMEOUT)
    parser.add_argument('--commit', help='the commit a frozen copy (no .git) was made from, for the record')
    args = parser.parse_args(argv)
    folder = MEASURE / args.project
    folder.mkdir(parents=True, exist_ok=True)
    report = prepare(Path(args.report).expanduser().resolve(), folder)
    adapter = assistants.installed()[args.assistant]
    if not adapter.available():
        print(f'{adapter.name} is not installed and logged in here', file=sys.stderr)
        return 2
    corpus = dev_paths.CORPUS / args.project
    say = lambda en, ar: print(en, flush=True)
    result = ideal.plan(report, project=corpus if corpus.is_dir() else None, lang=args.lang, adapters={args.assistant: adapter},
                        timeout=args.timeout, say=say)
    print(json.dumps({k: result.get(k) for k in ('state', 'elements', 'share', 'raw_share', 'model')}, ensure_ascii=False), flush=True)
    exported = export.export(report, args.lang, args.project)
    body = ideal.section(report, args.lang)
    record = json.loads((report / 'ideal/plan.json').read_text(encoding='utf-8')) if result['state'] == 'planned' else {}
    from eaos import build_info
    commit = subprocess.run(['git', '-C', str(ROOT), 'rev-parse', '--short', 'HEAD'], capture_output=True, text=True).stdout.strip()
    eaos = {'commit': commit or args.commit or None, 'digest': build_info.digest()}
    run = {'project': args.project, 'assistant': result.get('assistant') or adapter.name, 'model': result.get('model'),
           'at': result.get('at') or (body['runs'][-1]['at'] if body['runs'] else None), 'real': True, 'state': result['state'],
           'message': result['message'], 'passes': result.get('passes') or [], 'seconds': result.get('seconds'),
           'share_with_evidence': record.get('share'), 'raw_share': record.get('raw_share'), 'draft_share': record.get('draft_share'),
           'elements': record.get('elements') or 0,
           'views': {name: {'method': view['provenance']['method'], 'rules': view['rules']['count']['value'],
                            'planned': (view['planned'] or {}).get('count', {}).get('value'),
                            'departures': len(view['provenance']['departures']), 'questions': len(view['provenance']['open_questions'])}
                     for name, view in body['views'].items()},
           'dropped': record.get('dropped') or [], 'departures': (record.get('ideal') or {}).get('departures') or [],
           'open_questions': (record.get('ideal') or {}).get('open_questions') or [], 'critique': record.get('critique'),
           'bundle_bytes': record.get('bundle_bytes'), 'export_errors': exported['errors'], 'eaos': eaos,
           'corpus_documents': corpus.is_dir()}
    (folder / 'run.json').write_text(json.dumps(run, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    if record: (folder / 'comparison.md').write_text(comparison(args.project, body, record), encoding='utf-8')
    print(f"wrote {folder / 'run.json'}: {run['state']}, {run['elements']} elements, share {run['share_with_evidence']}", flush=True)
    return 0 if result['state'] == 'planned' else 1


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
