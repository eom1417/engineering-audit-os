# Controlled architecture benchmark: pricing ownership drift

This small synthetic fixture has a deliberate cross-flow defect, not a production evaluation.
Business requirement: premium customers receive 10% off in BOTH interactive quotes and exports.
The two entry paths currently own conflicting copies of the same business rule. Existing tests only protect standard customers.
An appropriate remedy gives this rule one owner, preserves the entry contracts, and tests premium/standard behavior across both paths.
An inappropriate remedy merely renames files, changes one constant while leaving policy duplication, or adds services/queues for this tiny system.
