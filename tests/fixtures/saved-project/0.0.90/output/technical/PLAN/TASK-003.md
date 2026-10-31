# TASK-003: Dead code: app/old_report.py (no production entry point reaches it)

> claim: CLM-003 · pattern: remove_dead · priority: 0.0

> repair · ready

No data for this section in this snapshot.

## The problem

Dead code: app/old_report.py (no production entry point reaches it)

Code nobody runs is still read, maintained and reviewed, and can be switched back on without anyone noticing.

## Evidence

- facts: FACT-0de6b2b4ef840623
- probes: PRB-003
- falsifier: A production path that reaches it: an import, a call, or a registry entry naming it that the text search missed.

## Blast radius

- files: app/old_report.py
- مستوردون مباشرون (0): —
- غير مباشرين (0): —
- تدفقات مارّة: —
- اختبارات مغطية: —
- executed coverage: —
- شركاء التغيير: —

## Options

| Option | Cost | Verdict |
|---|---|---|
| الحذف الآن مع إعادة التدقيق | منخفضة | مختار: الدليل آلي بالكامل |
| إبقاؤه بمالك وسبب مكتوب في eaos.engagement.json | صفر | حين يكون تجريبيًا أو قادمًا |
| لا نفعل شيئًا | يبقى عبئًا على القراءة والمراجعة | مرفوض ما دامت القاعدة قائمة |
| لا نفعل شيئًا | صفر الآن | يبقى الكود الميت عبئًا على القراءة والصيانة، ويصعّب تغييرات لا تعرف بوجوده، وقد يُعاد تفعيله دون تحذير |

## Before and after

- unreachable module `app/old_report.py`: no production entry point imports it
- the module app/old_report.py is deleted, the audit no longer reports it, and nothing that imported it remains.

## Proposed change

احذف الملف أو الرمز، ثم احذف ما لا يستورده إلا هو، وشغّل الاختبارات: لا مسار إنتاجي يصل إليه ولا نص يذكر اسمه.

## Acceptance criterion

| Command | Expected |
|---|---|
| {{PYTHON}} -B -c 'import json, subprocess, sys, tempfile
holder = tempfile.TemporaryDirectory(prefix='"'"'eaos-deadcode-'"'"'); tmp = holder.name
r = subprocess.run([sys.executable, '"'"'-m'"'"', '"'"'eaos'"'"', '"'"'facts'"'"', '"'"'.'"'"', '"'"'--out'"'"', tmp])
if r.returncode: sys.exit(r.returncode)
facts = json.load(open(tmp + '"'"'/facts/deadcode.json'"'"'))['"'"'facts'"'"']
left = [f for f in facts if (f['"'"'location'"'"']['"'"'path'"'"'], f['"'"'location'"'"']['"'"'symbol'"'"'], f['"'"'value'"'"']['"'"'rule'"'"']) == ('"'"'app/old_report.py'"'"', '"'"'app/old_report.py'"'"', '"'"'unreachable-module'"'"')]
sys.exit(1 if left else 0)
' | the next audit no longer reports the module app/old_report.py as dead code |

## Rollback

revert واحد يعيد الملف أو الرمز كما كان.

## Effort

S · estimate confidence: A rule on the files it touches and its dependents (eaos/analysis/planning/roadmap.py), not a measured duration.
