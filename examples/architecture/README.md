# Synthetic architecture example

This model is a record-contract fixture, not a reviewed application's architecture. It makes direction explicit: entry depends on service; service calls store. Source paths and evidence ID E-1 are illustrative and require real evidence when applying the framework. Never copy its REVIEWED status to an actual audit.

`impact(store)` should discover service then entry as potential consumers. The calls edge participates in impact but not the static-dependency-cycle calculation. A cycles signal needs a declared imports/uses_contract cycle. Context packets include rule owners and consumers even when an explicit graph edge has not yet been recorded.

The automated tests create isolated files and bind the model to the fixture revision. In a real run, use architecture.schema.json and rebuild all nodes, contracts, rules and change scenarios from that repository.
