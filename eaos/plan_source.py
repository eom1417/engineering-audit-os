"""Any plan the person has, read for the build (eaos/blueprint.py): pasted words, a file of any common kind, or a folder
of them, with the pictures of its screens kept as files for the assistant to look at (it reads pictures itself)."""
import html
import re
import subprocess
import zipfile
from pathlib import Path

SOURCE_SUFFIXES = ('.md', '.markdown', '.txt', '.text', '.rst', '.pdf', '.docx', '.html', '.htm', '.json', '.yaml', '.yml')
IMAGE_SUFFIXES = ('.png', '.jpg', '.jpeg', '.webp', '.gif')


def read_plan(path=None, text=None):
    """(the plan's text, the paths of its pictures): pasted words, one file, one picture, or a folder of them."""
    where = Path(path).expanduser() if path else None
    if where is not None and where.is_dir(): return _folder(where, (text or '').strip())
    if where is not None and where.suffix.lower() in IMAGE_SUFFIXES: return (text or '').strip(), [str(where)]
    return read_source(path, text), []


def _folder(where, text):
    files = sorted(p for p in where.rglob('*') if p.is_file() and not any(part.startswith('.') for part in p.relative_to(where).parts))
    pictures = [str(p) for p in files if p.suffix.lower() in IMAGE_SUFFIXES]
    words = [f'## {p.relative_to(where)}\n\n{read_source(p)}' for p in files if p.suffix.lower() in SOURCE_SUFFIXES]
    plan = '\n\n'.join(part for part in [text, *words] if part)
    if not plan and not pictures: raise ValueError(f'the folder holds no plan (a document or pictures of the screens): {where}')
    return plan, pictures


def read_source(path=None, text=None):
    """The plan as plain text: pasted words as they are, or a file of any common kind."""
    if text and text.strip(): return text.strip()
    if not path: raise ValueError('no plan was given: pass the file path or paste its text')
    path = Path(path).expanduser()
    if not path.is_file(): raise ValueError(f'the plan file was not found: {path}')
    suffix = path.suffix.lower()
    if suffix == '.pdf': return _pdf(path)
    if suffix == '.docx': return _docx(path)
    raw = path.read_text(encoding='utf-8', errors='replace')
    if suffix in ('.html', '.htm'):
        raw = re.sub(r'(?is)<(script|style)\b.*?</\1>', '', raw)
        raw = re.sub(r'(?i)<br\s*/?>|</(p|div|li|h\d|tr)>', '\n', raw)
        raw = html.unescape(re.sub(r'<[^>]+>', '', raw))
    return re.sub(r'\n{3,}', '\n\n', raw).strip()


def _pdf(path):
    try:
        from pypdf import PdfReader        # when installed; the command-line tool otherwise
        return '\n\n'.join((page.extract_text() or '') for page in PdfReader(str(path)).pages).strip()
    except ImportError:
        pass
    try:
        done = subprocess.run(['pdftotext', '-layout', str(path), '-'], capture_output=True, text=True, timeout=120)
    except FileNotFoundError:
        raise ValueError('this PDF cannot be read here (no pypdf, no pdftotext): paste its text instead') from None
    if done.returncode: raise ValueError(f'the PDF could not be read: {done.stderr[-300:]}')
    return done.stdout.strip()


def _docx(path):
    """Word's text: the paragraphs of word/document.xml, one per line, tables row by row."""
    with zipfile.ZipFile(path) as archive:
        xml = archive.read('word/document.xml').decode('utf-8', errors='replace')
    xml = re.sub(r'</w:p>', '\n', xml)
    xml = re.sub(r'</w:tc>', ' | ', xml)
    return html.unescape(re.sub(r'<[^>]+>', '', xml)).strip()
