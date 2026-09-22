# Traced flows

> Static trace: every step has a real location, and an unresolved step means the trace stopped, not execution.

## Coverage

| Traced flows | steps | unresolved | stop at first boundary |
|---|---|---|---|
| 1 | 40 | 0 | 0 |

## FLOW-005 — cli  build_wheel

- Entry point: packaging/pypi/build_wheel.py:176 [argparse]
- Handler: main
- Files touched: packaging/pypi/build_wheel.py

| Step | Call | Location | Resolution |
|---|---|---|---|
| main | WheelWriter | packaging/pypi/build_wheel.py:238 | local |
| main | add | packaging/pypi/build_wheel.py:239 | local |
| main | add | packaging/pypi/build_wheel.py:240 | local |
| main | build_metadata | packaging/pypi/build_wheel.py:240 | local |
| main | add | packaging/pypi/build_wheel.py:241 | local |
| main | build_wheel_file | packaging/pypi/build_wheel.py:241 | local |
| main | add | packaging/pypi/build_wheel.py:246 | local |
| main | add | packaging/pypi/build_wheel.py:247 | local |
| main | close | packaging/pypi/build_wheel.py:248 | local |

+31 library or method calls on this path (in the fact records)
