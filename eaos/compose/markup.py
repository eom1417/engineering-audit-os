"""The HTML pieces every page EAOS writes shares: escaping, and the same words in both languages."""
import html


def esc(value):
    return html.escape(str(value), quote=True)


def both(ar, en, tag='span', cls=''):
    """The same words in both languages; the page shows one of them."""
    extra = f' {cls}' if cls else ''
    return f'<{tag} class="l-ar{extra}" lang="ar">{ar}</{tag}><{tag} class="l-en{extra}" lang="en">{en}</{tag}>'
