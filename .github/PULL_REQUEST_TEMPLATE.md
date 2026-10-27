## What and why

<!-- What changes, and the problem it solves. Link the issue: Closes #… -->

## How it was verified

- [ ] The pull request targets `develop`, from a `dev/<topic>` branch
- [ ] `tools/quality.sh` passes (every code law; no number worse than recorded)
- [ ] `.venv/bin/python -m unittest discover -s tests -q` passes
- [ ] `.venv/bin/python tools/validate.py` passes
- [ ] `(cd console && npm run build)` passes and the built Studio is committed, if `console/` or
  `docs/studio-actions.json` changed
- [ ] A test reproduces the real failure this fixes, if it is a fix
- [ ] Every new text a person reads is in English and in Arabic
- [ ] What a person will see differently is said above, for the next version's `CHANGELOG.md` entry

## Pictures

<!-- For a change to the Studio or the reports: before and after, desktop and phone. -->
