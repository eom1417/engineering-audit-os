"""What the project declared out of scope for analysis.

Reading a declared field is extraction, not policy interpretation, so it belongs in this layer:
every collector gets the same answer without the facts layer depending on the ledger.

A vendored directory is one whose contents were copied in from elsewhere and are not the
reader's code. The fact that a vendored dependency is in the tree does not turn the audit
into an audit of that dependency: the reader wants a report about their code. By default
the engine excludes a small set of well-known vendored directory names; a project that
genuinely wants them analysed declares `include_vendored: true` in `eaos.policy.json`.
"""
import json
from pathlib import Path

FILENAME = 'eaos.policy.json'
VENDORED = ("testdata", "fixtures", "vendor", "node_modules", "third_party",
            "generated", ".venv", "dist", "build")


def _include_vendored(target, path=None):
    """True when the project's policy says vendored paths are part of the analysis."""
    candidate = Path(path) if path else Path(target) / FILENAME
    if not candidate.is_file(): return False
    try: policy = json.loads(candidate.read_text(encoding='utf-8'))
    except (ValueError, OSError): return False
    analysis = policy.get('analysis') or {}
    if not isinstance(analysis, dict): return False
    flag = analysis.get('include_vendored')
    return bool(flag)


def declared_exclusions(target, path=None):
    """Paths the project declares and the vendored defaults the engine applies.

    Silent exclusion is forbidden: every entry carries a reason the summary must surface.
    """
    candidate = Path(path) if path else Path(target) / FILENAME
    declared = []
    if candidate.is_file():
        try: policy = json.loads(candidate.read_text(encoding='utf-8'))
        except (ValueError, OSError): policy = {}
        patterns = ((policy.get('analysis') or {}).get('exclude')) or []
        if not isinstance(patterns, list) or not all(isinstance(item, str) for item in patterns):
            raise ValueError('analysis.exclude must be an array of path patterns')
        declared = sorted({item.strip('/') for item in patterns if item.strip('/')})
    vendored = [] if _include_vendored(target, path) else list(VENDORED)
    return sorted({*declared, *vendored})


def vendored_patterns():
    """The default vendored directory names the engine excludes unless the project opts in."""
    return list(VENDORED)


def exclusion_reasons(target, path=None):
    """For every exclusion pattern, the reason the engine applied it.

    Used by the summary that must surface every exclusion; never returns an entry without
    a reason attached.
    """
    candidate = Path(path) if path else Path(target) / FILENAME
    declared = []
    if candidate.is_file():
        try: policy = json.loads(candidate.read_text(encoding='utf-8'))
        except (ValueError, OSError): policy = {}
        patterns = ((policy.get('analysis') or {}).get('exclude')) or []
        if isinstance(patterns, list) and all(isinstance(item, str) for item in patterns):
            declared = sorted({item.strip('/') for item in patterns if item.strip('/')})
    reasons = {}
    for pattern in declared:
        reasons[pattern] = 'declared in eaos.policy.json analysis.exclude'
    if not _include_vendored(target, path):
        for pattern in VENDORED:
            reasons.setdefault(pattern, 'vendored directory name; opt in via analysis.include_vendored=true')
    return reasons
