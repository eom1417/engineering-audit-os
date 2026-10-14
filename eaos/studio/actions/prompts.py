"""The words a run sends the assistant: what the person would have typed in chat, tied to the EAOS way and its gates.

A Fix run is the EAOS fix prompt limited to the selected cards; Verify, Explain and Plan only read. Every prompt says
the same three things: change code only through the EAOS tools, never take the person's decisions (accept, undo,
the branch, the run consent), and ask the person with one `eaos-question` block, which the Studio shows in its inbox.
"""
import json
import re

from ...language import NAMES

QUESTION = re.compile(r'```eaos-question\s*\n(.*?)\n\s*```', re.S)

ASK = ('When you need the person (their agreement to run the app, a choice only they can make), end your turn with exactly '
       'one block, and stop; you will be resumed with their answer:\n'
       '```eaos-question\n'
       '{"text": {"en": "<the question>", "ar": "<the question in Arabic>"}, "options": [{"id": "<short id>", "label": '
       '{"en": "<label>", "ar": "<label in Arabic>"}}], "recommendation": "<option id>"}\n'
       '```\n'
       'When an option means closing the open batch of fixes (fix_abandon), give it "action": "fix_abandon": the Studio '
       'closes the batch itself when the person picks it, before you go on. '
       'Never answer for the person. Do not call accept, undo or choose_branch: the person decides those in the Studio. '
       'If a tool you need is refused or is not among your tools, never ask the person to change permissions, settings or '
       'files: that is never theirs to do. Say plainly which step of the Studio does it (for example "Run the app safely") '
       'and end your turn.')
ACTS = ('fix_abandon',)                    # what an answer may make the Studio do itself (eaos/studio/actions/runs.py)

VERBS = {
    'fix': ('Use the eaos tools to fix these cards of this project safely, end to end, without coming back between steps. '
            'Follow `status`: audit if it says so, then run_setup, run_try until the app runs, safety_net, then fix_start with '
            'exactly these cards, and for each card: finding and fix_read, then fix_edit, keeping the code laws of the EAOS instructions (least code, one home for every rule, nothing dead). A card you cannot fix (its change '
            'keeps failing the checks, or no safe change exists) gets fix_skip with its reason, and you go on with the next '
            'card: one card never stops the batch. Try every card yourself first: why an earlier batch skipped it is no '
            'reason now (EAOS\'s checks change), so skip only after your own change was refused. When every card was tried, call fix_finish, even if some were skipped; if it '
            'asks for a repair (the changes fail the checks together), repair on top with fix_edit card="REPAIR" and call it '
            'again. If '
            'status says fix_abandon (a batch that cannot be closed), call it and start again. Change code only with fix_edit: '
            'never write a file yourself. Add the why with `note` after each card. At the end, tell the person in plain words '
            'what was fixed, what was skipped and why, and on which branch; they accept or undo it in the Studio. If nothing '
            'was kept, say so plainly: never say it is done.'),
    'verify': ('Use the eaos tools to verify these cards: read each with `finding`, look at the code it points at (Read, '
               'Grep), and decide whether the problem is still there, already gone, or a false alarm, with the evidence. '
               'Record each verdict with `note` (card set). Change nothing.'),
    'explain': ('Use the eaos tools to explain these cards to the person: for each, with `finding` and `impact`, say what is '
                'wrong, why it matters to them, and what fixing it would change, in plain words with no jargon. Change nothing.'),
    'plan': ('Use the eaos tools to plan these cards: read them (`finding`, `impact`, `plan`, `structure`), then propose an '
             'order of batches, what waits for what, and the risk of each batch, in plain words. Record the plan with `note`. '
             'Change nothing.'),
}


# A step whose answer leads straight on, done through to where the person decides.
CHAINS = {'blueprint_start': 'then do what its answer says through to blueprint_design (the spec, blueprint_spec until it '
                             'is complete, asking the person only real choices), always with the same project; stop there: the '
                             'person reads the blueprint and agrees to build it (build_start).'}


def build(verb, cards, project, lang='ar', action=None, inputs=None, labels=None, where=None):
    """The prompt of a run: a verb over cards, or one assistant action with its inputs (and, for a Fix, where the person
    chose to build and deliver it)."""
    language = NAMES.get(lang, NAMES['en'])
    if verb:
        listed = '\n'.join(f"- {card['id']}: {card.get('title') or ''} ({', '.join(card.get('paths') or [])})".rstrip(' ()') for card in cards)
        task = f"{VERBS[verb]}\n\nThe cards ({len(cards)}):\n{listed}\nCard ids for the tools: {json.dumps([c['id'] for c in cards])}"
        if verb == 'fix' and where:
            task += (f"\nThe person chose where this batch goes: call fix_start with base={json.dumps(where['base'])}, "
                     f"base_commit={json.dumps(where['base_commit'])}, deliver_as={json.dumps(where['deliver_as'])}, "
                     f"merge_into={json.dumps(where['merge_into'])}. If it answers base_moved, stop and tell the person the "
                     'branch moved: they preview the fix again.')
    else:
        label = (labels or {}).get(action, {}).get('en', action)
        shown = {k: v for k, v in (inputs or {}).items() if v is not None and not (k == 'project' and v == str(project))}
        task = (f'Use the eaos tools for this one step of the EAOS way: {label} (the `{action}` tool)'
                + (f', with these inputs from the person: {json.dumps(shown, ensure_ascii=False)}' if shown else '')
                + '. Call `status` first; ' + CHAINS.get(action, 'do what the step needs and no more.'))
    return (f'{task}\n\nThe project is the current folder ({project.name}). This request comes from the EAOS Studio, where the '
            f'person follows every step. {ASK}\nWrite every message in {language}, the short notes between tools too: the person reads them live in the Studio.')


def done(result):
    """The words of a direct step that ended: a check whose tools broke says which, and where it goes on from."""
    broke = ', '.join(((result.get('counts') or {}).get('failed_tools') or []) if isinstance(result, dict) else [])
    if not broke: return {'en': 'Done', 'ar': 'تم'}
    return {'en': f'Done, but these tools failed: {broke}. Run them again from the check map.',
            'ar': f'تم، لكن هذه الأدوات فشلت: {broke}. أعد تشغيلها من خريطة الفحص.'}


def acts(question, option):
    """The EAOS action the person's chosen option means (an option with `action`, or the id `abandon`), or None."""
    chosen = next((o for o in question.get('options') or [] if o.get('id') == option), None)
    if chosen is None: return None
    action = chosen.get('action') or ('fix_abandon' if chosen['id'] in ('abandon', 'fix_abandon') else None)
    return action if action in ACTS else None


def answer(question, option, text, lang='ar', done=None):
    """The words that resume a session with the person's answer (and what the Studio already did for it)."""
    chosen = next((o for o in question.get('options') or [] if o.get('id') == option), None)
    said = (chosen or {}).get('label', {}).get(lang) or (chosen or {}).get('label', {}).get('en') or option or ''
    parts = [f'The person answered in the Studio: {said}' + (f' (option "{option}")' if option else '')]
    if text: parts.append(f'They added: {text}')
    if done: parts.append(f'The Studio already ran {done[0]} for this answer; its result: {json.dumps(done[1], ensure_ascii=False)[:1500]}.')
    parts.append('Go on from where you stopped.')
    return ' '.join(parts)


def _both(words):
    """{'en', 'ar'} from a string (the same in both) or a dict with either, each language falling back to the other."""
    if isinstance(words, str): words = {'en': words, 'ar': words}
    if not isinstance(words, dict): return None
    return {'en': words.get('en') or words.get('ar'), 'ar': words.get('ar') or words.get('en')}


def _option(index, option):
    """One option normalised: its id, its label in both languages, and the EAOS action it means; None when unreadable."""
    if isinstance(option, str): option = {'id': f'o{index + 1}', 'label': option}
    if not isinstance(option, dict): return None
    return {'id': str(option.get('id') or f'o{index + 1}'), 'label': _both(option.get('label') or option.get('id')),
            **({'action': option['action']} if option.get('action') in ACTS else {})}


def question_in(text):
    """The question block at the end of the assistant's words, normalised; None when there is none."""
    found = QUESTION.findall(text or '')
    if not found: return None
    try: data = json.loads(found[-1])
    except ValueError: return None
    if not isinstance(data, dict): return None
    words = _both(data.get('text'))
    if not words or not words['en']: return None
    options = [row for index, option in enumerate(data.get('options') or []) if (row := _option(index, option))]
    recommendation = data.get('recommendation')
    if recommendation not in {o['id'] for o in options}: recommendation = None
    return {'text': words, 'options': options, 'recommendation': recommendation}


def consent_question(payload):
    """run_setup's own question, when the assistant ended its turn on it without asking with a block."""
    ask = payload.get('ask_the_person') or payload.get('question') or ''
    words = _both(ask if isinstance(ask, dict) else str(ask))
    if not words['en']:
        words = {'en': 'May EAOS run your app in an isolated copy to prepare and check the fixes?',
                 'ar': 'تسمح لـ EAOS يشغّل تطبيقك في نسخة معزولة عشان يجهّز الإصلاحات ويفحصها؟'}
    return {'text': words, 'options': [{'id': 'yes', 'label': {'en': 'Yes, go ahead', 'ar': 'نعم، موافق'}},
                                       {'id': 'no', 'label': {'en': 'No', 'ar': 'لا'}}],
            'recommendation': 'yes', 'why': 'run consent'}


def assistant_question(payload):
    """The check's own stop when the person's assistant does not answer (agent_tools._assistant_not_ready): what is
    wrong, how to fix it, and their choice: check again once fixed, or this one check without AI."""
    found = payload.get('assistant') or {}
    reason = found.get('reason') or {}
    name = found.get('name') or 'Your assistant'
    return {'text': {'en': f"The check did not start: {name} is not answering. {reason.get('en') or found.get('code') or ''} "
                           'Fix it and check again, or start this check without AI (the report says why).',
                     'ar': f"ما بدأ الفحص: {name} ما يرد. {reason.get('ar') or reason.get('en') or found.get('code') or ''} "
                           'صلّحه وأعد الفحص، أو ابدأ هذا الفحص بدون ذكاء (التقرير يذكر السبب).'},
            'options': [{'id': 'retry', 'label': {'en': 'I fixed it: check again', 'ar': 'صلّحته: افحص من جديد'}},
                        {'id': 'without_ai', 'label': {'en': 'Start this check without AI', 'ar': 'ابدأ هذا الفحص بدون ذكاء'}}],
            'recommendation': 'retry', 'why': 'assistant'}


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
