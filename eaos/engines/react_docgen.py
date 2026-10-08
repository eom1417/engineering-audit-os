"""react-docgen: every exported React component with the props it declares, read from the source.

Each component becomes a record (granularity `symbol`): its name, its file, its props with their types and
whether they are required, and the type names its props refer to. That is what lets EAOS tell a component's
props apart from the project's data models (`vehicle: Vehicle` names a model the component receives).

The CLI stops at the first file it cannot parse and writes nothing, so the files go in batches, and a batch
that fails is split in two until the file that fails stands alone; it is named in the coverage, the rest is
read. A file that is not UTF-8 (one saved as UTF-16) is named the same way without being given to it.
"""
import json
import os
import re
from pathlib import Path

from . import tool
from .contract import ERROR, OBSERVED, Report
from .process import run, which

NAME = BINARY = 'react-docgen'
PINNED = tool.pinned(NAME)
EXCLUDED = ('.git', 'node_modules', '.venv', 'venv', 'dist', 'build', '.next', 'vendor', 'coverage')
EXTENSIONS = ('.tsx', '.jsx')
BATCH = 150
GLOB_SPECIAL = re.compile(r'([()\[\]{}*?!+@])')
# Past this many files that fail alone, the tool itself is failing, not the files: the run is an error.
MAX_FAILURES = 25


class TooManyFailures(RuntimeError):
    pass


def capabilities():
    return []


def version():
    return tool.package_version(NAME, BINARY)


def sources(target, exclude=()):
    """(readable files, unreadable files): every .tsx and .jsx file, relative, outside the skipped directories."""
    target, readable, unreadable = Path(target), [], []
    skipped = EXCLUDED + tuple(exclude)
    for base, directories, names in os.walk(target):
        # An entry may be a path (`components/ui`), so a directory is tested by its relative path, not its name.
        here = Path(base).relative_to(target).as_posix()
        directories[:] = sorted(d for d in directories
                                if not tool.excluded(d if here == '.' else f'{here}/{d}', skipped))
        for name in sorted(names):
            if not name.endswith(EXTENSIONS): continue
            path = Path(base) / name
            try: path.read_bytes().decode('utf-8')
            except (OSError, UnicodeDecodeError): unreadable.append(path.relative_to(target).as_posix()); continue
            readable.append(path.relative_to(target).as_posix())
    return readable, unreadable


def type_names(node, out=None):
    """The capitalised type names a prop type refers to (`Vehicle | null` -> Vehicle)."""
    out = set() if out is None else out
    if isinstance(node, dict):
        name = node.get('name')
        if isinstance(name, str) and name[:1].isupper() and name.isidentifier(): out.add(name)
        for value in node.values(): type_names(value, out)
    elif isinstance(node, list):
        for value in node: type_names(value, out)
    return out


def prop_type(detail):
    kind = detail.get('tsType') or detail.get('flowType') or detail.get('type') or {}
    return kind.get('raw') or kind.get('name')


def records(parsed):
    """{file: [component]} as metric rows, one per component."""
    rows = []
    for path, components in sorted(parsed.items()):
        for component in components or []:
            props = component.get('props') or {}
            rows.append({'path': tool.relative(path), 'line': None, 'symbol': component.get('displayName'), 'granularity': 'symbol',
                         'measurements': {'record': 'react_component',
                                          'props': [{'name': name, 'type': prop_type(detail), 'required': bool(detail.get('required'))}
                                                    for name, detail in sorted(props.items())],
                                          'prop_count': len(props),
                                          'referenced_types': sorted(type_names([d.get('tsType') or d.get('flowType') or {}
                                                                                 for d in props.values()]))}})
    return rows


def _batch(files, target, folder, index, failures, seconds):
    """Parse one batch; on failure split it until the failing file stands alone. Returns {file: [component]}."""
    output = folder / f'docgen-{index}.json'
    output.unlink(missing_ok=True)
    command = [which(BINARY), '--out', str(output), '--resolver', 'find-all-exported-components',
               *(GLOB_SPECIAL.sub(r'\\\1', path) for path in files)]
    code, _, error, spent = run(command, cwd=target)
    seconds.append(spent)
    if code == 0 and output.is_file():
        return json.loads(output.read_text(encoding='utf-8'))
    if len(files) == 1:
        failures.append(files[0])
        if len(failures) > MAX_FAILURES: raise TooManyFailures(error.strip()[-300:] or f'exit {code}')
        return {}
    middle = len(files) // 2
    first = _batch(files[:middle], target, folder, f'{index}a', failures, seconds)
    return {**first, **_batch(files[middle:], target, folder, f'{index}b', failures, seconds)}


def analyze(target, workdir, exclude=(), formats=None):
    declined = tool.declined(NAME, BINARY, target, probe=version)
    if declined: return declined
    found = version()
    target = Path(target).resolve()
    folder = Path(workdir) / NAME
    folder.mkdir(parents=True, exist_ok=True)
    files, unreadable = sources(target, exclude)
    parsed, failures, seconds = {}, [], []
    try:
        for start in range(0, len(files), BATCH):
            parsed.update(_batch(files[start:start + BATCH], target, folder, start // BATCH, failures, seconds))
    except TooManyFailures as problem:
        return Report(NAME, found, PINNED, ERROR, seconds=sum(seconds),
                      reason=f'{len(failures)} files failed one by one: {problem}'[:300])
    output = folder / 'react-docgen.json'
    output.write_text(json.dumps(parsed, indent=1, sort_keys=True), encoding='utf-8')
    metrics = records(parsed)
    return Report(NAME, found, PINNED, OBSERVED, seconds=sum(seconds), raw=str(output), metrics=metrics,
                  coverage={'status': 'observed', 'files': len(files), 'files_with_components': len(parsed),
                            'components': len(metrics), 'components_with_props': sum(1 for m in metrics if m['measurements']['prop_count']),
                            'resolver': 'find-all-exported-components',
                            'unparsed_files': sorted(failures), 'unreadable_files': sorted(unreadable)})
