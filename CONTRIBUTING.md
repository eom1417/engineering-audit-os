# تطوير القواعد والـCLI

1. اقرأ `core/EXTENSION-PROTOCOL.md` وحدد المشكلة أو failure mode الجديد.
2. أضف المصدر بإصداره وحدود قراءته إلى sources.json. لا تنسب synthesis إلى فيديو.
3. أعد استخدام control ID إن كان نفس invariant؛ افصل applicability عن severity؛ وثق contradiction resolution.
4. عدل controls.json أو core أو schemas، ثم `python tools/render.py`.
5. شغّل `python tools/validate.py` و`python -m unittest discover -s tests -v`.
6. راجع نواتج diff وcontext packet sizes وتوافق run schema. migration مطلوبة إذا تغير عقد السجلات.
7. أضف changelog، لا ترفع ادعاء field-validation دون تجارب منشورة داخل المشروع.

الـCLI مستقل عن agent providers. إضافة adapter ليست مبررًا لتغيير evidence-first policy أو الإرسال التلقائي لكود العميل.
