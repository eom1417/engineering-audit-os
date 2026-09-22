"""The pipeline, declared as data.

The order used to live inside one function as a sequence of calls, which meant nothing could ask
what the pipeline does, skip a step, resume one, or report what never ran. Here each stage names
what it needs, what it produces, and whether the run may continue without it.
"""
from dataclasses import dataclass, field

REQUIRED, OPTIONAL = 'required', 'optional'


class SkipStage(Exception):
    """Raised by a runner that cannot apply here — no provider, no policy, no engine installed."""



@dataclass(frozen=True)
class Stage:
    name: str
    produces: tuple
    requires: tuple = ()
    necessity: str = REQUIRED
    # Why a run may legitimately lack this stage. An optional stage with no reason is a required
    # stage somebody did not want to pay for.
    absent_when: str = ''
    description: str = ''


STAGES = (
    Stage('facts', produces=('facts/index.json',), description='Deterministic extraction over one snapshot'),
    Stage('engines', produces=('facts/external.json', 'ENGINES.md'), requires=('facts',), necessity=OPTIONAL,
          absent_when='no external engine is installed, or --engines was not asked for',
          description='Pinned external analyzers, normalised into one fact set'),
    Stage('verify', produces=('verification.json',), requires=('facts',), necessity=OPTIONAL,
          absent_when='no test command was given, or execution was not authorised',
          description='Run the test suite in an isolated copy and map real coverage'),
    Stage('policy', produces=('facts/policy.json', 'POLICY.md'), requires=('facts',), necessity=OPTIONAL,
          absent_when='the project declares no eaos.policy.json',
          description='Enforce the declared architecture policy'),
    Stage('claims', produces=('dossier.json', 'DECISION-BRIEF.md', 'README.md'), requires=('facts',),
          description='Facts interpreted into a ledger of falsifiable claims'),
    Stage('probe', produces=('probes.json',), requires=('claims',),
          description='Settle every claim whose truth can be decided mechanically'),
    Stage('load', produces=('load-model.json', 'LOAD-MODEL.md'), requires=('facts', 'claims'),
          description='A cost record per entry point, with a stated projection at 1000x'),
    Stage('semantic', produces=('SEMANTIC.md',), requires=('claims',), necessity=OPTIONAL,
          absent_when='no model provider was configured',
          description='Model interpretation over the facts; every output stays a hypothesis'),
    Stage('sustainability', produces=('SUSTAINABILITY.md', 'sustainability.json'), requires=('claims',),
          description='The six sustainability indicators, measured or declared unmeasured'),
    Stage('transform', produces=('transform-plan.md', 'transform-plan.json'), requires=('sustainability',),
          description='Canonical homes for repeated definitions, and the move that gets there'),
    Stage('plan', produces=('plan.json', 'PLAN/WAVES.md'), requires=('probe',),
          description='Confirmed claims become task cards ordered into waves'),
    Stage('target', produces=('TARGET-ARCHITECTURE.md', 'target-architecture.json'), requires=('plan', 'transform'),
          description='Source inventory and explicitly reviewed target decisions; unknowns remain gaps'),
    Stage('executive', produces=('EXECUTIVE.md',), requires=('sustainability',),
          description='Executive view of the measured indicators and their limits'),
    Stage('compose', produces=('PRODUCT-REPORT.md', 'BLOCKERS.md'), requires=('plan', 'target', 'executive'),
          description='Human artifacts, each inside its declared line budget'),
    Stage('bundles', produces=('bundles/manifest.json', 'CANONICAL-HOMES.md', 'canonical-homes.json',
                              'STAGES.md', 'WAVES.md', 'KPI.md', 'gap-matrix.json', 'DATA-MODEL.md',
                              'DEPLOYMENT.md', 'OBSERVABILITY.md', 'SECURITY-SURFACE.md',
                              'INTEGRATIONS.md'), requires=('compose',),
          description='Package the same report, preserving the engagement contract'),
    Stage('site', produces=('index.html',), requires=('compose',), necessity=OPTIONAL,
          absent_when='--no-site was given',
          description='One browsable page over the same records; adds navigation, never content'),
    Stage('validate', produces=('report-result.json', 'RUN.md'), requires=('compose',),
          description='Write what the run did and did not do, then judge the output contract'),
)

BY_NAME = {stage.name: stage for stage in STAGES}
ORDER = tuple(stage.name for stage in STAGES)


def graph():
    """The declared dependency graph, for anything that needs to reason about the order."""
    return {stage.name: list(stage.requires) for stage in STAGES}


def errors():
    """Structural problems in the declaration itself. An empty list means the pipeline is sane."""
    found, seen, produced = [], set(), {}
    for stage in STAGES:
        if stage.name in seen:
            found.append(f'{stage.name}: declared twice')
        seen.add(stage.name)
        for need in stage.requires:
            if need not in seen:
                found.append(f'{stage.name}: requires {need}, which no earlier stage provides')
        if stage.necessity == OPTIONAL and not stage.absent_when.strip():
            found.append(f'{stage.name}: optional without saying when it may be absent')
        if stage.necessity not in (REQUIRED, OPTIONAL):
            found.append(f'{stage.name}: unknown necessity {stage.necessity!r}')
        if not stage.produces:
            found.append(f'{stage.name}: produces nothing, so nothing can depend on it')
        for artifact in stage.produces:
            if artifact in produced:
                found.append(f'{stage.name}: {artifact} is already produced by {produced[artifact]}')
            produced[artifact] = stage.name
    return sorted(found)


def dependents(name):
    """Every stage that cannot run once this one has failed."""
    blocked, frontier = set(), {name}
    while frontier:
        current = frontier.pop()
        for stage in STAGES:
            if current in stage.requires and stage.name not in blocked:
                blocked.add(stage.name)
                frontier.add(stage.name)
    return sorted(blocked)
