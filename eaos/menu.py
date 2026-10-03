"""`/eaos` alone: what the person can ask EAOS for now, as a short menu with the step that fits the project first.

menu(project) reads the project as `status` does and returns only the options that make sense now: no "continue"
without open work, no "review the fixes" without a branch waiting, no report before a check. Each option carries its
words in Arabic and English, a description made from the project's own numbers, and what the assistant does once it is
chosen. The options are cut into pages of at most four, the most one choice shows in Claude Code: when there are more,
the fourth place of a page is "more", which shows the next page. The first option is always the recommended one.
"""
from pathlib import Path
import os

PAGE = 4
MORE = 'more'

# id: (Arabic label, English label, what the assistant does once the person chose it)
OPTIONS = {
    'continue': ('تابع من حيث توقفنا', 'Continue where we stopped',
                 'Continue the open work exactly as status.handover.how_to_continue says, without asking the person again what '
                 'they already answered.'),
    'branch': ('اختر الفرع', 'Choose the branch',
               'status asks which branch: show the branches as a choice (when each last changed, how far ahead of the main '
               'branch, which you recommend and why), then choose_branch with person_said set to their choice.'),
    'decide': ('راجع الإصلاحات الجاهزة', 'Review the ready fixes',
               'Say in plain words what the waiting branch fixes (plan, findings), then offer three choices: take it in '
               '(accept with person_agreed=true), throw it away (undo), or decide later. Act only on their choice.'),
    'audit': ('افحص المشروع', 'Check the project',
              'audit (fresh=true when status says the code changed), wait until it is done, then explain how healthy the '
              'project is and its five most important problems simply, with evidence from finding.'),
    'fix': ('أصلح الدفعة التالية', 'Fix the next batch',
            'Fix the next batch end to end, following status: run_setup (its one question), run_try, safety_net, fix_start, '
            'fix_edit for each card, fix_finish. Then say what was fixed, on which branch, and offer to take it in or undo.'),
    'status': ('أين وصلنا؟', 'Where are we?',
               'From status: in five short lines, where the project is, the progress, what is open or waiting, and the next '
               'step. Then offer this menu again.'),
    'report': ('افتح التقرير', 'Open the report',
               'open_report, then tell the person where the page is, that it is one file they can send to anyone as it is, '
               'and what is new in it since their last visit (report_errors plainly, if any).'),
    'tasks': ('المنجز والقادم', 'Done and coming next',
              'From plan and status.progress: a short table of what is done (merged), what waits for the person, and the '
              'next cards in order, with the progress (closed of total, percent).'),
    'ask': ('اسأل عن مشروعك', 'Ask about your project',
            'Ask the person what they want to know (for example: what does changing this file touch, where is this API used, '
            'why is this a problem). Answer only from EAOS records: impact for a file or symbol, ask for a question, finding, '
            'structure and report_file for the rest; cite the files. Say plainly when the records do not answer it.'),
    'build': ('ابنِ مشروعًا من خطة', 'Build a project from a plan',
              'Ask for the plan (a file path or pasted text), then build it end to end: blueprint_start, the spec, '
              'blueprint_design, build_start, every milestone with build_edit and build_finish.'),
    'tools': ('الأدوات والمحركات', 'Tools and engines',
              'tools_check, then say which EAOS version runs and how many tools are installed, and a short table of the '
              'tools this project needs (needed_here), those for the check first: what each is for, installed or not, at '
              'which version. If any is missing, the one command that installs it (`install`), and what the check loses '
              'without it.'),
}

DESCRIBE = {   # the description when nothing more specific is known
    'continue': ('العمل المفتوح يكمل من آخر خطوة، بلا أسئلة جديدة', 'The open work goes on from its last step, no new questions'),
    'branch': ('في المشروع أكثر من فرع: اختر الفرع الذي نعمل عليه', 'The project has several branches: choose the one to work on'),
    'decide': ('فرع إصلاحات ينتظر قرارك: تدمجه أو تتراجع عنه', 'A branch of fixes waits for you: take it in or throw it away'),
    'audit': ('فحص كامل (5 إلى 30 دقيقة) وشرح أهم المشاكل ببساطة', 'A full check (5 to 30 minutes), its main problems in plain words'),
    'fix': ('في نسخة معزولة، وتصلك كفرع جديد. مشروعك لا يتغير', 'In an isolated copy, handed over as a new branch; your project stays as it is'),
    'status': ('الحالة والتقدم والخطوة التالية باختصار', 'The state, the progress and the next step, briefly'),
    'report': ('التقرير التفاعلي في المتصفح: ملف واحد ترسله لمن تريد', 'The interactive report in the browser: one file to send to anyone'),
    'tasks': ('ما انتهى، وما ينتظر قرارك، وما التالي في الخطة', 'What is done, what waits for you, and what comes next in the plan'),
    'ask': ('مثل: ماذا يتأثر لو غيّرت هذا الملف؟ أين يُستخدم هذا الـ API؟', 'Like: what does changing this file touch? Where is this API used?'),
    'build': ('أعطني ملف الخطة، وأبنيه ببنية احترافية خطوة بخطوة', 'Give me the plan, and I build it with a sound structure, step by step'),
    'tools': ('ما المثبّت ونسخته، وما الناقص وكيف يُثبَّت', 'What is installed and at which version, what is missing and how to install it'),
}
MORE_WORDS = (('خيارات أخرى…', 'More options…'), ('بقية ما يقدمه EAOS هنا', 'The rest of what EAOS offers here'))


def _status(project):
    from .build_tools import status_of
    return status_of(project)


def _numbers(answer, lang):
    """The descriptions made from this project's own numbers, where they say more than the generic one."""
    ar, said = lang == 'ar', {}
    progress = answer.get('progress') or {}
    handover = answer.get('handover') or {}
    work, busy = handover.get('open_work'), handover.get('running_job')
    if busy:
        said['continue'] = (f"{busy['kind']} يعمل الآن، وأتابعه من حيث وصل" if ar else f"A {busy['kind']} is running: I follow it from where it is")
    elif work:
        number = work.get('number') or work.get('milestone')
        said['continue'] = (f"الدفعة {number} مفتوحة: حُفظ {len(work['kept'])}، باقي {len(work['left'])}" if ar else
                            f"Batch {number} is open: {len(work['kept'])} kept, {len(work['left'])} left")
    if answer.get('waiting_branch'):
        said['decide'] = (f"الفرع {answer['waiting_branch']} ينتظر قرارك: تدمجه أو تتراجع عنه" if ar else
                          f"{answer['waiting_branch']} waits for you: take it in or throw it away")
    if progress.get('total'):
        left = progress['total'] - progress['closed']
        said['tasks'] = (f"انتهى {progress['closed']} من {progress['total']} ({progress['percent']}%)، وباقي {left}" if ar else
                         f"{progress['closed']} of {progress['total']} done ({progress['percent']}%), {left} left")
        if left: said['fix'] = (f"باقي {left} مشكلة. الإصلاح في نسخة معزولة ويصلك كفرع جديد" if ar else
                                f"{left} problems left; fixed in an isolated copy, handed over as a new branch")
    if answer.get('checked') and (answer.get('next') or {}).get('tool') == 'audit':
        said['audit'] = ('تغيّر الكود أو EAOS بعد آخر فحص: افحص من جديد' if ar else 'The code or EAOS changed since the last check: check again')
    return said


def _available(answer, folder):
    """The options that make sense now, the recommended one first."""
    if answer is None:                                      # not a project folder: only what needs none
        return ['build', 'tools']
    if answer.get('status') == 'needs_branch':
        return ['branch', 'status', 'tools']
    handover = answer.get('handover') or {}
    open_work = bool(handover.get('open_work') or handover.get('running_job'))
    if answer.get('mode') == 'build from a plan':         # its plan is read already: the build goes on from status's next step
        waiting = (answer.get('next') or {}).get('tool') == 'accept'
        return ['decide' if waiting and not open_work else 'continue', 'status', 'tools']
    checked = bool(answer.get('checked'))
    step = (answer.get('next') or {}).get('tool') or ''
    left = (answer.get('progress') or {}).get('total', 0) - (answer.get('progress') or {}).get('closed', 0)
    order = []
    if open_work: order.append('continue')
    if answer.get('waiting_branch'): order.append('decide')
    if not checked or step == 'audit': order.append('audit')
    if checked and not open_work and not answer.get('waiting_branch') and left > 0 and step != 'audit': order.append('fix')
    if checked: order += ['report', 'tasks', 'ask']
    order.append('status')
    if checked and 'audit' not in order: order.append('audit')
    order += ['build', 'tools']
    return order


def pages(ids):
    """At most four to a page; when more are left, the fourth place is MORE, which shows the next page."""
    out, rest = [], list(ids)
    while rest:
        if len(rest) <= PAGE:
            out.append(rest); break
        out.append(rest[:PAGE - 1] + [MORE]); rest = rest[PAGE - 1:]
    return out


def menu(project=None, lang=None):
    from . import guided
    folder = Path(project or os.getcwd()).expanduser().resolve()
    state = guided.load(folder) if folder.is_dir() else None
    try:
        answer = _status(str(folder)) if state or guided.looks_like_project(folder) else None
    except ValueError:                                      # not a project folder after all
        answer = None
    lang = guided.language(lang, guided.load(folder) if folder.is_dir() else None)
    ar = lang == 'ar'
    ids = _available(answer, folder)
    said = _numbers(answer or {}, lang)
    recommended = ' (موصى به)' if ar else ' (Recommended)'

    def option(key, first=False):
        if key == MORE:
            return {'id': MORE, 'label': MORE_WORDS[0][0 if ar else 1], 'description': MORE_WORDS[1][0 if ar else 1],
                    'do': 'Show the next page of this menu, the same way.'}
        return {'id': key, 'label': OPTIONS[key][0 if ar else 1] + (recommended if first else ''),
                'description': said.get(key) or DESCRIBE[key][0 if ar else 1], 'do': OPTIONS[key][2]}
    return {'project': folder.name, 'language': lang, 'state': _headline(folder.name, answer, ar),
            'question': 'ماذا تريد أن نفعل؟' if ar else 'What would you like to do?',
            'pages': [[option(key, first=(n == 0 and i == 0)) for i, key in enumerate(page)] for n, page in enumerate(pages(ids))],
            'how_to_show': ('Show pages[0] as one choice (in Claude Code: AskUserQuestion with header "EAOS", the question '
                            'preceded by `state`, and each option\'s label and description as they are, in this order). Without '
                            'a choice tool, write `state`, then the options numbered with their descriptions, and wait for '
                            'the person\'s answer. "more" shows the next page. Once they chose, do what the option\'s `do` says '
                            'at once, without asking again; their own words instead of a choice are a request: do it.')}


def _headline(name, answer, ar):
    """One line: the project, its branch, the progress, and what waits for the person."""
    parts = [f'EAOS · {name}']
    if not answer:
        parts.append('ليس مشروعًا بعد' if ar else 'not a project yet')
        return ' · '.join(parts)
    if answer.get('branch'): parts.append(answer['branch'])
    progress = answer.get('progress') or {}
    if progress.get('total'):
        parts.append(f"المنجز {progress['closed']} من {progress['total']} ({progress['percent']}%)" if ar else
                     f"{progress['closed']} of {progress['total']} done ({progress['percent']}%)")
    elif answer.get('mode') != 'build from a plan' and answer.get('status') != 'needs_branch' and not answer.get('checked'):
        parts.append('لم يُفحص بعد' if ar else 'not checked yet')
    if answer.get('waiting_branch'): parts.append('فرع ينتظر قرارك' if ar else 'a branch waits for you')
    if (answer.get('handover') or {}).get('open_work'): parts.append('عمل مفتوح' if ar else 'work open')
    return ' · '.join(parts)
