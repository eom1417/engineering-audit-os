# Progress fixtures

Recorded material for the progress contract (eaos/progress/, tests/test_progress_contract.py).

- `<name>.jsonl`: a real check's `run-progress.jsonl`, recorded by `tools/progress_golden.py record` from a check of a
  fresh copy of the corpus project RendaPerene with this repository's EAOS (host, process numbers and folders replaced
  by fixed placeholders, nothing else changed). `<name>.fold.json` is the fold of it (`eaos/progress/fold.py`), written
  by `tools/progress_golden.py expect`; the Python fold must keep producing it, and the Studio's TypeScript fold must
  produce the same JSON from the same lines.
  - `complete`: the check ran to its end.
  - `stopped`: Ctrl-C (SIGINT to the process group) while `engines` ran: the run says STOPPED and every stage ends.
  - `killed`: `kill -9` of the run while `engines` ran: the file stops mid-run with no end; a reader judges it
    `interrupted` or `stalled` (eaos/progress/liveness.py).
- `ps/linux.txt`: `ps -A -o pid=,ppid=,etime=,comm=` recorded on the Linux development container while a real check
  ran (procps; `comm` is the short name, at most 15 characters; it holds the check's `eaos → pysemgrep →
  semgrep-core` tree).
- `ps/macos.txt`: NOT recorded on a Mac (the repository has no macOS machine). Written from the documented macOS ps
  output for the same flags: right-aligned columns, `etime` as `[[dd-]hh:]mm:ss`, `comm` as the executable's full
  path (which may contain spaces and parentheses), a login shell as `-zsh`. Replace it with a real recording from the
  owner's Mac when one is made (plan section 8).
