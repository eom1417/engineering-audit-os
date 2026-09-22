"""Build a blind, time-boxed review pack from an audit of an external project."""
import argparse
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DEFAULT_TARGET = Path('/workspace/upstream-src/enola')
REVIEW_FILES = (
    'README.md', 'RUN.md', 'EXECUTIVE.md', 'DECISION-BRIEF.md', 'PRODUCT-REPORT.md',
    'BLOCKERS.md', 'SYSTEM-MAP.md', 'FLOWS.md', 'DOMAIN-AND-DATA.md', 'CONTRACTS.md',
    'VERIFICATION-MAP.md', 'RISK-REGISTER.md', 'ONBOARDING.md', 'SUSTAINABILITY.md',
    'TARGET-ARCHITECTURE.md', 'transform-plan.md', 'LOAD-MODEL.md', 'PLAN',
    'dossier.json', 'plan.json', 'target-architecture.json', 'transform-plan.json',
    'load-model.json', 'run-manifest.json',
)
QUESTIONS = (
    'Is the central claim correct?',
    'Is each claim specific enough to verify?',
    'Does each claim identify an exact source location?',
    'Can you execute a task card without asking its author a question?',
    'Does every task state an observable acceptance command?',
    'Is the task order logical and dependency-aware?',
    'Are system boundaries and their responsibilities clear?',
    'Does the target architecture follow from cited evidence?',
    'Are uncertainty and missing evidence visible?',
    'Would this report materially improve your next engineering decision?',
)


def instructions(target_name):
    return f"""# Independent review pack

This pack contains an EAOS report for `{target_name}`, a project not used to tune this review.
Allow at most 30 minutes. Review only `REPORT/`; do not inspect the source repository or ask the
tool authors for interpretation. Start with `REPORT/EXECUTIVE.md`, follow its cited records, then
sample at least three claims and three task cards.

For every question in `REVIEW-FORM.md`, choose exactly one of **Yes**, **No**, or
**Cannot judge** and cite the report location that determined your answer. Do not infer missing
evidence. A negative answer and an inability to judge are valid results. Return the completed form
unchanged except for the answer and evidence fields.

The pack deliberately contains no expected answers, ground truth, score, or author commentary.
"""


def form():
    lines = ['# Independent judgement form', '',
             'Reviewer name or identifier: ', 'Review date: ', 'Minutes spent (maximum 30): ', '',
             'Allowed answers: `Yes` / `No` / `Cannot judge`.', '']
    for index, question in enumerate(QUESTIONS, 1):
        lines += [f'## Q{index}. {question}', '', 'Answer: ', 'Evidence in REPORT/: ', '']
    lines += ['## Verbatim closing comment', '', 'Comment: ', '']
    return '\n'.join(lines)


def build(destination, target=DEFAULT_TARGET):
    from eaos.pipeline import execute
    destination, target = Path(destination).resolve(), Path(target).resolve()
    if not target.is_dir(): raise FileNotFoundError(f'external review target does not exist: {target}')
    destination.mkdir(parents=True, exist_ok=True)
    report_destination = destination / 'REPORT'
    if report_destination.exists(): shutil.rmtree(report_destination)
    report_destination.mkdir()
    with tempfile.TemporaryDirectory(prefix='eaos-review-') as temporary:
        report = Path(temporary) / 'report'
        manifest = execute(target, report, language='en', site=False)
        if manifest['status'] == 'INCOMPLETE':
            raise RuntimeError('external audit was incomplete; review pack was not built')
        for name in REVIEW_FILES:
            source = report / name
            if not source.exists(): continue
            target_path = report_destination / name
            if source.is_dir(): shutil.copytree(source, target_path)
            else:
                target_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target_path)
    (destination / 'README.md').write_text(instructions(target.name), encoding='utf-8')
    (destination / 'REVIEW-FORM.md').write_text(form(), encoding='utf-8')
    return destination


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', required=True)
    parser.add_argument('--target', default=str(DEFAULT_TARGET))
    args = parser.parse_args(argv)
    result = build(args.out, args.target)
    print(result)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
