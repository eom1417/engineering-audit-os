"""What every emitter shares: the record of a file it wrote, and its templates."""
from dataclasses import dataclass
from pathlib import Path
from string import Template

TEMPLATES = Path(__file__).resolve().parent.parent / 'templates/emit'


@dataclass(frozen=True)
class Emitted:
    path: str           # relative to the report directory
    tool: str           # the tool that judges it, a name in upstreams/toolchain.json or a schema check
    argv: tuple = ()    # the validator command; '{path}' is replaced by the absolute file path


def render(template, **values):
    """A template from eaos/templates/emit/, filled with string.Template: $name, and $$ for a literal dollar."""
    return Template((TEMPLATES / template).read_text(encoding='utf-8')).substitute(**values)
