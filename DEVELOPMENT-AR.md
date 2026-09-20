# بيئة التطوير المحلية

الريبو المستعاد: `/workspace/engineering-audit-os`.
الحزمة الأصلية والأدلة المنقولة: `/workspace/engineering-audit-bundle`.
نتائج التحقق الحالي: `/workspace/eaos-review`.

```bash
cd /workspace/engineering-audit-os
source .venv/bin/activate
eaos --version
python -m unittest discover -s tests -v
python tools/validate.py
```

المشروع مثبت بوضع editable؛ تعديلات مصدر Python تظهر في الأمر المثبت دون إعادة تثبيت. إذا عدلت إعدادات الحزمة أعد `python -m pip install -e .`. بعد تعديل القواعد أو schemas أو core شغّل `python tools/render.py` ثم تحقق من diff ومن `tools/validate.py`.

إعادة تجهيز الحاوية بعد استبدالها: `bash /workspace/setup.sh`. السكربت يحتاج صلاحية تثبيت حزم النظام والوصول لتنزيل اعتماديات البناء.

لجلسة محلية جديدة دون مزود نموذج:

```bash
eaos audit /absolute/path/to/project --out /workspace/eaos-runs/new-review
eaos next /workspace/eaos-runs/new-review
```

اختر مجلد إخراج جديدًا خارج المشروع المستهدف؛ الأمر لا يستبدل جلسة موجودة. `audit` يبدأ سير عمل الوكيل ولا ينفذ تحليل نموذج مستقلًا. للتشغيل المتصل بنموذج استخدم `run` وإعداد provider حسب `core/RUNTIME.md`؛ لم يُعد مزود خارجي ضمن هذا التجهيز.

لإعادة تجربة التنفيذ المبرمجة في مجلد جديد:

```bash
.venv/bin/python /workspace/eaos-review/reproduce_demo.py /workspace/eaos-review/another-demo
```

لا توجد واجهة ويب أو dev server في هذه النسخة. تفاصيل الهيكلة والتقييم والخطة في [REVIEW-AR.md](REVIEW-AR.md).
