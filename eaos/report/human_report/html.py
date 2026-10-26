"""The small HTML pieces every section of REPORT.html is made of: a word, a number with its meaning, a chip."""
from ...core.language.markup import both as T, esc
from .words import W


# ---------------------------------------------------------------- html helpers

def w(key, tag='span', cls=''):
    ar, en = W[key]
    return T(esc(ar), esc(en), tag, cls)


def num(value, meaning, cls='n'):
    """A number, with what it means in a data attribute; the visible words beside it say it too."""
    return f'<span class="{cls}" data-meaning="{esc(meaning)}">{esc(value)}</span>'


def lit(text):
    """A file path or an identifier, shown as it is, left to right; the readability check does not read it as a score."""
    return f'<code class="lit" dir="ltr" data-literal="1">{esc(text)}</code>'


def quoted(text):
    """A sentence the plan wrote in the reader's language, quoted as it is (it may name an identifier such as E4)."""
    return f'<span class="quote" data-literal="quote">{esc(text or "")}</span>'


def said(text):
    """A sentence the engine wrote (in English or in the report's language), shown as written."""
    return f'<span class="said" dir="auto" data-literal="quote">{esc(text)}</span>' if text else ''


def tech(text):
    """A technical sentence the engine wrote in English, kept as written."""
    return f'<span class="tech" lang="en" dir="ltr" data-literal="1">{esc(text)}</span>' if text else ''


def unavailable(section, error=None):
    note = f'<!-- {esc(type(error).__name__)} -->' if error else ''
    return f'<div class="card na">{w("na", "p")}{note}</div>'


def sev_chip(severity):
    return f'<span class="chip sev-{severity}" data-severity="{severity}"><i aria-hidden="true"></i>{w(severity)}</span>'


def priority_words(top, severity=None):
    band = 'vhigh' if top <= 10 else 'high' if top <= 30 else 'mid' if top <= 60 else 'low'
    # The ranking weighs how much of the program a problem reaches; a known security hole reaches little code and
    # is still urgent. A serious problem is never shown as low priority: its severity decides.
    if severity in ('critical', 'high') and band in ('mid', 'low'):
        return T('عاجلة بسبب خطورتها', 'Urgent because of its severity')
    ar = {'vhigh': 'أولوية عالية جدًا', 'high': 'أولوية عالية', 'mid': 'أولوية متوسطة', 'low': 'أولوية منخفضة'}[band]
    en = {'vhigh': 'Very high priority', 'high': 'High priority', 'mid': 'Medium priority', 'low': 'Low priority'}[band]
    if band == 'low':
        return T(f'{ar} — في النصف الأدنى من الترتيب', f'{en} — in the lower half of the ranking')
    rank = num(f'{top}%', f'rank among all problems: in the top {top}%')
    return T(f'{ar} — ضمن أعلى {rank} من المشاكل', f'{en} — in the top {rank} of problems')
