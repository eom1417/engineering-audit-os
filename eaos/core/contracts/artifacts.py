"""Every artifact a run may produce: who owns it, why a reader opens it, and how long it may be.

Before this declaration existed, sixteen of thirty documents were outside the output contract
entirely — unbudgeted and unchecked — and four of them were written twice, the second writer
replacing 574 lines of measured content with empty headings. A file with no declared owner is a
file nobody is responsible for.
"""
from dataclasses import dataclass

DOCUMENT, RECORD = 'document', 'record'
FOUR = 'every number it states names its source in the text; a record of them had no reader (0.0.73)'


@dataclass(frozen=True)
class Artifact:
    name: str
    owner: str                  # the pipeline stage responsible for writing it
    kind: str                   # document (a human reads it) or record (a machine reads it)
    purpose: str
    order: int = 99             # reading order in the generated index
    budget_lines: int = 200     # documents only; a record has no length budget
    record: str = ''            # the machine-readable twin that holds the full detail
    checked: bool = True        # False when it is written after the contract runs
    mutated_by: tuple = ()      # stages that legitimately update it after its owner created it
    required: bool = True
    absent_when: str = ''
    record_absent_because: str = ''   # a document with no machine twin must say why, not stay silent


ARTIFACTS = (
    Artifact('features.json', 'features', RECORD, 'Each feature tied to the surfaces that expose it and the data it touches', 7, 200,
             mutated_by=('target',)),
    Artifact('START-HERE.md', 'reports', DOCUMENT, 'The first page in plain words: what was found, what EAOS fixes alone', 1, 200,
             record='plan.json'),
    Artifact('CURRENT-STATE.md', 'reports', DOCUMENT, 'What the program is today: features, data, measured risk', 2, 200, record_absent_because=FOUR),
    Artifact('TARGET-STATE.md', 'reports', DOCUMENT, 'The same features on the reference type, with its infrastructure', 2, 200, record_absent_because=FOUR),
    Artifact('GAP-AND-STRATEGY.md', 'reports', DOCUMENT, 'The distance component by component, and the order to close it', 2, 200, record_absent_because=FOUR),
    Artifact('EXECUTION-PLAN.md', 'reports', DOCUMENT, 'Milestones, sections and the first cards a team starts with', 2, 200, record_absent_because=FOUR),
    Artifact('README.md', 'claims', DOCUMENT, 'What this report holds and in what order to read it', 1, 120,
             record='dossier.json'),
    Artifact('debt-register.json', 'claims', RECORD, 'Every debt item: category, severity, witnesses, files, hotspot, recommendation',
             mutated_by=('plan',)),
    Artifact('TARGET-ARCHITECTURE.md', 'reconcile', DOCUMENT, 'The structure the evidence argues for, and who decided each part', 32, 200,
             record='target-architecture.json'),
    Artifact('load-model.json', 'load', RECORD, 'Per-entry-point cost record and 1000x projection, ranked'),
    Artifact('dossier.json', 'claims', RECORD, 'The claim ledger this report renders',
             mutated_by=('probe', 'plan', 'semantic', 'cards')),
    Artifact('plan.json', 'plan', RECORD, 'Task cards, their milestones, sections, waves and order'),
    Artifact('proposals.json', 'proposals', RECORD, "Which of the Studio's records of the proposals were written for the assistant",
             required=False, absent_when='no assistant was installed or allowed, so nobody reads the proposals before the reports'),
    Artifact('roles.json', 'roles', RECORD, 'The kinds of users of the app, each with the code that makes it one and its own pages',
             required=False, absent_when='no assistant was installed or allowed, or its answer named no real line of the code'),
    Artifact('live/setup.json', 'setup', RECORD, 'How the app was started in an isolated copy, or why it was not',
             required=False, absent_when='the person did not agree to run the app'),
    Artifact('live/lock.json', 'record', RECORD, "Every spec of the lock run on today's code, passed or not, and why",
             required=False, absent_when='the app is not running in an isolated copy, or the program has no feature to lock'),
    Artifact('live/crawl.json', 'crawl', RECORD, 'Every page found by following the app\'s links, with its Lighthouse scores',
             required=False, absent_when='the app is not running in an isolated copy, or it serves no page'),
    Artifact('live/screens.json', 'screens', RECORD, 'Each page at phone and desktop width: its picture, accessibility and speed',
             required=False, absent_when='the app is not running in an isolated copy, or it has no page to open'),
    Artifact('live/keeping.json', 'keeping', RECORD, "How the data is saved and kept on the copy: the saves the pages send, the database filled, read and restored, the files the server wrote, two edits of one record",
             required=False, absent_when='the app is not running in an isolated copy'),
    Artifact('rules.json', 'rules', RECORD, "The person's own rules that held for this check, each by its guard: held, broken and where, or not guarded and why",
             required=False, absent_when='the person stated no rule that holds for this project now'),
    Artifact('live/baseline.json', 'baseline', RECORD, "Today's speed under the intake's load scenarios (p95) on the production build",
             required=False, absent_when='the app has no production build that starts in an isolated copy'),
    Artifact('cards.json', 'cards', RECORD, 'Which cards the plan kept, set aside or marked doubtful, and who decided'),
    Artifact('i18n/ar/START-HERE.md', 'translate', RECORD, 'Every document of the report whole in Arabic, under i18n/ar/ (eaos/core/language/bilingual.py)',
             required=False, absent_when='no assistant was installed or allowed: each document stays as it was written'),
    Artifact('i18n/en/START-HERE.md', 'translate', RECORD, 'Every document of the report whole in English, under i18n/en/ (eaos/core/language/bilingual.py)',
             required=False, absent_when='no assistant was installed or allowed: each document stays as it was written'),
    Artifact('PLAN/STEPS.md', 'steps', DOCUMENT, "The plan's order: the assistant's steps with why, or the rules' waves", 35, 200,
             record='plan.json'),
    Artifact('probes.json', 'probe', RECORD, 'What each probe decided'),
    Artifact('report-result.json', 'claims', RECORD, 'The output-contract verdict'),
    Artifact('run-manifest.json', 'claims', RECORD, 'Per-stage status, timing and reason',
             checked=False),
    Artifact('facts/external.json', 'engines', RECORD, 'Every external engine finding, normalised',
             required=False, absent_when='no engine was requested, or none is installed'),
    Artifact('facts/policy.json', 'policy', RECORD, 'Every architecture-policy violation in full',
             required=False, absent_when='the project declares no architecture policy'),
    Artifact('logic-flaws.json', 'claims', RECORD, 'The logic-flaw hunt (`eaos logic-flaws`, an optional deep check after a check): '
             'at most 12 flaws, each grounded on a line and read twice, the candidates set aside and why, the code it read; '
             'replaced by the next hunt, read by the claims', required=False, checked=False,
             absent_when='the person did not ask for the logic-flaw hunt'),
    Artifact('facts/logic_flaws.json', 'claims', RECORD, "The logic-flaw hunt's flaws as facts, the claims' input; replaced by the next hunt",
             required=False, checked=False, absent_when='the person did not ask for the logic-flaw hunt'),
    Artifact('target-architecture.json', 'target', RECORD, 'The final target model in full, with who decided each component',
             mutated_by=('reconcile',)),
    Artifact('target-proposal.json', 'target', RECORD, "The rules' target proposal, as it was before the assistant judged it"),
    Artifact('semantic.json', 'semantic', RECORD, 'Raw model output', required=False,
             absent_when='no model provider was configured'),
    Artifact('nodes/card_triage/verdicts.json', 'triage', RECORD, "Every open card confirmed, doubted or rejected by the person's assistant, with why and its evidence",
             required=False, absent_when='no assistant was installed or allowed, or its verdicts could not be used'),
    Artifact('ideal/plan.json', 'ideal', RECORD, "The ideal planned by the person's assistant on top of the rules, every element with its evidence",
             required=False, absent_when='no assistant was installed or allowed, or its plan could not be used'),
    Artifact('nodes/visual_reviewer/findings.json', 'visual', RECORD, "What the person's assistant saw on each picture of the app's screens, with the region",
             required=False, absent_when='no assistant was installed or allowed, or no screen was pictured'),
    Artifact('nodes/pipeline_gap_planner/plan.json', 'pipeline_gaps', RECORD, "How the person's assistant closes each gap of the pipeline rules",
             required=False, absent_when='no assistant was installed or allowed, or the project breaks no pipeline rule'),
    Artifact('nodes/plan_orderer/order.json', 'order', RECORD, "The order of the plan's cards proposed by the person's assistant, every prerequisite kept",
             required=False, absent_when='no assistant was installed or allowed, or its order could not be used'),
    Artifact('measurements.json', 'measure', RECORD, 'Every analysed file with its measurements, each field naming its source'),
    Artifact('behavior-lock/plan.json', 'lock', RECORD, 'The spec of every feature, its tool and the surfaces it locks',
             required=False, absent_when='the program has no feature to lock'),
    Artifact('intake.json', 'intake', RECORD, 'What the owner must protect: every question answered or on a declared default, and the quality scenarios'),
    Artifact('sustainability.json', 'sustainability', RECORD, 'Indicator values, targets, gaps and moves in full'),
    Artifact('transform-plan.json', 'transform', RECORD, 'Every transform stage in full'),
    Artifact('verification.json', 'verify', RECORD, "What the project's own tests reached when they ran, or which test imports which file",
             required=False, absent_when='the person did not agree to run the app, or its run profile names no test command'),
    Artifact('live/sign-in.json', 'session', RECORD, "Whether the app's pages need a sign-in, its evidence, and how they were opened; "
             'never the session itself', required=False,
             absent_when='the app is not running in an isolated copy, the person chose no sign-in, or nobody signed in within the wait'),
    Artifact('live/journeys.json', 'journeys', RECORD, "Each feature's pages walked, with where a journey fails; its capped rrweb recordings "
             'and failure traces under live/journeys/', required=False,
             absent_when='the app is not running in an isolated copy, or the lock has no page'),
    Artifact('readiness.json', 'readiness', RECORD, 'Resilience, security, observability and speed under load, as findings with evidence'),
    Artifact('layers.json', 'layers', RECORD, 'The system as layers: every file in its layer and side, the endpoints and their guards, the '
             'tables, operations and tests, and every broken boundary with its fix', mutated_by=('layers_trial',)),
    Artifact('live/api-trial', 'layers_trial', RECORD, "The OpenAPI derived for the API trial when the project has none; "
             "Schemathesis' report and the accounts' sessions are removed once read", required=False,
             absent_when='the person did not choose to try the layers, or the app is not running in an isolated copy'),
    Artifact('experience/run.json', 'experience', RECORD, "The simulated users' run: each goal's ending, the hand-offs' events, "
             'the time and calls spent; the journeys, pictures and judging beside it under experience/', required=False, checked=False,
             absent_when='the person did not choose to try the experience, no assistant was allowed, or the app did not run'),
    Artifact('EXPERIENCE.md', 'experience', DOCUMENT, "The users' story: who tried the app, what each reached, the difficulties "
             'confirmed with their steps and pictures, the replays', 9, 400, record='experience/story.json', required=False,
             checked=False, absent_when='the person did not choose to try the experience'),
    Artifact('experience/story.json', 'experience', RECORD, "The experience report's data, EXPERIENCE.md's record", required=False,
             checked=False, absent_when='the person did not choose to try the experience'),
    Artifact('architecture/map.json', 'architecture', RECORD, 'The hotspots and the import clusters of the code, from its facts',
             required=False, absent_when='no production file was measured or imports another'),

)

BY_NAME = {artifact.name: artifact for artifact in ARTIFACTS}
DOCUMENTS = tuple(artifact for artifact in ARTIFACTS if artifact.kind == DOCUMENT)
BUDGETS = {artifact.name: artifact.budget_lines for artifact in DOCUMENTS}


def owner(name):
    artifact = BY_NAME.get(name)
    return artifact.owner if artifact else None


def reading_order():
    return sorted(DOCUMENTS, key=lambda artifact: (artifact.order, artifact.name))


def errors():
    """Problems in the declaration itself: two owners for one name, or a budget on a record."""
    found, seen = [], {}
    for artifact in ARTIFACTS:
        if artifact.name in seen:
            found.append(f'{artifact.name}: declared twice, by {seen[artifact.name]} and {artifact.owner}')
        seen[artifact.name] = artifact.owner
        if artifact.kind not in (DOCUMENT, RECORD):
            found.append(f'{artifact.name}: unknown kind {artifact.kind!r}')
        if not artifact.required and not artifact.absent_when.strip():
            found.append(f'{artifact.name}: optional without saying when it may be absent')
        if not artifact.purpose.strip():
            found.append(f'{artifact.name}: no stated purpose, so no reader knows why to open it')
    return sorted(found)
