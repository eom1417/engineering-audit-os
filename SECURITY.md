# Security model

The CLI executes no project scripts, installs no target dependencies, opens no network connection, and sends no source to a model. Repository files and source references are untrusted data, not instructions. Run output must be outside the target. Symlinks and known credential files are excluded from content capture. Metadata and source snippets can still be sensitive: inspect packets locally before sharing. This is not a complete secret detector.

Project permissions, actual cloud IAM, deployed gateways, production data, logs and recoverability require separate authorized evidence. Missing repository config is not proof that production protection is missing.

A malicious local process can race file reads. Use a read-only snapshot or isolated checkout when auditing untrusted or concurrently modified repositories. Do not use privileged credentials. JSON files are evidence containers, not executable policy.

Report issues privately to the repository owner; no contact address or hosted repository has been configured in this distribution.
