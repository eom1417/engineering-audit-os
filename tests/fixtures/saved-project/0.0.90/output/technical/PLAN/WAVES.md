# Execution waves

> Two tasks touching the same file never share a wave; an investigation precedes the change it informs.

- entry: Required predecessor decisions accepted; file conflicts serialized.
- exit: Record check outcomes or an evidenced investigation decision.

## Wave 1

| # | Task | Kind | Priority |
|---|---|---|---|
| TASK-001 | Dead code: app/old_export.py (no production entry point reaches it) | remediate | 0.0 |
| TASK-002 | Dead code: app/old_mail.py (no production entry point reaches it) | remediate | 0.0 |
| TASK-003 | Dead code: app/old_report.py (no production entry point reaches it) | remediate | 0.0 |
