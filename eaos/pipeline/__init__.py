"""One declared pipeline: what runs, in what order, and what a run may honestly lack."""
from .run import MANIFEST, SkipStage, execute, resume
from .stages import BY_NAME, ORDER, OPTIONAL, REQUIRED, STAGES, Stage, dependents, errors, graph
