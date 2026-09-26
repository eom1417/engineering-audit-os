# Handover kit

These files were written by EAOS from the audit of this project. Each one is in
the format of the tool that runs it, and that tool accepted it before handover:
see `validation.json` next to this file.

## Use it

1. Copy this folder into the root of the repository, keeping the paths:
   `.github/workflows/eaos.yml`, `.pre-commit-config.yaml`, `renovate.json`,
   `.dependency-cruiser.cjs`, `semgrep/`, `otel/`, `slo/`, `readiness/`,
   `mkdocs.yml` and `docs/`.
2. Record the boundary violations the code has today, so CI fails only on new
   ones: the command is at the top of `.dependency-cruiser.cjs`.
3. To run the EAOS gate in CI, pin a baseline (`eaos baseline pin`), commit it
   as `.eaos/baseline/`, and set the repository variable `EAOS_PACKAGE`.
4. `pip install pre-commit && pre-commit install` for the fast local checks.
5. The security job fails on any high or critical finding from the first run:
   the first milestone of the plan (stabilize) closes them.

## Files

$listing
