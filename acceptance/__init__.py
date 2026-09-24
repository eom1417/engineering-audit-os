"""Acceptance tests written with the plan, before the code they accept.

Each file here is the acceptance of one task in docs/north-star.json and fixes that task's interface. They
fail until the task is done. An executor never edits them: acceptance/LOCK.json records their digests, and
`python tools/acceptance.py test NAME` refuses to run them if any file changed.
"""
