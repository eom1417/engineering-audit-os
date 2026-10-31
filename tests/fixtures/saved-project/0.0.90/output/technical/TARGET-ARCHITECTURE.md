# Target architecture

> Source inventory and reviewed target proposals are separate. Unspecified targets remain gaps.

## Reference type and target components

Type: `python-cli` (a modular monolith). 2 target components; 0 forbidden imports the plan removes.

| Component | Layer | Files | Moving in | Forbidden imports |
|---|---|---:|---:|---:|
| `domain` | domain | 6 | 0 | 0 |
| `feature:cli-shop` | services | 0 | 0 | 0 |

## Infrastructure decisions

- ✅ **configuration**: Keep: Flags and one config file, validated at start. The check: Every invalid setting exits with code 2 and its name. (no tool: a code change: one typed settings module). Evidence: the environment is read in 0 file(s)
- ⬜ **data**: Introduce: Inputs and outputs in documented formats with versions. Why: A format change breaks scripts that call the tool. (no tool: a schema owner in code). Evidence: typed schema source: none
- ⬜ **ci**: Introduce: Tests on every push, on every supported Python. Why: A change breaks an older interpreter unseen. (GitHub Actions + pre-commit). Evidence: 0 CI step(s) in the repository
- ⬜ **tests**: Introduce: Unit tests plus approval tests of command output. Why: Output is the tool's interface. (pytest + ApprovalTests). Evidence: 0 test file(s)
- ⬜ **observability**: Introduce: Exit codes that mean something, and --verbose logging. Why: A script calling the tool needs to know what failed. (no tool: a local rotating log inside the application; there is no server to collect from). Evidence: 0 observability signal(s)
- ✅ **secrets**: Keep: Tokens from the environment or keychain only. The check: No credential in the repository. (no tool: the host's own secret store). Evidence: 0 secret-class credential(s) committed

## Who decided

No assistant judged this target: the rules decided every part of it.


## Retained structure

Source inventory is shown below. Missing target decisions remain explicit gaps.

## Components

### Retain (1)
- `T-app` ← `app` → `domain`: app · the rules alone

## Architectural decisions

## Gap matrix
- covered: 0 / 1
