"""Which command belongs to which surface, so `eaos --help` reads as a map rather than a list."""
GROUPS = (
    ('start', 'ابدأ من هنا: أوامر موجِّهة بكلام بسيط', 'Start here: guided commands in plain words',
     ('start', 'next', 'status', 'show', 'do', 'accept', 'undo', 'doctor', 'clean', 'assistant', 'handover', 'mcp')),
    ('govern', 'الحوكمة كاملة من الطرفية', 'Full governance from a terminal',
     ('check', 'watch', 'runs', 'stop', 'pause', 'resume', 'retry', 'waiting', 'answer', 'sign-in', 'problems',
      'problem', 'fix', 'verify', 'explain', 'plan', 'branch', 'branches', 'history', 'compare', 'usage', 'rules',
      'govern')),
    ('run', 'الفحص والأدوات', 'The check and its tools', ('audit', 'tools')),
    ('cards', 'ما تشغّله بطاقات الإصلاح للتحقق', 'What a task card runs to check itself',
     ('facts', 'policy', 'decided', 'recheck')),
)


def epilog(language='ar'):
    lines = ['المجموعات:' if language == 'ar' else 'Command groups:']
    for _, arabic, english, members in GROUPS:
        lines.append(f"  {(arabic if language == 'ar' else english)}")
        lines.append('    ' + '  '.join(members))
    return '\n'.join(lines)
