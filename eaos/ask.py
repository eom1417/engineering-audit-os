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
from .facts.run import ALL_SETS as SETS


def terms(question):
    words = [w.lower() for w in re.findall(r'[\w./-]{2,}', question)]
    return [w for w in words if w not in STOP]


KIND_WEIGHT = {'claim': 4, 'open question': 3, 'flow': 3, 'entry point': 3, 'rule constant': 3,
               'configuration': 2, 'data_model': 2, 'data_table': 2, 'artifact section': 2, 'symbol': 1}


def score(row, wanted):
    """Structure first: an exact identifier or route match outranks a loose word overlap."""
    text = (row['text'] + ' ' + row['id'] + ' ' + row['citation']).lower()
    tokens = set(re.findall(r'[\w./-]+', text))
    total = 0
    for word in wanted:
        if word in tokens: total += 4
        elif word in text: total += 1
    if row['kind'] in {'entry point', 'flow'} and any(word in (row.get('route') or '').lower() for word in wanted):
        total += 6
    return total


def artifact_sections(out):
    """The rendered artifacts are part of the record, and they are the only Arabic surface we have."""
    rows = []
    for path in sorted(Path(out).glob('*.md')):
        heading = path.stem
        for number, line in enumerate(path.read_text(encoding='utf-8').split('\n'), start=1):
            if line.startswith('#'): heading = line.lstrip('#').strip()
            elif line.strip().startswith('|') and len(line) > 12:
                cells = [cell.strip() for cell in line.strip().strip('|').split('|')]
                if all(set(cell) <= {'-', ':'} for cell in cells if cell): continue  # table rule, not content
                rows.append({'kind': 'artifact section', 'id': heading[:40], 'text': ' · '.join(cells)[:200],
                             'detail': path.name, 'citation': f'{path.name}:{number}'})
    return rows


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
                     'route': str(value['route'] or ''),
                     'citation': f"{fact['location']['path']}:{fact['location'].get('start_line') or 1}"})
    for fact in sets.get('flows', {}).get('facts', []):
        value = fact['value']
        rows.append({'kind': 'flow', 'id': value['flow_id'],
                     'text': f"{value['entry']['surface']} {value['entry']['route']} touches " + ', '.join(value['touched_files']),
                     'detail': f"{len(value['steps'])} steps", 'route': str(value['entry']['route'] or ''),
                     'citation': f"{value['entry']['path']}:{value['entry']['line']}"})
    for fact in sets.get('domain', {}).get('facts', []):
        value = fact['value']
        if fact['kind'] == 'domain_constant':
            rows.append({'kind': 'rule constant', 'id': value['name'],
                         'text': f"{value['name']} defined in " + ', '.join(f"{d['path']}:{d['line']}" for d in value['definitions']),
                         'detail': 'duplicated' if value['duplicated'] else 'single definition',
                         'citation': f"{fact['location']['path']}:{fact['location']['start_line']}"})
        else:
            # Domain facts are not all named the same way: a cross-module write has a module and an attribute.
            name = value.get('name') or f"{value.get('module', '')}.{value.get('attribute', '')}".strip('.')
            if not name: continue
            rows.append({'kind': fact['kind'], 'id': name, 'text': name, 'detail': str(value.get('kind') or value.get('shape') or ''),
                         'citation': f"{fact['location']['path']}:{fact['location'].get('start_line') or 1}"})
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


def follow_ups(answers):
    """Where a reader usually needs to go next, phrased as a command they can run."""
    if not answers: return []
    top = answers[0]
    path = top['citation'].split(':')[0]
    suggestions = []
    if top['kind'] in {'entry point', 'flow'}:
        suggestions.append(f'eaos impact-of {path} --out <dir>  — what a change to this entry point would reach')
        suggestions.append('FLOWS.md — the traced steps of this entry point')
    elif top['kind'] == 'rule constant':
        suggestions.append('DOMAIN-AND-DATA.md — every definition site of this rule')
        suggestions.append(f'eaos impact-of {path} --out <dir>')
    elif top['kind'] == 'claim':
        suggestions.append('RISK-REGISTER.md — where this claim sits against the others')
        suggestions.append('PLAN/ — the task card generated for it, if any')
    else:
        suggestions.append(f'eaos impact-of {path} --out <dir>  — who depends on this')
    return suggestions


def answer(out, question, limit=8):
    dossier, sets = records(out)
    wanted = terms(question)
    if not wanted:
        return {'question': question, 'answers': [], 'status': 'NO_QUERY',
                'note': 'The question contains no searchable term.'}
    scored = []
    for row in candidates(dossier, sets) + artifact_sections(out):
        value = score(row, wanted)
        if value: scored.append((value * KIND_WEIGHT.get(row['kind'], 1), row))
    scored.sort(key=lambda pair: (-pair[0], pair[1]['kind'], pair[1]['id']))
    answers = [dict(row, score=value) for value, row in scored[:limit]]
    return {'question': question, 'terms': wanted, 'answers': answers,
            'next_questions': follow_ups(answers),
            'status': 'ANSWERED' if answers else 'NOT_IN_RECORDS',
            'note': ('Answers come only from recorded facts and claims; each carries its own location.'
                     if answers else
                     'No record answers this question. Records are written in the code\'s own language; try the identifier or path you are after, '
                     'or extend coverage with eaos facts/verify before concluding anything.'),
            'unexamined': dossier.get('coverage', {}).get('not_examined', [])}
