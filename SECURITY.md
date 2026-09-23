# Security model

Security boundaries depend on the command:

- `audit`, `facts`, `dossier`, `tasks` and the local record and graph commands do not invoke a model or execute target scripts.
- `audit --test-command` and `verify --execute` do run the target's test suite, in a separate copy. That copy is not an operating-system sandbox: use them only on trusted projects, or inside an isolated environment.
- `run` and `continue` send eligible, heuristically redacted source ranges and audit records to the explicitly configured provider. An HTTP provider opens network connections; a command provider executes the configured adapter without a shell, in an empty working directory. That adapter inherits the invoking process environment and is trusted code, not a sandboxed plugin.
- `implement` and `improve` invoke the provider, create separate candidate copies, apply planned edits, and execute explicitly configured verification commands. Checks receive a minimal environment plus names explicitly listed in `inherit_env`. Their working directory is not an OS security boundary; commands can access resources outside the candidate copy. Target dependencies are not installed automatically.

Repository files and source references are untrusted data, not instructions. Run output must be outside the target. Symlinks and known credential files are excluded from content capture. Metadata, generated records and source snippets can still be sensitive: inspect inputs before authorizing provider access. Source ranges are redacted with whole-file context before slicing, but this is not a complete secret detector. See [runtime boundaries](core/RUNTIME.md).

Project permissions, actual cloud IAM, deployed gateways, production data, logs and recoverability require separate authorized evidence. Missing repository config is not proof that production protection is missing.

A malicious local process can race file reads. Use a read-only snapshot or isolated checkout when auditing untrusted or concurrently modified repositories. Do not use privileged credentials. JSON files are evidence containers, not executable policy.

Report issues privately to the repository owner; no contact address or hosted repository has been configured in this distribution.
