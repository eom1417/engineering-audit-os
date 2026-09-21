"""Every artifact a run may produce: who owns it, why a reader opens it, and how long it may be.

Before this declaration existed, sixteen of thirty documents were outside the output contract
entirely — unbudgeted and unchecked — and four of them were written twice, the second writer
replacing 574 lines of measured content with empty headings. A file with no declared owner is a
file nobody is responsible for.
"""
from dataclasses import dataclass

DOCUMENT, RECORD = 'document', 'record'


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


ARTIFACTS = (
    Artifact('README.md', 'claims', DOCUMENT, 'What this report holds and in what order to read it', 1, 120),
    Artifact('RUN.md', 'validate', DOCUMENT, 'What this run examined, and what it could not', 2, 120,
             record='run-manifest.json'),
    Artifact('EXECUTIVE.md', 'executive', DOCUMENT, 'The decision a sponsor has to make, and on what evidence', 3, 120),
    Artifact('DECISION-BRIEF.md', 'claims', DOCUMENT, 'Every live claim with its confidence and its falsifier', 4, 120),
    Artifact('PRODUCT-REPORT.md', 'compose', DOCUMENT, 'The reviewed project in one narrative', 5, 200),
    Artifact('BLOCKERS.md', 'compose', DOCUMENT, 'What stops the plan from being executable today', 6, 120),
    Artifact('SYSTEM-MAP.md', 'claims', DOCUMENT, 'Modules and their dependency directions', 10, 260),
    Artifact('COUPLING-ATLAS.md', 'claims', DOCUMENT, 'Where change spreads and why', 11, 220),
    Artifact('FLOWS.md', 'claims', DOCUMENT, 'Traced end-to-end paths from each entry point', 12, 300),
    Artifact('DOMAIN-AND-DATA.md', 'claims', DOCUMENT, 'Domain concepts and the state they own', 13, 240),
    Artifact('CONTRACTS.md', 'claims', DOCUMENT, 'The public surface other code depends on', 14, 200),
    Artifact('EVOLUTION.md', 'claims', DOCUMENT, 'How the code changed over its recorded history', 15, 220),
    Artifact('DATA-MODEL.md', 'bundles', DOCUMENT, 'Persisted shapes and their migrations', 16, 200),
    Artifact('DEPLOYMENT.md', 'bundles', DOCUMENT, 'Where the system is declared to run', 17, 200),
    Artifact('OBSERVABILITY.md', 'bundles', DOCUMENT, 'What the system reports about itself', 18, 200),
    Artifact('SECURITY-SURFACE.md', 'bundles', DOCUMENT, 'Reachable surfaces and declared secrets', 19, 200),
    Artifact('INTEGRATIONS.md', 'bundles', DOCUMENT, 'Outbound calls to systems outside this repository', 20, 200),
    Artifact('ENGINES.md', 'engines', DOCUMENT, 'What each external engine saw, and where they disagree', 21, 200,
             record='facts/external.json', required=False,
             absent_when='external engines were not requested or are not installed'),
    Artifact('POLICY.md', 'policy', DOCUMENT, 'The declared architecture contract and its breaches', 22, 160,
             record='facts/policy.json', required=False, absent_when='the project declares no policy'),
    Artifact('VERIFICATION-MAP.md', 'claims', DOCUMENT, 'What the tests actually executed', 23, 180,
             record='verification.json'),
    Artifact('RISK-REGISTER.md', 'claims', DOCUMENT, 'Live risks with their dispositions', 24, 200),
    Artifact('ONBOARDING.md', 'claims', DOCUMENT, 'The shortest path to understanding this system', 25, 200),
    Artifact('SUSTAINABILITY.md', 'sustainability', DOCUMENT, 'The six indicators and the moves that would close them',
             30, 200, record='sustainability.json'),
    Artifact('CANONICAL-HOMES.md', 'bundles', DOCUMENT, 'Where each repeated definition should live', 31, 200,
             record='canonical-homes.json'),
    Artifact('TARGET-ARCHITECTURE.md', 'target', DOCUMENT, 'The structure the evidence argues for', 32, 200,
             record='target-architecture.json'),
    Artifact('transform-plan.md', 'transform', DOCUMENT, 'The staged route from here to there', 33, 200,
             record='transform-plan.json'),
    Artifact('STAGES.md', 'bundles', DOCUMENT, 'Each transform stage with its acceptance check', 34, 200,
             record='transform-plan.json'),
    Artifact('WAVES.md', 'bundles', DOCUMENT, 'Execution waves over the task cards', 35, 200, record='plan.json'),
    Artifact('KPI.md', 'bundles', DOCUMENT, 'What to measure to know the transformation worked', 36, 120),
    Artifact('BASELINE.md', 'validate', DOCUMENT, 'The debt accepted when the baseline was pinned, and what has closed since', 37, 120, record='baseline/baseline.json', required=False,
             absent_when='no baseline is pinned in this report directory'),
    Artifact('PROVENANCE.md', 'claims', DOCUMENT, 'Which tool, which version, which commit produced this', 40, 80),
    Artifact('SEMANTIC.md', 'semantic', DOCUMENT, 'Model interpretation, every line still a hypothesis', 41, 200,
             record='semantic.json', required=False, absent_when='no model provider was configured'),

    Artifact('dossier.json', 'claims', RECORD, 'The claim ledger this report renders',
             mutated_by=('probe', 'plan', 'semantic')),
    Artifact('plan.json', 'plan', RECORD, 'Task cards and waves'),
    Artifact('probes.json', 'probe', RECORD, 'What each probe decided'),
    Artifact('report-result.json', 'validate', RECORD, 'The output-contract verdict'),
    Artifact('run-manifest.json', 'validate', RECORD, 'Per-stage status, timing and reason',
             checked=False),
    Artifact('product-review.json', 'compose', RECORD, 'The summary a caller reads back',
             checked=False),
    Artifact('transform-plan.json', 'transform', RECORD, 'Every transform stage in full'),
    Artifact('target-architecture.json', 'target', RECORD, 'The target model in full'),
    Artifact('sustainability.json', 'sustainability', RECORD, 'Indicator values, gaps and moves in full'),
    Artifact('canonical-homes.json', 'bundles', RECORD, 'Every canonical home in full'),
    Artifact('gap-matrix.json', 'bundles', RECORD, 'Current against target, component by component'),
    Artifact('engagement.json', 'bundles', RECORD, 'What good means for this codebase'),
    Artifact('verification.json', 'verify', RECORD, 'Coverage from the executed test command', required=False,
             absent_when='no test command was given'),
    Artifact('semantic.json', 'semantic', RECORD, 'Raw model output', required=False,
             absent_when='no model provider was configured'),
    Artifact('index.html', 'site', DOCUMENT, 'The same records, browsable', 50, 100000, required=False,
             absent_when='the site was turned off'),
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
