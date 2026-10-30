"""The rules of the repository's craft (M7.8) and its assistants' context (M7.9): each rule's sentence for one finding and
its fix, in English and Arabic; the thresholds are data (eaos/rules/repository-craft.json)."""
import json
from pathlib import Path

RULES_FILE = Path(__file__).resolve().parents[2] / 'rules' / 'repository-craft.json'

# rule: (English sentence, Arabic sentence, the fix (en), the fix (ar))
RULES = {
    'crowded-folder': ('{path} holds {count} source files at one level: a reader looks through all of them to find one',
                       '{path} فيه {count} ملف كود في مستوى واحد: اللي يدوّر على ملف يمر عليها كلها',
                       'Split it into folders by job, each named for what it holds.',
                       'وزّعه على مجلدات حسب الوظيفة، كل مجلد باسم اللي فيه.'),
    'prefix-family': ('{count} files in {path} share the prefix {prefix}: they are one job that wants its own folder',
                      '{count} ملفات في {path} تبدأ بـ{prefix}: وظيفة وحدة تستاهل مجلد خاص فيها',
                      'Move them into {path}/{folder}/ and drop the prefix from their names.',
                      'انقلها إلى {path}/{folder}/ وشِل البادئة من أسمائها.'),
    'vague-name': ('{path} ({lines} lines) has a name that says nothing of what it holds',
                   '{path} ({lines} سطر) اسمه ما يقول وش فيه',
                   'Split it by job and name each part for what it does.',
                   'قسّمه حسب الوظيفة، وسمِّ كل جزء باللي يسويه.'),
    'version-name': ('{path} sits beside {original}: two versions of one thing, and a reader cannot tell which is in use',
                     '{path} جنب {original}: نسختين من نفس الشي، واللي يقرا ما يعرف أيهم المستخدمة',
                     'Keep one: fold what the other adds into it, then remove it.',
                     'خلِّ وحدة: ادمج اللي تضيفه الثانية فيها، واحذف الثانية.'),
    'trap-folder': ('{path} is source code in a folder named {folder}, which build tools and checkers skip as output',
                    '{path} كود حقيقي في مجلد اسمه {folder}، وأدوات البناء والفحص تتجاهله كأنه مخرجات',
                    'Rename the folder for what it holds.',
                    'غيّر اسم المجلد باسم اللي فيه.'),
    'stale-doc-path': ('{path} names {named}, which is not in the repository: a reader following it lands nowhere',
                       '{path} يذكر {named}، وهو مو موجود في الريبو: اللي يتبعه ما يوصل لشي',
                       'Point it at where the file is now, or remove the line.',
                       'وجّهه لمكان الملف الحين، أو احذف السطر.'),
    'no-extending-guide': ('{count} source files and no map for extending them: every assistant and engineer reads around to learn which files a new page or endpoint touches',
                           '{count} ملف كود وما فيه خريطة للإضافة عليها: كل مساعد ومهندس يقرأ كثير عشان يعرف أي ملفات تتغير لما يضيف صفحة أو نقطة API',
                           "Take EAOS's draft (extending/EXTENDING.md in the check's report, drawn from the layers and how the project grew) into {path}, and one line in the context files pointing at it.",
                           'خذ مسودة EAOS (extending/EXTENDING.md في تقرير الفحص، مبنية من الطبقات ومن تاريخ نمو المشروع) إلى {path}، وسطر واحد في ملفات الكونتكست يشير لها.'),
    'tests-flat': ('{count} test files lie at one level of {path} while the code is in folders: a test is not found beside what it tests',
                   '{count} ملف اختبار في مستوى واحد داخل {path} والكود موزّع في مجلدات: الاختبار ما ينلقى جنب اللي يختبره',
                   'Give the tests the folders of the code they test.',
                   'رتّب الاختبارات بنفس مجلدات الكود اللي تختبره.'),
    'dev-detail': ('{path} publishes {what} of the computer it was made on (line {line}): if the repository is public, anyone reads it',
                   '{path} ينشر {what} من الجهاز اللي انعمل عليه (سطر {line}): لو الريبو عام، أي أحد يقراه',
                   'Keep machine details in the development notes outside the repository; use a relative path or a placeholder here.',
                   'خلِّ تفاصيل الجهاز في ملاحظات التطوير برا الريبو، واستخدم هنا مسار نسبي أو مثال.'),
    'context-heavy': ('The files an assistant reads at the start of every session ({files}) hold about {tokens} tokens',
                      'الملفات اللي يقراها المساعد أول كل جلسة ({files}) فيها تقريبًا {tokens} توكن',
                      'Keep what binds every session there; move history, done work and long references to files read when needed.',
                      'خلِّ فيها اللي يلزم كل جلسة بس، وانقل التاريخ والشغل المنتهي والمراجع الطويلة لملفات تنقرى وقت الحاجة.'),
    'context-repeat': ('{count} lines are said in two or more of the assistants\' context files ({files}): about {tokens} tokens read twice every session',
                       '{count} سطر مكرر في ملفين أو أكثر من ملفات الكونتكست ({files}): تقريبًا {tokens} توكن تنقرى مرتين كل جلسة',
                       'Say each once, in the file that owns it, and point to it from the others.',
                       'قل كل شي مرة وحدة في الملف المسؤول عنه، والملفات الثانية تشير له.'),
    'context-done': ('{path} still lists {count} done items an assistant reads every session',
                     '{path} لسه فيه {count} شي منتهي يقراه المساعد كل جلسة',
                     'Move the done items to an archive file, kept but not read at the start.',
                     'انقل المنتهي لملف أرشيف، يبقى محفوظ بس ما ينقرى أول الجلسة.'),
}


def limits():
    return json.loads(RULES_FILE.read_text(encoding='utf-8'))


def finding(rule, path, params):
    """One finding's value: its rule, its sentences and fix in both languages, its values."""
    english, arabic, fix_en, fix_ar = RULES[rule]
    said = lambda text: text.format_map(_Keep(params))
    return {'rule': rule, 'severity': 'low', 'path': path, 'params': params, 'en': said(english), 'ar': said(arabic),
            'fix_en': said(fix_en), 'fix_ar': said(fix_ar)}


class _Keep(dict):
    def __missing__(self, key): return '{' + key + '}'
