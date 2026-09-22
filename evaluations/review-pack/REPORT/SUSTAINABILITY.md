# Sustainability dashboard

> Six measurable properties. Values come from deterministic facts; targets from the engagement contract. The gap is the distance to the target; a proposed move closes it.

## Indicators

| Indicator | Current | Target | Gap |
| --- | --- | --- | --- |
| P1 Single source | 0.0 | 0.0 | 0.0 |
| P2 Minimal path | 0.0 | 0.0 | 0.0 |
| P3 Single owner per field | 0 | 0 | 0 |
| P4 Honest boundaries | 0 | 0 | 0 |
| P5 Verifiable paths | 0.0 | 0.0 | 0.0 |
| P6 Understandable units | 242 | 0 | 242 |

## Proposed moves

No moves required; every gap is zero.
## Details

The full measurement behind every indicator — inputs, thresholds and sites — is in `sustainability.json`.

- **P1 Single source** — duplicates=0, symbols=10495
- **P2 Minimal path** — functions=10368, redundant=0
- **P3 Single owner per field** — no detail
- **P4 Honest boundaries** — cycles=0, measured=True, policy_declared=False, policy_violations=0
- **P5 Verifiable paths** — flows=1, measured=True, stopping_at_first_boundary=0
- **P6 Understandable units** — oversized=242

## Limits

- Every indicator is a function of structural facts only; runtime behaviour is out of scope.
- Targets are taken from the engagement contract or the declared policy; no target is invented.
- A transformation is a proposal; its predicted delta is computed from the structural reduction, not from runtime measurements.
- A falsifier is a hint at the kind of evidence that would reject the move; it is not a guard.
