# Start here: shop

🔴 **Big gap: Judging the problems** (not covered). Sort the problems: No AI assistant was installed or allowed for this check, so the rules stand alone.
🔴 **Big gap: The ideal picture** (not covered). Plan the ideal target: No AI assistant was installed or allowed for this check, so the rules stand alone.

## In short

- I found **3** problems.
- **3** of them EAOS can fix automatically, checking after each fix that your app still works.
- **0** need your decision, or a person's look, before any change.

## The main problems

1. **Dead code** (3)
   Code nothing uses: it makes reading and changing the project harder.
   Can be fixed automatically: 3 of 3 · example: `app/old_export.py`

## Who decided

No assistant judged this target: the rules decided every part of it.

## Repair or rebuild?

**I recommend: repair.** The target keeps or improves most of today's code: it rebuilds or deletes 0 of 6 files (0%), so repairing it is the shorter, safer road.

- Repair: 3 cards (3 small, 0 medium, 0 large), touching 3 files, about 14–39 minutes.
- Rebuild: 6 files in 1 parts written anew, about 41–111 minutes.

A rough rule, not a measure: 3 to 8 minutes a card, and twice that a file written anew, plus preparing the safe copy; it improves with your own fix runs.

## What I recommend

Start with the automatic fixes: they are the safest, and each is tried on a separate copy of your project before you see it.

## The system in layers

Reference type: python-cli. 6 of 6 files placed in their layer; 0 endpoints, 0 tables. The boundaries were not tried on the running app: choose "Try the layers" in the next check.

| Boundary | State | First found |
|---|---|---|
| What ships to the browser | sound: nothing found |  |
| Endpoints and their guards | sound: nothing found |  |
| The data layer's rules | sound: nothing found |  |
| Where the business rules live | sound: nothing found |  |
| The boundaries between layers | sound: nothing found |  |
| Operations | 4 finding(s) | Inputs and outputs in documented formats with versions: not found (typed schema source: none) |
| Tests | sound: nothing found |  |

## Next step

```
eaos next
```

## Technical detail

For a developer or your AI assistant: `CURRENT-STATE.md` · `TARGET-STATE.md` · `GAP-AND-STRATEGY.md` · `EXECUTION-PLAN.md` · `plan.json`
