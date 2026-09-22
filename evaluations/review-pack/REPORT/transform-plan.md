# Machine-executable transform plan

> Each stage is a self-contained spec. The acceptance criterion is behavioral; movements are simulated before execution. A stage with no viable canonical home stays open.

## Summary

- stages: 0
- moves with no viable candidate: 0

## Limits

- A stage is a proposal, not an executed edit; the human or the isolated-copy remediator runs it.
- Acceptance commands are the closest executable proxy; runtime behaviour is not measured here.
- A predicted delta is computed from the structural reduction; a runtime check may show different results.
- A falsifier is a hint at the kind of evidence that would reject the move; it is not a guard.
- No stage edits /opt/flow or environment files: the engine never modifies the target outside its declared scope.
