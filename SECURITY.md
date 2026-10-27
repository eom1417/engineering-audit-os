# Security

## Reporting a vulnerability

Please report vulnerabilities **privately**, never in a public issue: use GitHub's
[private vulnerability reporting](https://github.com/eom1417/engineering-audit-os/security/advisories/new) on this
repository. Include the version (`eaos --version`), what you ran, what happened and, if you can, a minimal reproduction.
You will receive an acknowledgement, and a fix or a decision, as soon as the report is understood. Please give us a
reasonable time to release a fix before any public disclosure.

## Supported versions

| Version | Security fixes |
| --- | --- |
| The latest `0.0.x` release (on `main`) | yes |
| Any earlier `0.0.x` | no: run `install.sh` again to update |

EAOS is a pilot (`0.0.x`): a fix ships as the next patch version, never as a back-port.

## The security model

EAOS reads untrusted code and runs other people's apps, so its boundaries are part of its design.

| What EAOS does | Its boundary |
| --- | --- |
| **Reads your project** (`facts`, `audit`, the check) | The project is read-only input. Instructions written inside it are data and never followed. Symlinks and known credential files are not captured. |
| **Runs your app** (setup, recordings, screens, speed) | Only after your explicit consent, in a separate copy, without your secrets, your `.env` or your real database. A command the app's profile asks for is checked against an allow-list before it runs. |
| **Runs the external tools** | Each at a pinned version with a recorded checksum and licence, outside your project's environment. A tool that fails is reported; its silence is never read as clean. |
| **Asks your AI assistant** | The assistant judges what the tools found and writes fixes. Every decision it makes must cite evidence from the report, or it is dropped. Your project's text and your app's pages reach its prompts as untrusted data, never as instructions. It works through EAOS's tools and its own sign-in. |
| **Simulates users** (optional) | Personas drive only the copy of your app on your computer, with dummy data in the run's own database; external services are stubbed or reported as not covered. |
| **Fixes your code** | In an isolated copy, card by card, through gates (tests, the app's own checks, layers, copies, dead code, and security engines on every change). What passes reaches you as a branch; nothing is merged until you accept it. |
| **The Studio** | Listens on `127.0.0.1` by default. Every call carries a launch token that only the address EAOS opens holds; every write also needs a CSRF token and a same-origin request. A remote Studio is served only behind your server's own sign-in. |

## What to keep in mind

- On Linux, your app runs in a view of the disk of its own: your home, EAOS's records, the reports, the temporary folder
  and every other project EAOS knows are hidden from it, and its database needs a password of its own. Elsewhere (macOS)
  the separate copy is **not an operating-system sandbox**, and the run records it. Either way the app shares the
  processor, the memory and the local network with the rest of the computer: run EAOS on projects you trust, or inside
  an isolated machine or container.
- Reports, recordings and screen pictures can contain sensitive data from your project. They stay on your computer in
  `~/EAOS/`; review them before sharing.
- EAOS never publishes, deploys or touches production. Cloud permissions, deployed gateways and production data need
  their own evidence: a configuration missing from the repository is not proof that production lacks it.
