"""One shape for every external analysis engine, so nothing above this layer knows a tool's name.

An engine tells us what it found. It never tells us what is true: we did not implement its rules
and cannot vouch for what they decide, so every external finding enters as heuristic evidence and
carries the confidence the engine claimed as data, not as authority.
"""
from dataclasses import dataclass, field
from hashlib import sha1

HEURISTIC = 'heuristic'
OBSERVED, UNAVAILABLE, ERROR, SCHEMA_MISMATCH = 'observed', 'unavailable', 'error', 'schema_mismatch'

# The vocabulary every engine is normalised into. Anything an engine reports outside it is dropped
# and counted, so an unmapped rule shows up as reduced coverage instead of silently disappearing.
KINDS = ('cycle', 'coupling', 'complexity', 'duplication', 'dead_code', 'dataflow', 'surface',
         'literal_duplication', 'test_quality', 'naming', 'boundary')


@dataclass(frozen=True)
class Capability:
    """What one engine rule produces, in our vocabulary."""
    kind: str
    rule: str
    method: str = HEURISTIC


@dataclass
class Report:
    engine: str
    version: str | None
    pinned_version: str
    status: str
    seconds: float = 0.0
    reason: str = ''
    findings: list = field(default_factory=list)
    coverage: dict = field(default_factory=dict)
    provenance: dict = field(default_factory=dict)
    raw: str | None = None
    unmapped: dict = field(default_factory=dict)
    # Which kinds this engine actually evaluated, and how completely. An engine that looked for
    # cycles and found none is evidence of absence; one that never looked is not; one that looked
    # partially is weaker counter-evidence than one that looked fully. All three must read apart.
    evaluated: dict = field(default_factory=dict)

    def as_dict(self):
        return {'engine': self.engine, 'version': self.version, 'pinned_version': self.pinned_version,
                'status': self.status, 'seconds': round(self.seconds, 3), 'reason': self.reason,
                'findings': self.findings, 'coverage': self.coverage, 'provenance': self.provenance,
                'raw': self.raw, 'unmapped_rules': self.unmapped, 'evaluated_kinds': dict(sorted(self.evaluated.items())),
                'version_matches_pin': self.version == self.pinned_version}


def subject(kind, key, path=None, line=None):
    return {'kind': kind, 'key': key, 'path': path, 'line': line}


def measurement(name, value, threshold=None, unit=None):
    return {'name': name, 'value': value, 'threshold': threshold, 'unit': unit}


def finding(engine, version, rule, kind, subj, message, measurements=(), engine_confidence=None,
            method=HEURISTIC, raw_ref=None, sites=()):
    """One normalised finding. Its id is content-derived, so two runs of the same engine agree.

    A finding about several places carries all of them in `sites`; `subject` is only its anchor.
    Anchoring a five-file duplicate at one file would hide four of the five from correlation.
    """
    if kind not in KINDS:
        raise ValueError(f'{engine}: unknown finding kind {kind!r}')
    identity = '|'.join([engine, rule, str(subj.get('key')), str(subj.get('path')), message])
    return {'id': 'ENG-' + sha1(identity.encode('utf-8')).hexdigest()[:12],
            'engine': engine, 'engine_version': version, 'rule': rule, 'method': method, 'kind': kind,
            'subject': subj, 'message': message, 'measurements': list(measurements),
            'sites': sorted({(site.get('path'), site.get('line')) for site in sites} or
                            {(subj.get('path'), subj.get('line'))},
                            key=lambda spot: (str(spot[0]), spot[1] if spot[1] is not None else -1)),
            'engine_confidence': engine_confidence, 'raw_ref': raw_ref}
