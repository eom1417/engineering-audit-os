"""Answer questions strictly from the records, with citations — or say plainly that nothing answers it.

This is retrieval over the dossier and the fact sets. It never writes prose about code it has not
indexed, so an empty answer is a real answer: the records do not cover the question yet.
"""
from pathlib import Path
import re
from .facts.store import read_set
from .workspace import read

STOP = {'the', 'a', 'an', 'of', 'in', 'is', 'are', 'how', 'what', 'where', 'which', 'does', 'do', 'to', 'and',
        'for', 'from', 'this', 'that', 'it', 'on', 'with', 'أين', 'كيف', 'ما', 'هل', 'من', 'في', 'على', 'الى', 'إلى'}
SETS = ['syntax', 'resolve', 'entrypoints', 'config', 'metrics', 'domain', 'history', 'graph', 'flows', 'verification']


def terms(question):
    words = [w.lower() for w in re.findall(r'[\w./-]{2,}', question)]
    return [w for w in words if w not in STOP]


def score(text, wanted):
    lowered = (text or '').lower()
    return sum(3 if word in lowered.split() else 1 for word in wanted if word in lowered)


def records(out):
    out = Path(out)
    dossier = read(out / 'dossier.json') if (out / 'dossier.json').is_file() else {'claims': [], 'questions': []}
    sets = {}
    for name in SETS:
        if (out / 'facts' / (name + '.json')).is_file(): sets[name] = read_set(out, name)
    return dossier, sets


def candidates(dossier, sets):
    rows = []
    for claim in dossier.get('claims', []):
        rows.append({'kind': 'claim', 'id': claim['id'], 'text': claim['statement'],
                     'detail': f"{claim['confidence']} · {claim['claim_type']}",
                     'citation': ', '.join(claim.get('evidence_ids', []) or claim.get('fact_ids', []))[:80]})
    for question in dossier.get('questions', []):
        rows.append({'kind': 'open question', 'id': question['id'], 'text': question['question'],
                     'detail': question['source'], 'citation': ''})
    for fact in sets.get('entrypoints', {}).get('facts', []):
        value = fact['value']
        rows.append({'kind': 'entry point', 'id': fact['id'][:12], 'detail': f"{value['surface']} {value['http_method'] or ''}".strip(),
                     'text': f"{value['route']} → {value['handler']} [{value['framework']}]",
                     'citation': f"{fact['location']['path']}:{fact['location'].get('start_line') or 1}"})
    for fact in sets.get('flows', {}).get('facts', []):
        value = fact['value']
        rows.append({'kind': 'flow', 'id': value['flow_id'],
                     'text': f"{value['entry']['surface']} {value['entry']['route']} touches " + ', '.join(value['touched_files']),
                     'detail': f"{len(value['steps'])} steps",
                     'citation': f"{value['entry']['path']}:{value['entry']['line']}"})
    for fact in sets.get('domain', {}).get('facts', []):
        value = fact['value']
        if fact['kind'] == 'domain_constant':
            rows.append({'kind': 'rule constant', 'id': value['name'],
                         'text': f"{value['name']} defined in " + ', '.join(f"{d['path']}:{d['line']}" for d in value['definitions']),
                         'detail': 'duplicated' if value['duplicated'] else 'single definition',
                         'citation': f"{fact['location']['path']}:{fact['location']['start_line']}"})
        else:
            rows.append({'kind': fact['kind'], 'id': value['name'], 'text': value['name'], 'detail': value.get('kind', ''),
                         'citation': f"{fact['location']['path']}:{fact['location']['start_line']}"})
    for fact in sets.get('syntax', {}).get('facts', []):
        if fact['kind'] != 'symbol': continue
        rows.append({'kind': 'symbol', 'id': fact['location'].get('symbol') or fact['value']['name'],
                     'text': f"{fact['location'].get('symbol')} ({fact['value']['kind']})",
                     'detail': fact['value']['language'] or '',
                     'citation': f"{fact['location']['path']}:{fact['location']['start_line']}-{fact['location']['end_line']}"})
    for fact in sets.get('config', {}).get('facts', []):
        if fact['kind'] != 'env_read': continue
        rows.append({'kind': 'configuration', 'id': fact['value']['name'], 'text': fact['value']['name'] + ' is read here',
                     'detail': 'has default' if fact['value']['has_default'] else 'no default',
                     'citation': f"{fact['location']['path']}:{fact['location']['start_line']}"})
    return rows


def answer(out, question, limit=8):
    dossier, sets = records(out)
    wanted = terms(question)
    if not wanted:
        return {'question': question, 'answers': [], 'status': 'NO_QUERY',
                'note': 'The question contains no searchable term.'}
    scored = []
    for row in candidates(dossier, sets):
        value = score(row['text'] + ' ' + row['id'] + ' ' + row['citation'], wanted)
        if value: scored.append((value, row))
    scored.sort(key=lambda pair: (-pair[0], pair[1]['kind'], pair[1]['id']))
    answers = [dict(row, score=value) for value, row in scored[:limit]]
    return {'question': question, 'terms': wanted, 'answers': answers,
            'status': 'ANSWERED' if answers else 'NOT_IN_RECORDS',
            'note': ('Answers come only from recorded facts and claims; each carries its own location.'
                     if answers else
                     'No record answers this question. Extend coverage (eaos facts/verify) or run a semantic audit before concluding anything.'),
            'unexamined': dossier.get('coverage', {}).get('not_examined', [])}
