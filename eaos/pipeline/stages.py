"""The pipeline, declared as data.

The order used to live inside one function as a sequence of calls, which meant nothing could ask
what the pipeline does, skip a step, resume one, or report what never ran. Here each stage names
what it needs, what it produces, and whether the run may continue without it.
"""
from dataclasses import dataclass

REQUIRED, OPTIONAL = 'required', 'optional'


class SkipStage(Exception):
    """Raised by a runner that cannot apply here — no provider, no policy, no engine installed.

    `code` names the reason in a stable word (`no_provider`): the Studio shows the person the text for that code in
    their language (the `reasons` of eaos/data/errors.json), and EAOS's own sentence when the code is unknown."""

    def __init__(self, reason='', code=''):
        super().__init__(reason)
        self.code = code



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
    # Done by the person's assistant (docs/AI-IN-THE-PIPELINE.md): the live map marks it, and without one the rules stand.
    ai: bool = False


STAGES = (
    Stage('facts', produces=('facts/index.json',), description='Deterministic extraction over one snapshot'),
    Stage('features', produces=('features.json', 'FEATURES.md'), requires=('facts',),
          description='Group entry points and data accesses into what the program does for a user'),
    Stage('lock', produces=('behavior-lock/plan.json',), requires=('features',), necessity=OPTIONAL,
          absent_when='the program has no feature to lock',
          description='A spec per feature, in its own tool, describing what the system does today'),
    Stage('intake', produces=('intake.json',), requires=('features',),
          description='What the owner must protect: answers, or declared defaults, and the quality scenarios'),
    Stage('engines', produces=('facts/external.json', 'ENGINES.md'), requires=('facts',), necessity=OPTIONAL,
          absent_when='no external engine is installed, or --engines was not asked for',
          description='Pinned external analyzers, normalised into one fact set'),
    Stage('setup', produces=('live/setup.json',), requires=('features',), necessity=OPTIONAL,
          absent_when='the person did not agree to run the app in an isolated copy, or it could not be started there',
          description='Install and start the app in an isolated copy, with a temporary database and none of the '
                      "person's secrets; the assistant helps when the files alone do not say how"),
    Stage('verify', produces=('verification.json',), requires=('facts',), necessity=OPTIONAL,
          absent_when='no test command was given, or execution was not authorised',
          description='Run the test suite in an isolated copy and map real coverage'),
    Stage('record', produces=('live/lock.json',), requires=('lock', 'setup'), necessity=OPTIONAL,
          absent_when='the app is not running in an isolated copy, or the program has no feature to lock',
          description="Every spec of the lock run twice on today's code: its screens and interfaces recorded, the "
                      'safety net every fix is judged by'),
    Stage('journeys', produces=('live/journeys.json',), requires=('record',), necessity=OPTIONAL,
          absent_when='the app is not running in an isolated copy, or the lock has no page to walk through',
          description="Each feature's pages walked once more with Playwright's trace on and rrweb recording them: a "
                      'replayable journey per feature'),
    Stage('crawl', produces=('live/crawl.json',), requires=('setup',), necessity=OPTIONAL,
          absent_when='the app is not running in an isolated copy, or it serves no page',
          description="Every page of the app found by following its links (Unlighthouse), each measured by Lighthouse"),
    Stage('screens', produces=('live/screens.json',), requires=('setup',), necessity=OPTIONAL,
          absent_when='the app is not running in an isolated copy, or it has no page to open',
          description='Each page, from the code and from the crawl, in its light and dark states at phone and desktop '
                      'width: its picture and its accessibility (axe); the first page also by Lighthouse'),
    Stage('baseline', produces=('live/baseline.json',), requires=('setup', 'intake'), necessity=OPTIONAL,
          absent_when='the app is not running in an isolated copy, or it has no production build that starts',
          description="Today's speed under the intake's load scenarios (k6, p95) on the app's production build"),
    Stage('measure', produces=('measurements.json', 'MEASUREMENTS.md'), requires=('facts',),
          description='One row per analysed file: size, complexity, duplication, change and dependency, each with its source'),
    Stage('architecture', produces=('architecture/map.json',), requires=('measure',), necessity=OPTIONAL,
          absent_when='neither CodeCharta nor Emerge is installed, or neither reads this project',
          description="The architecture map: the code as a city (CodeCharta: area the size, height the complexity, colour "
                      'the changes) and its dependency clusters (Emerge), beside the dependency-cruiser and GitNexus findings'),
    Stage('policy', produces=('facts/policy.json', 'POLICY.md'), requires=('facts',), necessity=OPTIONAL,
          absent_when='the project declares no eaos.policy.json',
          description='Enforce the declared architecture policy'),
    Stage('load', produces=('load-model.json', 'LOAD-MODEL.md'), requires=('facts',),
          description='A cost record per entry point, with a stated projection at 1000x'),
    Stage('claims', produces=('dossier.json', 'DECISION-BRIEF.md', 'README.md'), requires=('facts', 'load'),
          description='Facts interpreted into a ledger of falsifiable claims'),
    Stage('probe', produces=('probes.json',), requires=('claims',),
          description='Settle every claim whose truth can be decided mechanically'),
    Stage('semantic', produces=('SEMANTIC.md',), requires=('claims',), necessity=OPTIONAL,
          absent_when='no assistant was installed or allowed, or its answer could not be used',
          description='Model interpretation over the facts; every output stays a hypothesis', ai=True),
    Stage('sustainability', produces=('SUSTAINABILITY.md', 'sustainability.json'), requires=('claims',),
          description='The six sustainability indicators, measured or declared unmeasured'),
    Stage('transform', produces=('transform-plan.md', 'transform-plan.json'), requires=('sustainability',),
          description='Canonical homes for repeated definitions, and the move that gets there'),
    Stage('plan', produces=('plan.json', 'PLAN/WAVES.md'), requires=('probe',),
          description="The candidate cards: every actionable claim becomes a task card; the triage decides which stay"),
    Stage('target', produces=('target-architecture.json', 'target-proposal.json'), requires=('plan', 'transform'),
          description="The rules' target proposal: today's components with their disposition and the reference's target "
                      'components; the assistant judges it before it is final'),
    Stage('proposals', produces=('proposals.json',), requires=('plan', 'target'), necessity=OPTIONAL,
          absent_when='no assistant was installed or allowed, so nobody reads the proposals before the reports',
          description="The tools' proposals as the Studio draws them (cards with their evidence, system, journeys, "
                      'paths, data, infrastructure, pipeline gaps), which the assistant reads'),
    Stage('triage', produces=('nodes/card_triage/verdicts.json',), requires=('proposals',), necessity=OPTIONAL,
          absent_when='no assistant was installed or allowed, or its verdicts could not be used',
          description='The assistant confirms, doubts or rejects every candidate card on its own evidence, and says why',
          ai=True),
    Stage('visual', produces=('nodes/visual_reviewer/findings.json',), requires=('screens',), necessity=OPTIONAL,
          absent_when='no assistant was installed or allowed, no screen was pictured, or its review could not be used',
          description="The assistant looks at each picture of the app's screens and names what a person would notice, "
                      'each finding with its picture and the region of it', ai=True),
    Stage('cards', produces=('cards.json',), requires=('plan',),
          description="The plan keeps the confirmed cards: a card the triage rejected leaves the plan and the gaps, a "
                      "doubted one is marked; without the triage every card stands as the rules wrote it"),
    Stage('ideal', produces=('ideal/plan.json',), requires=('proposals',), necessity=OPTIONAL,
          absent_when='no assistant was installed or allowed, or its plan could not be used',
          description="The assistant accepts, modifies or rejects each of the tools' proposals for the target, reading "
                      'the triage and the semantic reading, then reviews it; every element cites its evidence', ai=True),
    Stage('pipeline_gaps', produces=('nodes/pipeline_gap_planner/plan.json',), requires=('proposals',), necessity=OPTIONAL,
          absent_when='no assistant was installed or allowed, the project breaks no pipeline rule, or its plan could not be used',
          description="The assistant decides how each gap of the pipeline rules is closed, then reviews it", ai=True),
    Stage('reconcile', produces=('TARGET-ARCHITECTURE.md',), requires=('target', 'cards'),
          description="The final target: the assistant's decision where it cites evidence and passes the guards (known "
                      "components, the owner's policy and protected features kept), the rules' elsewhere; every "
                      'component says who decided it and the gap matrix is drawn from it'),
    Stage('order', produces=('nodes/plan_orderer/order.json',), requires=('cards',), necessity=OPTIONAL,
          absent_when='no assistant was installed or allowed, or its order could not be used',
          description="The assistant orders and groups the confirmed cards into steps, reading the triage, the ideal and "
                      'the pipeline steps, then reviews the order; every prerequisite is kept', ai=True),
    Stage('steps', produces=('PLAN/STEPS.md',), requires=('cards',),
          description="The plan's order: the assistant's steps when they keep every prerequisite, else the rules' waves"),
    Stage('execution_guide', produces=('EXECUTION-GUIDE.md',), requires=('steps', 'transform', 'load'),
          description='Literal, ordered execution instructions for every task card'),
    Stage('reports', produces=('CURRENT-STATE.md', 'TARGET-STATE.md', 'GAP-AND-STRATEGY.md', 'EXECUTION-PLAN.md', 'reports.json'),
          requires=('reconcile', 'steps'),
          description='The four reports a client reads first, written from the final target and plan; every other '
                      'document is an appendix to them'),
    Stage('quality', produces=('report-quality.json',), requires=('reports',), necessity=OPTIONAL,
          absent_when='neither Vale nor markdownlint-cli2 is installed',
          description='The four reports judged by Vale (the EAOS style) and markdownlint-cli2 (their structure)'),
    Stage('pdf', produces=('EXECUTIVE.pdf',), requires=('reports',), necessity=OPTIONAL,
          absent_when='Typst, or a font for the report language, is not installed',
          description='The one-page executive summary, typeset by Typst from the report\'s own records'),
    Stage('executive', produces=('EXECUTIVE.md',), requires=('reconcile', 'transform'),
          description='Executive view of the measured indicators and their limits'),
    Stage('compose', produces=('PRODUCT-REPORT.md', 'BLOCKERS.md', 'START-HERE.md', 'human/index.html'),
          requires=('reconcile', 'steps', 'executive'),
          description='Human artifacts, each inside its declared line budget'),
    Stage('bundles', produces=('bundles/manifest.json', 'CANONICAL-HOMES.md', 'canonical-homes.json',
                              'STAGES.md', 'WAVES.md', 'KPI.md', 'gap-matrix.json', 'DATA-MODEL.md',
                              'DEPLOYMENT.md', 'OBSERVABILITY.md', 'SECURITY-SURFACE.md',
                              'INTEGRATIONS.md'), requires=('compose',),
          description='Package the same report, preserving the engagement contract'),
    Stage('emit', produces=('handover/README.md', 'handover/validation.json'), requires=('compose',), necessity=OPTIONAL,
          absent_when='no emitter applies',
          description='Files in other tools\' own formats, each judged by its own tool'),
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
