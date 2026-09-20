"""What changed since the last dossier — the difference between a one-off report and a living record."""
from pathlib import Path
from .compose import Document
from .workspace import read, write

SEVERE = {'CONFIRMED', 'LIKELY'}


def key_of(claim): return (claim['claim_type'], ' '.join(claim['statement'].split()).lower())


def compare(previous, current):
    before = {key_of(claim): claim for claim in previous.get('claims', [])}
    after = {key_of(claim): claim for claim in current.get('claims', [])}
    appeared = [after[key] for key in sorted(set(after) - set(before), key=lambda k: (k[0], k[1]))]
    resolved = [before[key] for key in sorted(set(before) - set(after), key=lambda k: (k[0], k[1]))]
    changed = []
    for key in sorted(set(before) & set(after), key=lambda k: (k[0], k[1])):
        if before[key]['confidence'] != after[key]['confidence']:
            changed.append({'id': after[key]['id'], 'statement': after[key]['statement'],
                            'from': before[key]['confidence'], 'to': after[key]['confidence']})
    coverage_before, coverage_after = previous.get('coverage', {}), current.get('coverage', {})
    coverage_delta = {}
    for field in ['parse_coverage', 'imports_resolved', 'entry_points', 'runtime_confirmation', 'executed_coverage_percent']:
        if coverage_before.get(field) != coverage_after.get(field):
            coverage_delta[field] = {'from': coverage_before.get(field), 'to': coverage_after.get(field)}
    new_severe = [claim for claim in appeared if claim['confidence'] in SEVERE and claim['claim_type'] in {'risk', 'cause', 'business_rule', 'structure'}]
    # A difference can come from changed code or from a changed toolchain. Saying which is not optional.
    before_tools = previous.get('provenance', {})
    after_tools = current.get('provenance', {})
    toolchain = {}
    if before_tools.get('tool_version') != after_tools.get('tool_version'):
        toolchain['tool_version'] = {'from': before_tools.get('tool_version'), 'to': after_tools.get('tool_version')}
    for name, version in sorted((after_tools.get('extractors') or {}).items()):
        older = (before_tools.get('extractors') or {}).get(name)
        if older != version: toolchain[name] = {'from': older, 'to': version}
    return {'new_claims': appeared, 'resolved_claims': resolved, 'confidence_changes': changed,
            'coverage_changes': coverage_delta, 'new_severe_claims': new_severe, 'toolchain_changes': toolchain,
            'counts': {'new': len(appeared), 'resolved': len(resolved), 'changed': len(changed), 'new_severe': len(new_severe)}}


def document(result, previous, current, language):
    words = Document('', language).words
    heading = 'ما تغيّر منذ المراجعة السابقة' if language == 'ar' else 'What changed since the previous dossier'
    doc = Document(heading, language, budget_lines=160)
    doc.header([f"{previous['provenance']['generated_at']} → {current['provenance']['generated_at']}",
                f"new {result['counts']['new']} · resolved {result['counts']['resolved']} · "
                f"confidence changed {result['counts']['changed']} · new severe {result['counts']['new_severe']}",
                (('تنبيه: أدوات التحليل تغيّرت بين اللقطتين (' if language == 'ar' else
                  'Warning: the analysis toolchain changed between the snapshots (')
                 + ', '.join(sorted(result['toolchain_changes'])) +
                 ('), فبعض الفروق قد تعود إلى تحسّن الكشف لا إلى تغيّر الكود.' if language == 'ar' else
                  '), so part of this difference may be improved detection rather than changed code.'))
                if result['toolchain_changes'] else None])
    doc.section('ادعاءات جديدة' if language == 'ar' else 'New claims')
    doc.table(['#', 'الادعاء' if language == 'ar' else 'Claim', 'الثقة' if language == 'ar' else 'Confidence'],
              [[claim['id'], claim['statement'][:140], claim['confidence']] for claim in result['new_claims']], limit=20)
    doc.section('ادعاءات لم تعد قائمة' if language == 'ar' else 'Claims no longer present')
    doc.table(['#', 'الادعاء' if language == 'ar' else 'Claim'],
              [[claim['id'], claim['statement'][:140]] for claim in result['resolved_claims']], limit=20)
    doc.section('تغيّر الثقة' if language == 'ar' else 'Confidence changes')
    doc.table(['#', 'من' if language == 'ar' else 'From', 'إلى' if language == 'ar' else 'To', 'الادعاء' if language == 'ar' else 'Claim'],
              [[row['id'], row['from'], row['to'], row['statement'][:120]] for row in result['confidence_changes']], limit=20)
    doc.section(words['coverage'])
    doc.table([words['name'], 'من' if language == 'ar' else 'from', 'إلى' if language == 'ar' else 'to'],
              [[field, str(value['from']), str(value['to'])] for field, value in sorted(result['coverage_changes'].items())])
    return doc


def run(previous_out, current_out, language='ar', fail_on_new_severe=False):
    previous = read(Path(previous_out) / 'dossier.json')
    current = read(Path(current_out) / 'dossier.json')
    result = compare(previous, current)
    write(Path(current_out) / 'delta.json', result)
    (Path(current_out) / 'DELTA.md').write_text(document(result, previous, current, language).render(), encoding='utf-8')
    status = 'DRIFT' if (fail_on_new_severe and result['new_severe_claims']) else 'OK'
    return {'previous': str(previous_out), 'current': str(current_out), 'counts': result['counts'],
            'toolchain_changes': result['toolchain_changes'],
            'new_severe_claims': [claim['id'] for claim in result['new_severe_claims']], 'status': status,
            'limits': 'A delta compares two dossiers. A claim that disappears may have been fixed, or may simply no longer be detectable.'}
