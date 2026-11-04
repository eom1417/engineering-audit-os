"""An executable repair for a dependency version with a known, fixed vulnerability.

OSV-Scanner's lookup is deterministic: this locked version is listed as affected, and the advisory names
the version that fixes it. When the engagement rule `upgrade_vulnerable_dependencies` holds (a declared
default the project can turn off in eaos.engagement.json), the claim carries the assessment a ready card
needs; when no tool of EAOS rewrites the lock file (MANAGERS of eaos/analysis/repair/codemods.py), the
assessment carries blockers instead, naming the command the person runs. Its reviewer of record is that
rule, never an invented person. Its check re-runs Syft and OSV-Scanner on the changed copy and passes only
when none of the original advisories remain for the package.
"""
from ..repair.acceptance import fingerprint, recheck
from ..repair.codemods import manual_upgrade
from ..understanding.engagement import rules_for
from ..repair.remediation import PATTERNS, cited


def _check_argv(wanted):
    """Re-scan into a private directory; exit 0 only when no package carries its advisories. `wanted`:
    {'<ecosystem>:<name>@': [advisory ids]}, one package, or every package of a lock file card."""
    return recheck('eaos-deps-', "data = json.load(open(tmp + '/facts/external.json'))\n"
                   "if 'osv-scanner' not in (data.get('summary') or {}).get('engines_observed', []): sys.exit(2)\n"
                   f"wanted = {dict((prefix, sorted(ids)) for prefix, ids in wanted.items())!r}\n"
                   "left = [f for f in data['facts'] if f['kind'] == 'engine_finding' and f['value'].get('kind') == 'vulnerability'\n"
                   "        and any(str(f['location'].get('symbol', '')).startswith(prefix) and set(ids) & set(next((m['value']\n"
                   "                for m in f['value']['measurements'] if m['name'] == 'advisory_ids'), [])) for prefix, ids in wanted.items())]\n"
                   "sys.exit(1 if left else 0)\n", engines=('syft', 'osv-scanner'))


def check_of(facts):
    """The check of a card upgrading the packages of `facts`: none of their advisories is left (a lock file card kept in
    part is held to the packages it moved, eaos/journeys/agent_tools/fixing.py)."""
    return _check_argv({f'{ecosystem}:{name}@': ids for ecosystem, name, _, _, ids in map(_upgrade, facts)})


# Why a batch cannot make the change itself, for the assistant (en) and the person (ar), with the command they run.
UNABLE = {'lock': ('no lock file names it, only the inventory found it; upgrade what brings it in',
                   'ما فيه ملف قفل يذكرها، لقاها جرد المكونات بس، فرقِّ الحزمة اللي تجيبها'),
          'tool': ('EAOS has no tool that rewrites {lock}; run `{command}` and commit {lock}',
                   'ما عنده أداة تعيد كتابة {lock}، فشغّل بنفسك `{command}` واعتمد {lock}'),
          'missing': ('{tool} is not installed here; run `{command}` and commit {lock}',
                      'أداة {tool} مو موجودة على هذا الجهاز، فشغّل بنفسك `{command}` واعتمد {lock}')}


def _unable(fact, upgrades):
    """(blockers, the words added to the change) when a batch cannot upgrade this lock file itself, else ([], '')."""
    # an Action is moved in the workflows that use it (eaos/analysis/repair/actions_upgrade.py), never through a lock file
    manuals = [None if ecosystem == 'GitHub Actions' else manual_upgrade(fact['location'].get('path') or '', name, fixed)
               for ecosystem, name, _, fixed, _ in upgrades]
    if manuals[0] is None: return [], ''
    manual = {**manuals[0], 'command': ' && '.join(m['command'] for m in manuals if m['command'])}
    en, ar = (text.format(**manual) for text in UNABLE[manual['why']])
    return ['EAOS cannot make this upgrade itself: ' + en + '.'], ' EAOS ما يقدر يسويها بنفسه: ' + ar + '.'


# The change of a lock file card: every package it gathers, each to its own fixed version.
GROUP_CHANGE = ('رقِّ في ملف القفل هذي الحزم اللي ما يذكرها المشروع بنفسه، كل وحدة لإصدارها المصلَّح أو أحدث، بأداة الحزم نفسها، '
                'ثم شغّل الاختبارات: {packages}.')


def _upgrade(fact):
    """(ecosystem, name, installed, fixed, advisories) of one vulnerable locked version."""
    ecosystem, _, rest = str(fact['location'].get('symbol')).partition(':')
    name, _, installed = rest.rpartition('@')
    return ecosystem, name, installed, measured(fact, 'fixed_in'), measured(fact, 'advisory_ids') or []


def _words(upgrades):
    """(expected, after, proposed change) of one package's card, or of a lock file card's packages."""
    names = ', '.join(name for _, name, _, _, _ in upgrades)
    advisories = sorted({advisory for upgrade in upgrades for advisory in upgrade[4]})
    expected = f'the next scan reports none of {", ".join(advisories)} for {names}'
    if len(upgrades) > 1:
        return (expected, f'{names} are at their fixed versions or later, and the scan reports none of their advisories.',
                GROUP_CHANGE.format(packages='، '.join(f'{name} من {installed} إلى {fixed}' for _, name, installed, fixed, _ in upgrades)))
    _, name, installed, fixed, _ = upgrades[0]
    return (expected, f'{name} is at {fixed} or later in every lockfile, and the scan reports none of its advisories.',
            PATTERNS['upgrade_dependency']['change'].format(name=name, installed=installed, fixed=fixed))


def measured(fact, name):
    return next((m['value'] for m in (fact.get('value') or {}).get('measurements') or [] if m['name'] == name), None)


def _upgradable(claim, fact_sets, target):
    """(the upgrade rule, the facts the claim cites) when the rule holds and every fact has a fix, else (None, [])."""
    if target is None or (claim.get('render') or {}).get('key') not in ('vulnerable_dependency', 'vulnerable_lockfile'):
        return None, []
    rule = rules_for(target)[0]['upgrade_vulnerable_dependencies']
    facts = list(cited(claim, fact_sets, 'external')) if rule['value'] else []
    return rule, facts if facts and all(measured(fact, 'fixed_in') for fact in facts) else []


def build_assessment(claim, fact_sets, target):
    """{'assessment': ..., 'checks': [...]} for a fixable vulnerable dependency, or a lock file's, under the upgrade
    rule, else None. A lock file card is fixable only when every package it gathers has a fix."""
    rule, facts = _upgradable(claim, fact_sets, target)
    if not facts: return None
    upgrades = [_upgrade(fact) for fact in facts]
    (expected, after, change), (blockers, manual) = _words(upgrades), _unable(facts[0], upgrades)
    check = {'id': 'DEP-' + facts[0]['id'], 'kind': 'command',
             'invariant': 'No locked dependency is a version with a published, fixed vulnerability.',
             'expected': expected, 'expected_exit': 0, 'cwd': '.', 'source_revision': fingerprint(target),
             'argv': check_of(facts)}
    return {'assessment': {
                'violated_invariant': check['invariant'],
                'requirement_refs': ['engagement.rules.upgrade_vulnerable_dependencies'],
                'evidence_refs': [fact['id'] for fact in facts],
                'reviewed_by': (f"engagement rule upgrade_vulnerable_dependencies ({rule['source']}): {rule['why']} "
                                'The evidence is a database lookup of the locked version; no human judgement is claimed.'),
                'before': '; '.join(fact['value']['message'] for fact in facts), 'after': after,
                'proposed_change': change + manual, **({'blockers': blockers} if blockers else {})},
            'checks': [check]}
