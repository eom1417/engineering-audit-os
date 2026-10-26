"""The guided way in: `eaos start`, `eaos next`, `eaos status`, `eaos doctor`, `eaos clean`.

For a person who built their app with an AI assistant and does not read code. Four rules hold everywhere:

  1. Nothing to write by hand. Everything EAOS keeps for a project lives outside it, in
     ~/.eaos/projects/<name>-<id>/ (or $EAOS_HOME): the report, the run's records, the logs, and state.json,
     which remembers where the person is. The project folder is never written.
  2. Questions are yes/no or a choice, asked only when nothing can be detected. Without a terminal to ask in
     (an AI assistant runs the command), the question is printed with the command that answers it
     (`eaos next --yes`), and nothing happens until then. Every question asked is kept in state.json.
  3. Every command ends with the same box: what happened, where the results are, and the next command to copy.
  4. A failure is shown in plain words with its fix (eaos/data/errors.json); the technical detail goes to a
     log file whose path is shown, never to the screen.

`next` picks the next step by itself from STEPS: each step says when it is done and how to do it. The commands:
guided/commands.py; what they share: person (the words and the box), project (its records), checking, running,
batches, doctor.
"""
# The names other modules call through the package (guided.publish, guided.report_of ...), each kept in one module here.
from ...core.project.places import outputs_root, second_name, workspace  # noqa: F401
from ...core.project.state import load, runtime_of  # noqa: F401
from .batches import choose, close_batch, merge, reconcile, retire_stale_batch  # noqa: F401
from .checking import (agree_to_assistant, check_provider, check_runtime, choose_assistant, later_steps,  # noqa: F401
                       scan, tools_for_check)
from .commands import COMMANDS, STEPS, TERMINAL, USER_COMMANDS, clean, do, main, watch  # noqa: F401
from .doctor import assistant_row, doctor, doctor_rows  # noqa: F401
from .person import (LINE, Declined, NeedsAnswer, ToolsMissing, answered, ask, box, catalog, explain,  # noqa: F401
                     progress_printer, say, show_error)
from .project import (PUBLISHERS, REPORT_PARTS, RESUME, _branch_exists, _git, _saved_note, chosen_assistant,  # noqa: F401
                      language, log_failure, outputs, publish, publish_fixes, report_of, report_stamp, safety_holds,
                      same_code, save, scan_done, set_up, source, tip)
from .running import fix, fix_done, ready, ready_done, safety, safety_done, safety_run  # noqa: F401
