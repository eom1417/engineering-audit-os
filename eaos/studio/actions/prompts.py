"""The words a run sends the assistant: what the person would have typed in chat, tied to the EAOS way and its gates.

A Fix run is the EAOS fix prompt limited to the selected cards; Verify, Explain and Plan only read. Every prompt says
the same three things: change code only through the EAOS tools, never take the person's decisions (accept, undo,
the branch, the run consent), and ask the person with one `eaos-question` block, which the Studio shows in its inbox.
"""
import json
import re

LANGS = {'ar': 'Arabic (plain, Gulf-friendly)', 'en': 'English'}
QUESTION = re.compile(r'```eaos-question\s*\n(.*?)\n\s*```', re.S)

ASK = ('When you need the person (their agreement to run the app, a choice only they can make), end your turn with exactly '
       'one block, and stop; you will be resumed with their answer:\n'
       '```eaos-question\n'
       '{"text": {"en": "<the question>", "ar": "<the question in Arabic>"}, "options": [{"id": "<short id>", "label": '
       '{"en": "<label>", "ar": "<label in Arabic>"}}], "recommendation": "<option id>"}\n'
       '```\n'
       'Never answer for the person. Do not call accept, undo or choose_branch: the person decides those in the Studio.')

VERBS = {
    'fix': ('Use the eaos tools to fix these cards of this project safely, end to end, without coming back between steps. '
            'Follow `status`: audit if it says so, then run_setup, run_try until the app runs, safety_net, then fix_start with '
            'exactly these cards, and for each card: finding and fix_read, then fix_edit (fix_skip only with a real reason). '
            'Then fix_finish. Change code only with fix_edit: never write a file yourself. Add the why with `note` after each '
            'card. At the end, tell the person in plain words what was fixed and on which branch; they accept or undo it in '
            'the Studio.'),
    'verify': ('Use the eaos tools to verify these cards: read each with `finding`, look at the code it points at (Read, '
               'Grep), and decide whether the problem is still there, already gone, or a false alarm, with the evidence. '
               'Record each verdict with `note` (card set). Change nothing.'),
    'explain': ('Use the eaos tools to explain these cards to the person: for each, with `finding` and `impact`, say what is '
                'wrong, why it matters to them, and what fixing it would change, in plain words with no jargon. Change nothing.'),
    'plan': ('Use the eaos tools to plan these cards: read them (`finding`, `impact`, `plan`, `structure`), then propose an '
             'order of batches, what waits for what, and the risk of each batch, in plain words. Record the plan with `note`. '
             'Change nothing.'),
}


def build(verb, cards, project, lang='ar', action=None, inputs=None, labels=None):
    """The prompt of a run: a verb over cards, or one assistant action with its inputs."""
    language = LANGS.get(lang, LANGS['en'])
    if verb:
        listed = '\n'.join(f"- {card['id']}: {card.get('title') or ''} ({', '.join(card.get('paths') or [])})".rstrip(' ()') for card in cards)
        task = f"{VERBS[verb]}\n\nThe cards ({len(cards)}):\n{listed}\nCard ids for the tools: {json.dumps([c['id'] for c in cards])}"
    else:
        label = (labels or {}).get(action, {}).get('en', action)
        shown = {k: v for k, v in (inputs or {}).items() if k != 'project'}
        task = (f'Use the eaos tools for this one step of the EAOS way: {label} (the `{action}` tool)'
                + (f', with these inputs from the person: {json.dumps(shown, ensure_ascii=False)}' if shown else '')
                + '. Call `status` first; do what the step needs and no more.')
    return (f'{task}\n\nThe project is the current folder ({project.name}). This request comes from the EAOS Studio, where the '
            f'person follows every step. {ASK}\nSpeak to the person in {language}.')


def answer(question, option, text, lang='ar'):
    """The words that resume a session with the person's answer."""
    chosen = next((o for o in question.get('options') or [] if o.get('id') == option), None)
    said = (chosen or {}).get('label', {}).get(lang) or (chosen or {}).get('label', {}).get('en') or option or ''
    parts = [f'The person answered in the Studio: {said}' + (f' (option "{option}")' if option else '')]
    if text: parts.append(f'They added: {text}')
    parts.append('Go on from where you stopped.')
    return ' '.join(parts)


def question_in(text):
    """The question block at the end of the assistant's words, normalised; None when there is none."""
    found = QUESTION.findall(text or '')
    if not found: return None
    try: data = json.loads(found[-1])
    except ValueError: return None
    if not isinstance(data, dict): return None
    words = data.get('text')
    if isinstance(words, str): words = {'en': words, 'ar': words}
    if not isinstance(words, dict) or not (words.get('en') or words.get('ar')): return None
    words = {'en': words.get('en') or words.get('ar'), 'ar': words.get('ar') or words.get('en')}
    options = []
    for index, option in enumerate(data.get('options') or []):
        if isinstance(option, str): option = {'id': f'o{index + 1}', 'label': {'en': option, 'ar': option}}
        if not isinstance(option, dict): continue
        label = option.get('label') or option.get('id')
        if isinstance(label, str): label = {'en': label, 'ar': label}
        options.append({'id': str(option.get('id') or f'o{index + 1}'), 'label': {'en': label.get('en') or label.get('ar'), 'ar': label.get('ar') or label.get('en')}})
    recommendation = data.get('recommendation')
    if recommendation not in {o['id'] for o in options}: recommendation = None
    return {'text': words, 'options': options, 'recommendation': recommendation}


def consent_question(payload):
    """run_setup's own question, when the assistant ended its turn on it without asking with a block."""
    ask = payload.get('ask_the_person') or payload.get('question') or ''
    if isinstance(ask, dict): words = {'en': ask.get('en') or ask.get('ar'), 'ar': ask.get('ar') or ask.get('en')}
    else: words = {'en': str(ask), 'ar': str(ask)}
    if not words['en']:
        words = {'en': 'May EAOS run your app in an isolated copy to prepare and check the fixes?',
                 'ar': 'تسمح لـ EAOS يشغّل تطبيقك في نسخة معزولة عشان يجهّز الإصلاحات ويفحصها؟'}
    return {'text': words, 'options': [{'id': 'yes', 'label': {'en': 'Yes, go ahead', 'ar': 'نعم، موافق'}},
                                       {'id': 'no', 'label': {'en': 'No', 'ar': 'لا'}}],
            'recommendation': 'yes', 'why': 'run consent'}


def branch_question(payload):
    """The check's own question when the project has several live branches (agent_tools._branch): which one EAOS
    checks and fixes. The options are the branches; the recommendation is the one EAOS would pick."""
    rows = [row for row in payload.get('branches') or [] if row.get('name')]
    options = []
    for row in rows:
        ahead = row.get('ahead_of_main')
        extra_en = ' (main)' if row.get('main') else f' ({ahead} ahead of main)' if ahead else ''
        extra_ar = ' (الرئيسي)' if row.get('main') else f' (متقدم {ahead} عن الرئيسي)' if ahead else ''
        options.append({'id': row['name'], 'label': {'en': row['name'] + extra_en, 'ar': row['name'] + extra_ar}})
    recommended = payload.get('recommended')
    recommended = recommended.get('name') if isinstance(recommended, dict) else recommended
    return {'text': {'en': 'Which branch should EAOS check and fix? The check, the fixes, the progress and every merge will follow '
                           'that branch. Your checkout is not switched.',
                     'ar': 'أي فرع يفحصه EAOS ويصلحه؟ الفحص والإصلاحات والتقدم وكل دمج تتبع هذا الفرع. نسختك الحالية لا تتغير.'},
            'options': options, 'recommendation': recommended if recommended in {o['id'] for o in options} else None, 'why': 'branch'}
