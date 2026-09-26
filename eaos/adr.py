"""Architecture decision records in MADR form: one file per decision, adr/ADR-NNN.md.

Each decision of target-architecture.json becomes the MADR sections a reader of any project already
knows: "## Context and Problem Statement", "## Considered Options" (every option, with the evidence),
"## Decision Outcome" (the choice and why), "### Consequences", and when to revisit it. The format is all
that is used; no log4brains (unmaintained since 2024-12). Text is wrapped at 80 columns and each file is
judged by markdownlint-cli2 with its default rules.
"""
import textwrap
from pathlib import Path

WIDTH = 80


def _wrap(text, first='', rest=''):
    return textwrap.wrap(str(text), WIDTH, initial_indent=first, subsequent_indent=rest,
                         break_long_words=False, break_on_hyphens=False) or [first.rstrip()]


def _title(decision):
    title = f"# {decision['id']}: {decision.get('component_id', 'decision')}"
    return title if len(title) <= WIDTH else title[:WIDTH - 1] + '…'


def render(decision):
    lines = [_title(decision), '', '## Context and Problem Statement', '']
    lines += _wrap(decision['problem'])
    lines += ['', 'Evidence:', '']
    lines += [f'- `{item}`' for item in decision['evidence']]
    lines += ['', '## Considered Options', '']
    for option in decision['options']:
        lines += _wrap(option, '- ', '  ')
    lines += ['', '## Decision Outcome', '']
    reason = decision['tradeoffs'][:1].lower() + decision['tradeoffs'][1:]
    lines += _wrap(f"Chosen option: \"{decision['chosen']}\", because {reason}")
    lines += ['', '### Consequences', '']
    for item in decision['consequences']:
        lines += _wrap(item, '- ', '  ')
    lines += ['', '### Migration', '']
    for index, step in enumerate(decision['migration'], 1):
        lines += _wrap(step, f'{index}. ', '   ')
    lines += ['', '### When to Revisit', '']
    lines += _wrap('When the cited evidence changes: run the audit again; a decision whose evidence is gone '
                   'is closed, and one whose evidence grew is reopened.')
    return '\n'.join(lines) + '\n'


def write_all(out, decisions):
    """Write adr/ADR-NNN.md for every decision and remove the files of decisions that no longer exist."""
    directory = Path(out) / 'adr'
    directory.mkdir(parents=True, exist_ok=True)
    expected = set()
    for decision in decisions:
        path = directory / f"{decision['id']}.md"
        expected.add(path.name)
        path.write_text(render(decision), encoding='utf-8')
    for path in directory.glob('ADR-*.md'):
        if path.name not in expected: path.unlink()
    return sorted(expected)
