"""What the person sees and is asked: the fixed ending of every command, the questions and their answers, errors in
plain words.
"""
import json
import re
import sys
from pathlib import Path

from ...core.language import plain
from .project import save
from ...core.system.clock import now


ERRORS = Path(__file__).resolve().parents[2] / 'data/errors.json'
LINE = '─' * 60


class NeedsAnswer(Exception):
    """A yes/no question with nobody at a terminal to answer it."""

    def __init__(self, question):
        super().__init__(question['id'])
        self.question = question


class Declined(Exception):
    """The person said no; nothing was changed."""


class ToolsMissing(RuntimeError):
    """Tools the check needs on this project could not be installed, and the person did not choose to start without."""


# ---------------------------------------------------------------- what the person sees

def say(text, stream=None):
    print(text, file=stream or sys.stdout, flush=True)


def box(lang, happened, where=None, commands=(), status='ok', note=None, stream=None, log=None):  # limits: parameters -- the printed box's optional parts, each passed by keyword
    """The fixed ending of every user command: what happened, where, and what to copy next."""
    icon = {'ok': '✅', 'warn': '⚠️', 'fail': '❌', 'ask': '❓'}[status]
    words = BOX_WORDS['ar' if lang == 'ar' else 'en']
    lines = [LINE, f"{icon} {words['happened']}: {happened}"]
    for line in ([note] if isinstance(note, str) else note or []): lines.append(f'   {line}')
    if where: lines.append(f"📁 {words['where']}: {where}")
    if log: lines.append(f"🧾 {words['log']}: {log}")
    if commands:
        lines.append(f"⏭️  {words['next']}:")
        lines += [f'   {command}' for command in commands]
    lines.append(LINE)
    say('\n'.join(lines), stream)


BOX_WORDS = {'ar': {'happened': 'ما حدث', 'where': 'النتائج', 'log': 'السجل التقني', 'next': 'الخطوة التالية، انسخ والصق'},
             'en': {'happened': 'What happened', 'where': 'Results', 'log': 'Technical log', 'next': 'Next step, copy and paste'}}


# Whether the check may use the person's assistant (docs/AI-IN-THE-PIPELINE.md), asked once.
AI_QUESTION = {'ar': 'أبغى أستعين بمساعدك الذكي ({name}) في الفحص: يقرأ الحقائق ويفسّرها، ويخطّط الصورة المثالية لمشروعك. '
                     'كل ما يقوله يبقى فرضية مربوطة بدليلها، وبدونه يكمل الفحص بالقواعد. أوافق؟',
               'en': 'May I use your AI assistant ({name}) in the check: it reads the facts and interprets them, and plans '
                     'the ideal of your project. Everything it says stays a hypothesis tied to its evidence, and without it '
                     'the check goes on with the rules. OK?'}


WITHOUT_AI_QUESTION = {'ar': '{name} غير جاهز الآن. أبدأ هذا الفحص بدون ذكاء؟ التقرير يذكر السبب، وتقدر تفحص مرة ثانية بعد ما تصلحه.',
                       'en': '{name} is not ready now. Start this check without AI? The report records why, and you can check again '
                             'once it is fixed.'}


WITHOUT_QUESTION = {'ar': 'ما قدرت أثبّت أدوات يحتاجها الفحص: {names}. أبدأ الفحص بدونها؟ التقرير يذكر أنه فحص بدونها.',
                    'en': 'Some tools the check needs could not be installed: {names}. Start the check without them? The '
                          'report records that it ran without them.'}


def progress_printer(lang):
    def show(done, total, stage):
        say(f"   [{done + 1}/{total}] {plain.stage(stage, lang)}…")
    return show


def answered(state, qid):
    """The answer kept for question `qid` (None: not answered yet)."""
    return next((q['answer'] for q in state.get('questions') or [] if q['id'] == qid and q.get('answer') is not None), None)


def ask(state, qid, text, yes=False, kind='yes_no'):
    """A yes/no question: answered by --yes, by a person at a terminal, or returned to whoever runs us."""
    question = {'id': qid, 'kind': kind, 'text': text}
    asked = state.setdefault('questions', [])
    earlier = answered(state, qid)
    if earlier is not None: return earlier
    if yes: answer = True
    elif sys.stdin.isatty():
        reply = input(f"❓ {text} [{'نعم/لا' if state.get('lang') == 'ar' else 'yes/no'}] ").strip().lower()
        answer = reply in ('y', 'yes', 'نعم', 'ن', 'ايوه', 'ايوة', 'اي', 'اه', 'أيوه')
    else:
        raise NeedsAnswer(question)
    asked.append({**question, 'answer': answer, 'at': now()})
    save(state)
    if not answer: raise Declined(qid)
    return answer


# ---------------------------------------------------------------- errors in plain words

def catalog():
    return json.loads(ERRORS.read_text(encoding='utf-8'))['errors']


def explain(problem):
    """The catalog entry for an error: the first whose pattern matches its type and text."""
    text = f'{type(problem).__name__}: {problem}' if isinstance(problem, BaseException) else str(problem)
    for entry in catalog():
        if any(re.search(pattern, text) for pattern in entry['match']): return entry
    return next(entry for entry in catalog() if entry['id'] == 'unknown')


def show_error(lang, entry_id=None, problem=None, log=None):
    entry = next(e for e in catalog() if e['id'] == entry_id) if entry_id else explain(problem)
    text = entry[lang]
    box(lang, text['message'], status='warn' if entry['id'] in ('not_started', 'declined', 'interrupted') else 'fail',
        note=[text['fix']] + ([text['after']] if text.get('after') else []), commands=text['commands'], log=log)
