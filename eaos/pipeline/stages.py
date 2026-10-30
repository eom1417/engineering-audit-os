"""The pipeline, declared as data.

The order used to live inside one function as a sequence of calls, which meant nothing could ask
what the pipeline does, skip a step, resume one, or report what never ran. Here each stage names
what it needs, what it produces, and whether the run may continue without it.
"""
from dataclasses import dataclass

from .loops import LOOPS, errors as loop_errors

REQUIRED, OPTIONAL = 'required', 'optional'
# The app running in its isolated copy (one copy, one port, one database), most of the memory (the heavy analyzers),
# and the whole machine (a measure that nothing else may disturb).
RESOURCES = ('app', 'memory', 'machine')
# The app's stages share its database: they hold it in the declared order, so each finds there what it found before.
IN_ORDER = ('app',)


class SkipStage(Exception):
    """Raised by a runner that cannot apply here — no provider, no policy, no engine installed.

    `code` names the reason in a stable word (`no_provider`): the Studio shows the person the text for that code in
    their language (the `reasons` of eaos/data/errors.json), and EAOS's own sentence when the code is unknown."""

    def __init__(self, reason='', code='', lost=None):
        super().__init__(reason)
        self.code = code
        self.lost = lost      # {'resets': …} when the assistant the check was given stopped midway: the check is partial



@dataclass(frozen=True)
class Stage:
    name: str
    produces: tuple
    requires: tuple = ()
    # Stages whose output it reads when they ran: it waits for them, runs again with them (again), and is never held
    # back by their failure.
    reads: tuple = ()
    # Artifacts of an earlier stage it rewrites: every stage built on that one sees them as in the declared order, the
    # ones declared before it unchanged and the ones after it rewritten (waits).
    amends: tuple = ()
    # It reads what every stage before it made (the Studio's whole export, the final target): it waits for them all.
    gathers: bool = False
    # What it holds while it runs, which no other stage holds at the same time (RESOURCES).
    uses: tuple = ()
    # It runs the app in a copy and a database of its own (eaos/live/app/run.py `apart`): it holds no resource, and takes
    # an app's memory.
    apart: bool = False
    necessity: str = REQUIRED
    # Why a run may legitimately lack this stage. An optional stage with no reason is a required
    # stage somebody did not want to pay for.
    absent_when: str = ''
    description: str = ''
    # Done by the person's assistant (docs/AI-IN-THE-PIPELINE.md): the live map marks it, and without one the rules stand.
    ai: bool = False


_DECLARED = (
    Stage('facts', produces=('facts/index.json',), description='Deterministic extraction over one snapshot'),
    Stage('features', produces=('features.json',), requires=('facts',),
          description='Group entry points and data accesses into what the program does for a user'),
    Stage('roles', produces=('roles.json',), requires=('features',), necessity=OPTIONAL,
          absent_when='no assistant was installed or allowed, or its answer named no real line of the code: the app is '
                      'then opened as one user, and the report says its kinds of users are not known',
          description="The kinds of users the app has (an administrator, support, a customer...), each with the code "
                      'that makes it one and its own pages: the app is opened once as each', ai=True),
    Stage('intake', produces=('intake.json',), requires=('features',),
          description='What the owner must protect: answers, or declared defaults, and the quality scenarios'),
    Stage('engines', produces=('facts/external.json',), requires=('facts',), necessity=OPTIONAL, uses=('memory',),
          absent_when='no external engine is installed, or --engines was not asked for',
          description='Pinned external analyzers, normalised into one fact set'),
    Stage('setup', produces=('live/setup.json',), requires=('features',), necessity=OPTIONAL, uses=('app',),
          absent_when='the person did not agree to run the app in an isolated copy, or it could not be started there',
          description='Install and start the app in an isolated copy, with a temporary database and none of the '
                      "person's secrets; the assistant helps when the files alone do not say how"),
    Stage('verify', produces=('verification.json',), requires=('facts',), reads=('setup',), necessity=OPTIONAL, apart=True,
          absent_when='the person did not agree to run the app in an isolated copy, or its run profile names no test '
                      'command; which test imports which file is still written',
          description="The project's own tests, from its run profile, run in the isolated copy with coverage: what they "
                      'reach, what they miss, and whether they pass on the code as it is'),
    Stage('session', produces=('live/sign-in.json',), requires=('setup',), reads=('roles',), necessity=OPTIONAL, uses=('app',),
          absent_when='the app is not running in an isolated copy, the person chose no sign-in, or nobody signed in '
                      'within the wait: the pages behind the sign-in are then seen signed out, and the report says so',
          description="Whether the app's pages need a sign-in (its code, and the pages the setup opened), and the "
                      "sessions every page stage opens them with: the assistant's test users on the running app, one of "
                      'each kind of user, within five minutes, else the person signing in by hand on the sign-in page '
                      'while the stages that open no page go on', ai=True),
    Stage('crawl', produces=('live/crawl.json',), requires=('setup',), reads=('session',), necessity=OPTIONAL, uses=('app',),
          absent_when='the app is not running in an isolated copy, or it serves no page',
          description="Every page of the app found by following its links, the pages its code and files name, and those "
                      'behind its buttons (the browser agent: saved steps replayed, or explored with the assistant); '
                      'Lighthouse on the entry and the first page of each distinct template, ten at most'),
    Stage('lock', produces=('behavior-lock/plan.json',), requires=('features',), reads=('crawl',), necessity=OPTIONAL,
          absent_when='the program has no feature to lock: neither its code nor the crawl of its running copy names a page, '
                      'http route or command',
          description='A spec per feature, in its own tool, describing what the system does today; the pages the crawl '
                      'found stand in when the code names none'),
    Stage('record', produces=('live/lock.json',), requires=('lock', 'setup'), reads=('session',), necessity=OPTIONAL, uses=('app',),
          absent_when='the app is not running in an isolated copy, or the program has no feature to lock',
          description="Every spec of the lock run twice on today's code: its screens and interfaces recorded, the "
                      'safety net every fix is judged by'),
    Stage('journeys', produces=('live/journeys.json',), requires=('record',), reads=('session',), necessity=OPTIONAL, uses=('app',),
          absent_when='the app is not running in an isolated copy, the lock has no page to walk through, or rrweb is not '
                      'installed',
          description="Each feature's pages walked once more, rrweb recording them and Playwright keeping the trace of a "
                      'failure, both capped in size: which pages a user walks and where a journey fails'),
    Stage('screens', produces=('live/screens.json',), requires=('setup',), reads=('session', 'crawl'), necessity=OPTIONAL, uses=('app',),
          absent_when='the app is not running in an isolated copy, or it has no page to open',
          description='Each distinct page, from the code and from the crawl (one per template), in the app\'s own theme at '
                      'phone and desktop width: its picture and its accessibility (axe); the first page also by Lighthouse'),
    Stage('baseline', produces=('live/baseline.json',), requires=('setup', 'intake'), necessity=OPTIONAL, uses=('app', 'machine'),
          absent_when='the app is not running in an isolated copy, or it has no production build that starts',
          description="Today's speed under the intake's load scenarios (k6, p95) on the app's production build"),
    Stage('layers', produces=('layers.json', 'facts/boundaries.json'), requires=('facts',), reads=('engines', 'verify'),
          description="The system as layers: every file in a layer of its reference type, the boundaries between them, what "
                      'ships to the browser, every endpoint and its guard, the data rules read from the migrations, where the '
                      "business rules live, operations and tests; each broken boundary a finding, each doubt a question"),
    # the last page stage: it fills the copy's database, which the lock, the screens and the layers read before
    Stage('keeping', produces=('live/keeping.json',), requires=('setup',), reads=('session', 'crawl', 'screens', 'record', 'journeys', 'layers'),
          necessity=OPTIONAL, uses=('app',),
          absent_when='the app is not running in an isolated copy',
          description="How the data is saved, travels and is kept: the saves the pages send, read again once the copy's own "
                      'database is filled to a real size; how that database stores its data (whole documents and pictures in '
                      'columns, the same values in two tables); the project\'s backup restored into an empty database and '
                      'compared table by table; the files the server wrote; two edits of one record through the API'),
    Stage('layers_trial', produces=('live/api-trial',), requires=('layers', 'setup'), reads=('session',), apart=True,
          amends=('layers.json', 'facts/boundaries.json'), necessity=OPTIONAL,
          absent_when='the person did not choose to try the layers (the `layers` option, its time said before it starts), or '
                      'the app is not running in an isolated copy',
          description="The layers tried: the production build read for keys and source maps, the migrations applied to a "
                      "database of the run's own and tried per table with pgTAP as no one, the owner and another user (and the "
                      "Supabase advisors), the API tried by Schemathesis with two test accounts; each failure a finding with "
                      'its evidence'),
    # after the lock recorded its screens: the simulated users and their seeded history change the copy's data
    Stage('experience', produces=('experience/run.json',), requires=('setup',), reads=('roles', 'session', 'screens', 'record', 'journeys'),
          necessity=OPTIONAL, uses=('app',),
          absent_when='the person did not choose to try the experience (the `experience` path, or its short option beside '
                      'the complete check, its time and cost said before it starts), no assistant was installed or allowed, '
                      'or the app is not running in an isolated copy',
          description="Simulated users try the running app, signed in as each kind of user: alone, personas planned with "
                      'their data, their hand-offs and a support desk, each difficulty met again by a fresh one and judged; '
                      "beside the complete check, one persona doing the app's main task within a step budget. The confirmed "
                      'difficulties become cards, the journeys reached are kept for every later check to replay', ai=True),
    Stage('readiness', produces=('readiness.json',), requires=('intake',), reads=('baseline', 'layers'),
          description='How the program holds up in production and under pressure, as findings with evidence: the external '
                      'dependencies a fault would hit, the routes a security scan would request, a health route, telemetry '
                      "and SLO-able scenarios, and the load baseline against the intake's thresholds"),
    Stage('measure', produces=('measurements.json',), requires=('facts',), reads=('engines', 'verify'),
          description='One row per analysed file: size, complexity, duplication, change and dependency, each with its source'),
    Stage('architecture', produces=('architecture/map.json',), requires=('measure',), necessity=OPTIONAL,
          absent_when='no production file was measured or imports another',
          description="The architecture map from EAOS's own facts: the hotspots (complexity times changes per file) and the "
                      'import clusters with their modularity, which the assistant reads'),
    Stage('policy', produces=('facts/policy.json',), requires=('facts',), necessity=OPTIONAL,
          absent_when='the project declares no eaos.policy.json',
          description='Enforce the declared architecture policy'),
    Stage('rules', produces=('rules.json',), requires=('facts',), necessity=OPTIONAL,
          absent_when='the person stated no rule that holds for this project now',
          description="The person's own rules, each by its machine guard: held, broken and where, or not guarded and why (M16)"),
    Stage('load', produces=('load-model.json',), requires=('facts',), reads=('engines', 'baseline'),
          description='A cost record per entry point, with a stated projection at 1000x'),
    Stage('claims', produces=('dossier.json', 'README.md'), requires=('facts', 'features', 'measure', 'load'), reads=('layers', 'layers_trial', 'experience', 'policy', 'rules'),
          description='Facts interpreted into a ledger of falsifiable claims'),
    Stage('probe', produces=('probes.json',), requires=('claims',), amends=('dossier.json',),
          description='Settle every claim whose truth can be decided mechanically'),
    Stage('sustainability', produces=('sustainability.json',), requires=('claims',),
          description='The six sustainability indicators, measured or declared unmeasured, each against its target'),
    Stage('transform', produces=('transform-plan.json',), requires=('sustainability',),
          description='Canonical homes for repeated definitions, and the move that gets there'),
    Stage('semantic', produces=('semantic.json',), requires=('claims',),
          amends=('dossier.json', 'README.md'), necessity=OPTIONAL,
          absent_when='no assistant was installed or allowed, or its answer could not be used',
          description='Model interpretation over the facts; every output stays a hypothesis', ai=True),
    Stage('plan', produces=('plan.json', 'PLAN/WAVES.md'), requires=('probe',), amends=('dossier.json', 'README.md'),
          description="The candidate cards: every actionable claim becomes a task card; the triage decides which stay"),
    Stage('target', produces=('target-architecture.json', 'target-proposal.json'), requires=('plan',),
          description="The rules' target proposal: today's components with their disposition and the reference's target "
                      'components; the assistant judges it before it is final'),
    Stage('proposals', produces=('proposals.json',), requires=('plan', 'target'), gathers=True, necessity=OPTIONAL,
          absent_when='no assistant was installed or allowed, so nobody reads the proposals before the reports',
          description="The tools' proposals as the Studio draws them (cards with their evidence, system, journeys, "
                      'paths, data, infrastructure, pipeline gaps), which the assistant reads'),
    Stage('triage', produces=('nodes/card_triage/verdicts.json',), requires=('proposals',), necessity=OPTIONAL,
          absent_when='no assistant was installed or allowed, or its verdicts could not be used',
          description='The assistant confirms, doubts or rejects every candidate card on its own evidence, those carrying '
                      'the measurement first, and judges each doubted card again on all its facts; it says why',
          ai=True),
    Stage('visual', produces=('nodes/visual_reviewer/findings.json',), requires=('screens',), necessity=OPTIONAL,
          absent_when='no assistant was installed or allowed, no screen was pictured, or its review could not be used',
          description="The assistant looks at each picture of the app's screens and names what a person would notice, "
                      'each finding with its picture and the region of it', ai=True),
    Stage('cards', produces=('cards.json',), requires=('plan',), reads=('triage', 'visual'), amends=('plan.json', 'dossier.json'),
          description="The assistant's verdicts applied once, before anything ranks, plans or reports: a card the triage "
                      "rejected leaves the plan and the gaps and its claim is refuted, a doubted one waits for a person's "
                      "review and is never fixed automatically; without the triage every card stands as the rules wrote it"),
    Stage('ideal', produces=('ideal/plan.json',), requires=('proposals',), reads=('triage', 'visual'), necessity=OPTIONAL,
          absent_when='no assistant was installed or allowed, or its plan could not be used',
          description="The assistant accepts, modifies or rejects each of the tools' proposals for the target, reading "
                      'the triage and the semantic reading, then reviews it; every element cites its evidence', ai=True),
    Stage('pipeline_gaps', produces=('nodes/pipeline_gap_planner/plan.json',), requires=('proposals',), necessity=OPTIONAL,
          absent_when='no assistant was installed or allowed, the project breaks no pipeline rule, or its plan could not be used',
          description="The assistant decides how each gap of the pipeline rules is closed, then reviews it", ai=True),
    Stage('reconcile', produces=('TARGET-ARCHITECTURE.md',), requires=('target', 'cards'), gathers=True, amends=('target-architecture.json',),
          description="The final target: the assistant's decision where it cites evidence and passes the guards (known "
                      "components, the owner's policy and protected features kept), the rules' elsewhere; every "
                      'component says who decided it and the gap matrix is drawn from it'),
    Stage('order', produces=('nodes/plan_orderer/order.json',), requires=('cards',), reads=('ideal', 'pipeline_gaps'), necessity=OPTIONAL,
          absent_when='no assistant was installed or allowed, or its order could not be used',
          description="The assistant orders and groups the confirmed cards into steps, reading the triage, the ideal and "
                      'the pipeline steps, then reviews the order; every prerequisite is kept', ai=True),
    Stage('steps', produces=('PLAN/STEPS.md',), requires=('cards',), reads=('order',), amends=('plan.json',),
          description="The plan's order: the assistant's steps when they keep every prerequisite, else the rules' waves"),
    Stage('reports', produces=('CURRENT-STATE.md', 'TARGET-STATE.md', 'GAP-AND-STRATEGY.md', 'EXECUTION-PLAN.md', 'START-HERE.md'),
          requires=('reconcile', 'steps'),
          description='The four reports a client reads first, written from the final target and plan; every other '
                      'document is an appendix to them'),
    Stage('translate', produces=('i18n/ar/START-HERE.md', 'i18n/en/START-HERE.md'), requires=('reports',), necessity=OPTIONAL,
          absent_when='no assistant was installed or allowed: each document stays as it was written',
          description="Every document whole in Arabic and in English (eaos/core/language/bilingual.py): only the pieces in the other "
                      'language, as templates without their numbers and paths, by the smallest model without thinking, '
                      'once: EAOS ships its own sentences translated, and the rest is kept for the next check', ai=True),
)
# The declared order is the loops' (eaos/pipeline/loops.py): reordering the check is a change of that table.
_POSITION = {name: index for index, name in enumerate(name for loop in LOOPS for name in loop.stages)}
STAGES = tuple(sorted(_DECLARED, key=lambda stage: _POSITION.get(stage.name, len(_POSITION))))

BY_NAME = {stage.name: stage for stage in STAGES}
ORDER = tuple(stage.name for stage in STAGES)
# The five parts a person follows a check by (the Studio's board), each stage in one; within a part, the declared order.
PHASES = {phase: tuple(sorted(names, key=ORDER.index)) for phase, names in {
          'read': ('facts', 'features', 'roles', 'intake', 'measure', 'architecture', 'policy', 'rules', 'load'),
          'tools': ('engines', 'layers', 'layers_trial', 'claims', 'probe', 'sustainability', 'transform'),
          'app': ('setup', 'verify', 'session', 'crawl', 'lock', 'record', 'journeys', 'screens', 'baseline', 'keeping', 'experience', 'readiness'),
          'assistant': ('semantic', 'triage', 'visual', 'ideal', 'pipeline_gaps'),
          'plan': ('plan', 'target', 'proposals', 'cards', 'reconcile', 'order', 'steps', 'reports', 'translate')}.items()}
PHASE = {name: phase for phase, names in PHASES.items() for name in names}


def graph():
    """The declared dependency graph, for anything that needs to reason about the order."""
    return {stage.name: list(stage.requires) for stage in STAGES}


def errors():
    """Structural problems in the declaration itself. An empty list means the pipeline is sane."""
    found, seen, produced = [], set(), {}
    for stage in STAGES:
        if stage.name in seen: found.append(f'{stage.name}: declared twice')
        seen.add(stage.name)
        found += [f'{stage.name}: requires {need}, which no earlier stage provides' for need in stage.requires + stage.reads if need not in seen]
        found += [f'{stage.name}: {artifact} is already produced by {produced[artifact]}' for artifact in stage.produces if artifact in produced]
        found += [f'{stage.name}: amends {artifact}, which no earlier stage produces' for artifact in stage.amends if artifact not in produced]
        produced.update(dict.fromkeys(stage.produces, stage.name))
        found += _stage_errors(stage)
    return sorted(found + loop_errors(seen))


def _stage_errors(stage):
    """What is wrong with one stage's declaration on its own: its necessity, and what it produces."""
    found = []
    if stage.necessity == OPTIONAL and not stage.absent_when.strip():
        found.append(f'{stage.name}: optional without saying when it may be absent')
    if stage.necessity not in (REQUIRED, OPTIONAL):
        found.append(f'{stage.name}: unknown necessity {stage.necessity!r}')
    if not stage.produces:
        found.append(f'{stage.name}: produces nothing, so nothing can depend on it')
    return found + [f'{stage.name}: uses {held}, which is not one of {RESOURCES}' for held in stage.uses if held not in RESOURCES]


def _built_on():
    """{stage: every stage it is built on}: what it requires and reads, and what those are built on."""
    under = {}
    for stage in STAGES:
        under[stage.name] = {need for name in stage.requires + stage.reads for need in (name, *under.get(name, ()))}
    return under


def _waits():
    """{stage: the stages it waits for}: what it requires and reads, every earlier stage when it gathers, the stage
    before it holding a resource held in order (IN_ORDER), and for an amended artifact the declared order between the
    stage that amends it and every stage built on its maker. Each edge
    points to an earlier stage, so one stage at a time in the declared order meets them all, and the graph has no
    cycle."""
    under, maker = _built_on(), {artifact: stage.name for stage in STAGES for artifact in stage.produces}
    waits = {stage.name: set(stage.requires + stage.reads) | (set(ORDER[:ORDER.index(stage.name)]) if stage.gathers else set())
             for stage in STAGES}
    _hold_in_order(waits)
    for stage in STAGES:
        for artifact in stage.amends: _keep_order(waits, stage.name, maker[artifact], under)
    return {name: frozenset(found) for name, found in waits.items()}


def _hold_in_order(waits):
    """Each stage holding a resource held in order (IN_ORDER) waits for the stage holding it before it."""
    for resource in IN_ORDER:
        holders = [stage.name for stage in STAGES if resource in stage.uses]
        for before, name in zip(holders, holders[1:]): waits[name].add(before)


def _keep_order(waits, amending, maker, under):
    """The stages built on `maker` see what `amending` rewrites as in the declared order: it waits for those declared
    before it, and those after it wait for it."""
    for name in ORDER:
        if name == amending or not (name == maker or maker in under[name]): continue
        if ORDER.index(name) < ORDER.index(amending): waits[amending].add(name)
        else: waits[name].add(amending)


def dependents(name, reading=False):
    """Every stage that cannot run once this one has failed; `reading`: also those that wait for what it makes (WAITS)."""
    blocked, frontier = set(), {name}
    while frontier:
        current = frontier.pop()
        for stage in STAGES:
            if current in (WAITS[stage.name] if reading else stage.requires) and stage.name not in blocked:
                blocked.add(stage.name)
                frontier.add(stage.name)
    return sorted(blocked)


WAITS = _waits()
