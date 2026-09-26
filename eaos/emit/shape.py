"""The shape of the files whose own tools cannot check them without running: Toxiproxy's proxy list, the
fault experiments, the ZAP automation plan and the readiness checklist. `python -m eaos.emit.shape KIND FILE` exits 0 when the file
has the shape its tool reads, and prints every way it does not."""
import json
import sys

from ..artifact_contracts import contracts, validate

S = {'type': 'string', 'minLength': 1}
SHAPES = {
    'toxiproxy': {'type': 'array', 'minItems': 1, 'items': {
        'type': 'object', 'required': ['name', 'listen', 'upstream', 'enabled'],
        'properties': {'name': S, 'listen': {'type': 'string', 'pattern': r'^[\w.]+:\d+$'}, 'upstream': S, 'enabled': {'type': 'boolean'}}}},
    'zap': {'type': 'object', 'required': ['env', 'jobs'], 'properties': {
        'env': {'type': 'object', 'required': ['contexts'], 'properties': {'contexts': {'type': 'array', 'minItems': 1, 'items': {
            'type': 'object', 'required': ['name', 'urls'], 'properties': {'name': S, 'urls': {'type': 'array', 'minItems': 1}}}}}},
        'jobs': {'type': 'array', 'minItems': 1, 'items': {'type': 'object', 'required': ['type'], 'properties': {
            'type': {'type': 'string', 'enum': ['spider', 'requestor', 'passiveScan-wait', 'report']}}}}}},
    'checklist': {'type': 'object', 'required': ['schema_version', 'items'], 'properties': {'items': {
        'type': 'array', 'minItems': 1, 'items': {'type': 'object', 'required': ['id', 'title', 'command', 'why'],
                                                  'properties': {'id': S, 'title': S, 'command': S, 'why': S}}}}},
}


def problems(kind, data):
    if kind == 'experiments': return validate(data, contracts()['nfr-experiments'])
    return validate(data, SHAPES[kind])


def main(argv):
    kind, path = argv
    try: data = json.loads(open(path, encoding='utf-8').read())
    except (OSError, ValueError) as error:
        print(f'{path}: {error}')
        return 1
    found = problems(kind, data)
    for line in found: print(line)
    return 1 if found else 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
