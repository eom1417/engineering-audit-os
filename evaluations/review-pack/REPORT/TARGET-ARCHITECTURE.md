# Target architecture

> Source inventory and reviewed target proposals are separate. Unspecified targets remain gaps.

## Retained structure

Source inventory is shown below. Missing target decisions remain explicit gaps.

## Components

### Retain (27)
- `T-root` ← `.`: (root)
- `T-examples.cross-repo` ← `examples/cross-repo`: examples/cross-repo
- `T-examples.cross-repo.web` ← `examples/cross-repo/web`: examples/cross-repo/web
- `T-examples.custom-client` ← `examples/custom-client`: examples/custom-client
- `T-examples.custom-client.gateway.src.catalog` ← `examples/custom-client/gateway/src/catalog`: examples/custom-client/gateway/src/catalog
- `T-examples.custom-client.gateway.src.resources` ← `examples/custom-client/gateway/src/resources`: examples/custom-client/gateway/src/resources
- `T-examples.custom-client.sdk.src` ← `examples/custom-client/sdk/src`: examples/custom-client/sdk/src
- `T-examples.custom-client.sdk.src.http` ← `examples/custom-client/sdk/src/http`: examples/custom-client/sdk/src/http
- `T-examples.layers-gate` ← `examples/layers-gate`: examples/layers-gate
- `T-examples.layers-gate.notify` ← `examples/layers-gate/notify`: examples/layers-gate/notify
- `T-examples.layers-gate.telemetry` ← `examples/layers-gate/telemetry`: examples/layers-gate/telemetry
- `T-examples.layers-gate.web` ← `examples/layers-gate/web`: examples/layers-gate/web
- … the rest are in `target-architecture.json`

### Modify (126)
- `T-cmd.enola` ← `cmd/enola`: cmd/enola
- `T-examples.cross-repo.api` ← `examples/cross-repo/api`: examples/cross-repo/api
- `T-examples.custom-client.backend.src.catalog` ← `examples/custom-client/backend/src/catalog`: examples/custom-client/backend/src/catalog
- `T-examples.custom-client.sdk.src.connectors` ← `examples/custom-client/sdk/src/connectors`: examples/custom-client/sdk/src/connectors
- `T-examples.layers-gate.api` ← `examples/layers-gate/api`: examples/layers-gate/api
- `T-examples.layers-gate.storage` ← `examples/layers-gate/storage`: examples/layers-gate/storage
- `T-examples.policy-as-code.cardholder` ← `examples/policy-as-code/cardholder`: examples/policy-as-code/cardholder
- `T-examples.policy-as-code.customers` ← `examples/policy-as-code/customers`: examples/policy-as-code/customers
- `T-examples.policy-as-code.legacy` ← `examples/policy-as-code/legacy`: examples/policy-as-code/legacy
- `T-internal.clientspec` ← `internal/clientspec`: internal/clientspec
- `T-internal.config` ← `internal/config`: internal/config
- `T-internal.conformance` ← `internal/conformance`: internal/conformance
- … the rest are in `target-architecture.json`

## Architectural decisions

### ADR-001: 1 load blocker(s) on its entry points; 5 live claim(s) about it
- problem: 1 load blocker(s) on its entry points; 5 live claim(s) about it
- options:
  - Bound the entry path with rate limiting and explicit result pagination.
  - Cache repeated reads at the component boundary with an explicit lifetime.
  - Do nothing and accept the measured load blockers.
- chosen: Bound the entry path with rate limiting and explicit result pagination.
- tradeoffs: The component has 5 live claim(s), 0 policy violation(s), 0 cycle(s), and 1 load blocker(s). The chosen option changes 9 file(s); it keeps ownership at this boundary but requires its existing contracts to remain compatible.

### ADR-002: 3 load blocker(s) on its entry points; 4 live claim(s) about it
- problem: 3 load blocker(s) on its entry points; 4 live claim(s) about it
- options:
  - Bound the entry path with rate limiting and explicit result pagination.
  - Cache repeated reads at the component boundary with an explicit lifetime.
  - Do nothing and accept the measured load blockers.
- chosen: Bound the entry path with rate limiting and explicit result pagination.
- tradeoffs: The component has 4 live claim(s), 0 policy violation(s), 0 cycle(s), and 3 load blocker(s). The chosen option changes 1 file(s); it keeps ownership at this boundary but requires its existing contracts to remain compatible.

### ADR-003: 1 live claim(s) about it
- problem: 1 live claim(s) about it
- options:
  - Resolve the live claims inside the existing component boundary.
  - Split the claimed responsibility into a separately owned component.
  - Do nothing and retain the live claims.
- chosen: Resolve the live claims inside the existing component boundary.
- tradeoffs: The component has 1 live claim(s), 0 policy violation(s), 0 cycle(s), and 0 load blocker(s). The chosen option changes 1 file(s); it keeps ownership at this boundary but requires its existing contracts to remain compatible.

### ADR-004: 1 live claim(s) about it
- problem: 1 live claim(s) about it
- options:
  - Resolve the live claims inside the existing component boundary.
  - Split the claimed responsibility into a separately owned component.
  - Do nothing and retain the live claims.
- chosen: Resolve the live claims inside the existing component boundary.
- tradeoffs: The component has 1 live claim(s), 0 policy violation(s), 0 cycle(s), and 0 load blocker(s). The chosen option changes 1 file(s); it keeps ownership at this boundary but requires its existing contracts to remain compatible.

### ADR-005: 1 live claim(s) about it
- problem: 1 live claim(s) about it
- options:
  - Resolve the live claims inside the existing component boundary.
  - Split the claimed responsibility into a separately owned component.
  - Do nothing and retain the live claims.
- chosen: Resolve the live claims inside the existing component boundary.
- tradeoffs: The component has 1 live claim(s), 0 policy violation(s), 0 cycle(s), and 0 load blocker(s). The chosen option changes 1 file(s); it keeps ownership at this boundary but requires its existing contracts to remain compatible.

### ADR-006: 1 live claim(s) about it
- problem: 1 live claim(s) about it
- options:
  - Resolve the live claims inside the existing component boundary.
  - Split the claimed responsibility into a separately owned component.
  - Do nothing and retain the live claims.
- chosen: Resolve the live claims inside the existing component boundary.
- tradeoffs: The component has 1 live claim(s), 0 policy violation(s), 0 cycle(s), and 0 load blocker(s). The chosen option changes 1 file(s); it keeps ownership at this boundary but requires its existing contracts to remain compatible.

### ADR-007: 1 live claim(s) about it
- problem: 1 live claim(s) about it
- options:
  - Resolve the live claims inside the existing component boundary.
  - Split the claimed responsibility into a separately owned component.
  - Do nothing and retain the live claims.
- chosen: Resolve the live claims inside the existing component boundary.
- tradeoffs: The component has 1 live claim(s), 0 policy violation(s), 0 cycle(s), and 0 load blocker(s). The chosen option changes 1 file(s); it keeps ownership at this boundary but requires its existing contracts to remain compatible.

### ADR-008: 1 live claim(s) about it
- problem: 1 live claim(s) about it
- options:
  - Resolve the live claims inside the existing component boundary.
  - Split the claimed responsibility into a separately owned component.
  - Do nothing and retain the live claims.
- chosen: Resolve the live claims inside the existing component boundary.
- tradeoffs: The component has 1 live claim(s), 0 policy violation(s), 0 cycle(s), and 0 load blocker(s). The chosen option changes 1 file(s); it keeps ownership at this boundary but requires its existing contracts to remain compatible.

### ADR-009: 1 live claim(s) about it
- problem: 1 live claim(s) about it
- options:
  - Resolve the live claims inside the existing component boundary.
  - Split the claimed responsibility into a separately owned component.
  - Do nothing and retain the live claims.
- chosen: Resolve the live claims inside the existing component boundary.
- tradeoffs: The component has 1 live claim(s), 0 policy violation(s), 0 cycle(s), and 0 load blocker(s). The chosen option changes 1 file(s); it keeps ownership at this boundary but requires its existing contracts to remain compatible.

### ADR-010: 4 live claim(s) about it
- problem: 4 live claim(s) about it
- options:
  - Resolve the live claims inside the existing component boundary.
  - Split the claimed responsibility into a separately owned component.
  - Do nothing and retain the live claims.
- chosen: Resolve the live claims inside the existing component boundary.
- tradeoffs: The component has 4 live claim(s), 0 policy violation(s), 0 cycle(s), and 0 load blocker(s). The chosen option changes 2 file(s); it keeps ownership at this boundary but requires its existing contracts to remain compatible.

### ADR-011: 4 live claim(s) about it
- problem: 4 live claim(s) about it
- options:
  - Resolve the live claims inside the existing component boundary.
  - Split the claimed responsibility into a separately owned component.
  - Do nothing and retain the live claims.
- chosen: Resolve the live claims inside the existing component boundary.
- tradeoffs: The component has 4 live claim(s), 0 policy violation(s), 0 cycle(s), and 0 load blocker(s). The chosen option changes 10 file(s); it keeps ownership at this boundary but requires its existing contracts to remain compatible.

### ADR-012: 3 live claim(s) about it
- problem: 3 live claim(s) about it
- options:
  - Resolve the live claims inside the existing component boundary.
  - Split the claimed responsibility into a separately owned component.
  - Do nothing and retain the live claims.
- chosen: Resolve the live claims inside the existing component boundary.
- tradeoffs: The component has 3 live claim(s), 0 policy violation(s), 0 cycle(s), and 0 load blocker(s). The chosen option changes 2 file(s); it keeps ownership at this boundary but requires its existing contracts to remain compatible.

Showing 12 of 126 decisions; the rest are in `target-architecture.json`.

## Gap matrix
- covered: 27 / 153
