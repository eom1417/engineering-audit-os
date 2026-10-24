"""A project built from its plan, in the Studio (docs/BUILD-FROM-PLAN.md): its milestones and build cards as the plan of
kind `build`, the spec's open questions in the inbox (answered by build_tools.answered), and the build's own
verdict and next step on the Status page, from what build_tools.studio_build read of the blueprint folder."""
from .. import blueprint


def _in(lang, ar, en):
    return ar if lang == 'ar' else en


def _card_states(build):
    """{card: done | blocked | active}: kept or set aside (blocked) by a delivered milestone or the open one, or being built."""
    states = {}
    opened = build['open'] or {}
    for record in list(build['built']) + ([opened] if opened else []):
        states.update({card: 'blocked' for card in record.get('skipped') or []})
        states.update({card: 'done' for card in record.get('kept') or []})
    for card in opened.get('cards') or []: states.setdefault(card, 'active')
    return states


def _step(milestone, by_id, states, branches, lang):
    tasks = [_task(by_id[c], states.get(c, 'todo')) for c in milestone['tasks'] if c in by_id]
    seen = {t['state'] for t in tasks}
    state = 'done' if seen <= {'done', 'blocked'} else 'active' if seen & {'active', 'done', 'blocked'} else 'todo'
    return {'id': milestone['id'], 'title': milestone.get(_in(lang, 'name_ar', 'name')) or milestone['name'], 'state': state,
            'weight': len(tasks), 'gate': milestone.get('exit'), 'branch': branches.get(milestone['id']), 'tasks': tasks}


def _task(card, state):
    """One build card as a plan step's task: its title, state, acceptance (a line each), paths, tests and dependencies."""
    return {'id': card['id'], 'title': card['title'], 'state': state, 'acceptance': '\n'.join(map(str, card.get('acceptance') or [])),
            'paths': card.get('paths') or [], 'tests': card.get('tests') or [], 'depends_on': card.get('depends_on') or []}


def plan(build, lang):
    """The plan of kind `build` (plans.json): one step per milestone, its cards with their acceptance and state."""
    if not build or not build['plan']: return None
    by_id = {c['id']: c for c in build['plan']['tasks']}
    states, branches = _card_states(build), {r['milestone']: r.get('branch') for r in build['built']}
    steps = [_step(m, by_id, states, branches, lang) for m in build['plan']['milestones']]
    done = sum(states.get(c) == 'done' for c in by_id)
    state, waiting = _plan_state(build, steps)
    return {'id': 'build', 'title': _in(lang, 'خطة البناء', 'Build plan'), 'kind': 'build', 'parent': None, 'state': state,
            'goal': build['spec'].get('summary') or '', 'indicators': [], 'steps': steps,
            'open': (build['open'] or {}).get('milestone'), 'next': waiting, 'requirements': len(build['spec'].get('requirements') or []),
            'progress': {'value': round(done / max(len(by_id), 1), 4), 'src': 'blueprint: cards kept / every build card'}}


def _plan_state(build, steps):
    """(the plan's state, the first milestone not done): closed when none is left, active once one is built or open."""
    waiting = next((s['id'] for s in steps if s['state'] != 'done'), None)
    return 'closed' if waiting is None else 'active' if build['built'] or build['open'] else 'registered', waiting


def _options(question, lang):
    if question['kind'] == 'yes_no':
        return [{'id': 'yes', 'label': _in(lang, 'نعم', 'Yes')}, {'id': 'no', 'label': _in(lang, 'لا', 'No')}]
    if question['id'].startswith('stack-'):
        catalogue = blueprint.stacks()['concerns'][question['id'][len('stack-'):]]['options']
        return [{'id': key, 'label': catalogue[key]['name']} for key in question['options']]
    return [{'id': f'o{i + 1}', 'label': str(text)} for i, text in enumerate(question['options'])]


CONCERNS_AR = {'web': 'واجهة الموقع', 'api': 'الخادم', 'database': 'مكان حفظ البيانات', 'auth': 'تسجيل الدخول',
               'styling': 'التنسيق', 'testing': 'الاختبارات'}


def _words(question, spec, lang):
    """(question, why) in the page's language: EAOS's own questions are written in both, the spec's in the words the
    assistant wrote them."""
    if question['id'] == 'flows':
        return _in(lang, 'الخطة ما تذكر رحلة مستخدم كاملة من البداية للنهاية. نكتب الرحلات الرئيسية من الميزات؟', question['text']), None
    if question['id'].startswith('stack-'):
        concern = question['id'][len('stack-'):]
        wanted = (spec.get('stack_preferences') or {}).get(concern)
        return _in(lang, f'{CONCERNS_AR.get(concern, concern)}: خطتك تطلب «{wanted}»، وEAOS ما يجهّزها للحين. أي خيار نستخدم؟',
                   question['text']), _in(lang, None, question.get('why'))
    return question['text'], question.get('why')


def questions(build, lang):
    """The spec's open questions (blueprint._spec_questions) as inbox rows, asked from the blueprint."""
    rows = []
    for question in blueprint.validate_spec(build['spec'])[1] if build else []:
        options = _options(question, lang)
        recommended = next((o['id'] for o in options if question.get('recommendation') in (o['id'], o['label'])), None)
        text, why = _words(question, build['spec'], lang)
        label = next((o['label'] for o in options if o['id'] == recommended), '')
        rows.append({'id': f"blueprint:{question['id']}", 'question': text, 'options': options, 'recommended_option': recommended,
                     'recommendation': ' '.join(filter(None, [label and f'{label}.', why])),
                     'blocks': [], 'state': 'waiting', 'answer': None, 'plan': 'build', 'asked': '', 'tool': 'blueprint'})
    return rows


def verdict(build, lang):
    """The Status page's first sentence for a project still being built from its plan."""
    built = plan(build, lang)
    if not built: return _in(lang, 'مشروع جديد من خطة: المخطط ما انرسم بعد.', 'A new project from a plan: its blueprint is not drawn yet.')
    cards = sum(s['weight'] for s in built['steps'])
    done = sum(t['state'] == 'done' for s in built['steps'] for t in s['tasks'])
    return _in(lang, f"مشروع جديد من خطة: عدد المراحل {len(built['steps'])}، وعدد بطاقات البناء {cards}، وخلص منها {done}.",
               f"A new project from a plan: {len(built['steps'])} milestones and {cards} build cards, {done} built.")


def next_step(build, lang):
    """{action, tool}: the build's next step, as the report's head names it."""
    asked, built = questions(build, lang), plan(build, lang)
    if asked: return {'action': _in(lang, f'جاوب على أسئلة المخطط ({len(asked)})', f'Answer the blueprint questions ({len(asked)})'), 'tool': 'blueprint_answer'}
    if not built: return {'action': _in(lang, 'كمّل رسم المخطط', 'Finish drawing the blueprint'), 'tool': 'blueprint_start'}
    if built['open'] or built['next']:
        milestone = built['open'] or built['next']
        words = _in(lang, 'ابنِ المنتج كامل', 'Build the whole product') if milestone == built['steps'][0]['id'] else \
            _in(lang, f'كمّل بناء المنتج من المرحلة {milestone}', f'Go on building the product from milestone {milestone}')
        return {'action': words, 'tool': 'build_start', 'milestone': milestone}
    return {'action': _in(lang, 'كل المراحل انبنت: قرّر تدمج الفرع الأخير', 'Every milestone is built: decide on the last branch'), 'tool': 'accept'}

