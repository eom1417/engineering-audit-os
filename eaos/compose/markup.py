"""The HTML pieces every page EAOS writes shares: escaping, and the same words in both languages."""
import html


def esc(value):
    return html.escape(str(value), quote=True)


def svg_text(x, y, text, cls, side='left', rtl=False, attrs=''):
    """SVG text anchored at x on its left or right side; Arabic runs right to left so its words keep their order."""
    anchor = ('end' if side == 'left' else 'start') if rtl else ('start' if side == 'left' else 'end')
    return (f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}" direction="{"rtl" if rtl else "ltr"}" class="{cls}"{attrs}>'
            f'{esc(text)}</text>')


def fit(text, room):
    """A name cut from the left to fit `room` characters: the end of a path says the most."""
    text = str(text)
    return text if len(text) <= room else '…' + text[-(room - 1):]


def both(ar, en, tag='span', cls=''):
    """The same words in both languages; the page shows one of them."""
    extra = f' {cls}' if cls else ''
    return f'<{tag} class="l-ar{extra}" lang="ar">{ar}</{tag}><{tag} class="l-en{extra}" lang="en">{en}</{tag}>'
