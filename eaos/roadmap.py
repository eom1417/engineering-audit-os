"""The plan a team executes: every card sized, owned by a section, and placed in exactly one milestone.

Size (effort), from what the card touches:
    S   two files or fewer, and at most 5 dependents in its blast radius
    M   eight files or fewer, or at most 20 dependents
    L   anything larger
effort_basis keeps both numbers.

Section, the first rule that holds, in this order:
    security        an access gap, a committed credential, a vulnerable dependency, a secret
    infrastructure  a file under .github/, a Dockerfile, vercel.json, netlify.toml
    data            a .sql file, or anything under supabase/
    backend         a path under server/, api/ or functions/
    quality         a trace gap or an untested path
    frontend        everything else

Milestones, in the order of docs/MASTER-BLUEPRINT.md §7, an empty one never written:
    stabilize      vulnerable versions, broken code, dead code and leftovers, access gaps
    safety net     untested paths and flows that cannot be traced
    boundaries     cycles, hidden coupling, policy breaches, one definition per rule, shared state
    build          one milestone per target component (NS7), the highest total priority first; a component
                   whose disposition is rebuild is done Strangler Fig: the new path behind a flag, the old
                   one removed only after behaviour parity (E7)
    hardening      load blockers and redundant work
Fewer than ten milestones: builds past the third share one milestone.
"""
from collections import defaultdict

SECURITY = {'access_gap', 'upgrade_dependency', 'secret'}
STABILIZE = {'upgrade_dependency', 'broken_code', 'remove_dead', 'dead_code', 'leftover', 'access_gap', 'secret'}
SAFETY_NET = {'untested_path', 'trace_gap'}
BOUNDARIES = {'import_cycle', 'hidden_coupling', 'policy_violation', 'canonicalize', 'duplicated_rule',
              'external_write', 'mutable_state'}
HARDENING = {'load_blocker', 'redundant_work'}
BUILDS_SHOWN = 3
GOALS_AR = {
    'stabilize': ('لا يبقى إصدار معروف الثغرات، ولا مرجع معطّل، ولا كود ميت، ولا فجوة وصول مفتوحة.',
                  'كل بطاقة هنا يمر أمر قبولها، ولا يثير التدقيق التالي أيًا من هذه الادعاءات.'),
    'safety_net': ('كل مسار يصل إليه المستخدم قابل للتتبع ويمرّ عليه اختبار.',
                   'كل بطاقة هنا تمر، وتثبيت السلوك (E4) أخضر على الفرع الرئيسي.'),
    'boundaries': ('الطبقات تتبع النوع المرجعي: لا دورة، ولا استيراد ممنوع، وتعريف واحد لكل قاعدة.',
                   'كل بطاقة هنا تمر، ولا يجد التدقيق التالي دورة ولا قاعدة مكررة مما يسرده.'),
    'hardening': ('كل نقطة دخول تحدّ ما تقرؤه، وتحمي نداءاتها الخارجية، ولا تكرر عملًا.',
                  'كل بطاقة هنا تمر، ولا يبقى معيق حمل في load-model.json.'),
}
GOALS = {
    'stabilize': ('No known-vulnerable version, broken reference, dead code or open access gap remains.',
                  'Every card here passes its acceptance command, and the next audit raises none of these claims.'),
    'safety_net': ('Every user-facing flow can be traced and is exercised by a test.',
                   'Every card here passes; the behaviour lock (E4) runs green on the default branch.'),
    'boundaries': ('The layers follow the reference type: no cycle, no forbidden import, one definition per rule.',
                   'Every card here passes; the next audit finds no import cycle and no duplicated rule it lists.'),
    'hardening': ('Every entry point bounds its reads, protects its outbound calls and repeats no work.',
                  'Every card here passes; no load blocker remains in load-model.json.'),
}


def effort(paths, dependents):
    files = len(set(paths or []))
    size = 'S' if files <= 2 and dependents <= 5 else 'M' if files <= 8 or dependents <= 20 else 'L'
    return size, {'files': files, 'dependents': dependents}


def section(task):
    paths = task.get('paths') or []
    text = str(task.get('render') or '') + ' ' + str(task.get('title') or '')
    if task.get('pattern') in SECURITY or 'committed_credential' in text or ' secret ' in f' {text} ': return 'security'
    if any(p.startswith('.github/') or p.endswith(('Dockerfile', 'vercel.json', 'netlify.toml')) for p in paths): return 'infrastructure'
    if any(p.endswith('.sql') or p.startswith('supabase/') for p in paths): return 'data'
    if any(part in ('server', 'api', 'functions') for p in paths for part in p.split('/')[:-1]): return 'backend'
    if task.get('pattern') in SAFETY_NET: return 'quality'
    return 'frontend'


def milestone_of(task, placements):
    pattern = task.get('pattern')
    if pattern in STABILIZE: return 'stabilize'
    if pattern in SAFETY_NET: return 'safety_net'
    if pattern in BOUNDARIES: return 'boundaries'
    if pattern in HARDENING: return 'hardening'
    component = next((placements[p] for p in task.get('paths') or [] if p in placements), None)
    return f"build:{component or 'unplaced'}"


def milestones(tasks, placements=None, dispositions=None):
    """[{id, goal, exit, tasks, strangler}] in the fixed order; each card in exactly one milestone."""
    placements, dispositions = placements or {}, dispositions or {}
    groups = defaultdict(list)
    for task in tasks: groups[milestone_of(task, placements)].append(task)
    builds = sorted((name for name in groups if name.startswith('build:')),
                    key=lambda name: (-sum(t.get('priority') or 0 for t in groups[name]), name))
    kept, rest = builds[:BUILDS_SHOWN], builds[BUILDS_SHOWN:]
    if rest:
        groups['build:other'] = [task for name in rest for task in groups.pop(name)]
        kept.append('build:other')
    order = ['stabilize', 'safety_net', 'boundaries', *kept, 'hardening']
    out = []
    for name in order:
        members = sorted(groups.get(name) or [], key=lambda t: (-(t.get('priority') or 0), t['id']))
        if not members: continue
        if name.startswith('build:'):
            component = name.split(':', 1)[1]
            rebuild = dispositions.get(component) == 'rebuild'
            goal = (f"`{component}` is rebuilt in its target layer, behind a flag (Strangler Fig), with the same behaviour."
                    if rebuild else f"`{component}` is reshaped to its target: its cards done, its files in place.")
            exit_ = ('Every card here passes; the behaviour lock matches on the new path; the old path is removed '
                     'in its own step only after parity (E7).' if rebuild else
                     'Every card here passes, and the next audit places every file of the component in its target layer.')
        else:
            goal, exit_ = GOALS[name]
            rebuild = False
        if name.startswith('build:'):
            goal_ar = (f"إعادة بناء `{component}` في طبقته المستهدفة خلف علم (Strangler Fig)، بالسلوك نفسه." if rebuild
                       else f"تشكيل `{component}` على صورته المستهدفة: بطاقاته منجزة وملفاته في أماكنها.")
            exit_ar = ('كل بطاقة هنا تمر، وتثبيت السلوك يطابق على المسار الجديد، والمسار القديم يُزال في خطوة مستقلة بعد التكافؤ (E7).'
                       if rebuild else 'كل بطاقة هنا تمر، ويضع التدقيق التالي كل ملف من المكوّن في طبقته المستهدفة.')
        else:
            goal_ar, exit_ar = GOALS_AR[name]
        out.append({'id': f'M{len(out) + 1:02d}', 'name': name, 'goal': goal, 'exit': exit_, 'goal_ar': goal_ar, 'exit_ar': exit_ar,
                    'tasks': [t['id'] for t in members], 'strangler': rebuild})
    return out


def sections(tasks):
    """[{section, tasks in order, depends_on}]: a section waits for the sections its cards' prerequisites are in."""
    by_id = {t['id']: t for t in tasks}
    grouped, needs = defaultdict(list), defaultdict(set)
    for task in sorted(tasks, key=lambda t: (-(t.get('priority') or 0), t['id'])):
        grouped[task['section']].append(task['id'])
        for ref in task.get('prerequisites') or []:
            other = by_id.get(ref.get('task_id'))
            if other and other['section'] != task['section']: needs[task['section']].add(other['section'])
    order = ['security', 'infrastructure', 'data', 'backend', 'frontend', 'quality']
    return [{'section': name, 'tasks': grouped[name], 'depends_on': sorted(needs[name])} for name in order if grouped[name]]


def clip(text, n):
    text = ' '.join(str(text).split())
    return text if len(text) <= n else text[:n - 1].rstrip() + '…'


def render(plan_milestones, tasks, language='ar', shown=5):
    from .compose import Document
    ar = language == 'ar'
    by_id = {t['id']: t for t in tasks}
    document = Document('خارطة التنفيذ' if ar else 'Roadmap', language, budget_lines=120)
    document.header([('المعالم بترتيب ثابت: التثبيت، ثم شبكة الأمان، ثم الحدود، ثم البناء، ثم التصليب. كل بطاقة في معلم واحد.'
                      if ar else 'Milestones in a fixed order: stabilize, safety net, boundaries, build, hardening. '
                                 'Every card is in exactly one.')])
    for milestone in plan_milestones:
        document.section(f"{milestone['id']} · {milestone['name']} ({len(milestone['tasks'])})")
        document.bullets([('الهدف: ' if ar else 'Goal: ') + milestone['goal_ar' if ar else 'goal'],
                          ('الخروج: ' if ar else 'Exit: ') + milestone['exit_ar' if ar else 'exit']]
                         + [f"{tid} [{by_id[tid].get('effort', '?')}/{by_id[tid].get('section', '?')}] {clip(by_id[tid].get('title', ''), 80)}"
                            for tid in milestone['tasks'][:shown]])
    return document
