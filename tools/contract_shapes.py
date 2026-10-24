"""The JSON-schema building blocks every artifact contract is written with (tools/make_contracts.py)."""

S, I, N, B = {'type': 'string'}, {'type': 'integer'}, {'type': 'number'}, {'type': 'boolean'}
NS = {'type': ['string', 'null']}
NN = {'type': ['number', 'null']}
NI = {'type': ['integer', 'null']}
STAGE = {'type': 'string', 'pattern': '^S(0[1-9]|1[0-5])$'}


def obj(props, required=None, extra=True):
    out = {'type': 'object', 'required': list(props) if required is None else required, 'properties': props}
    if not extra: out['additionalProperties'] = False
    return out


def arr(items, min_items=0):
    out = {'type': 'array', 'items': items}
    if min_items: out['minItems'] = min_items
    return out


def enum(*values): return {'type': 'string', 'enum': list(values)}
