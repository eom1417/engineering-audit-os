# Capability scorecard

> Measured from 2 report(s). An unmeasured indicator is not a pass. Target for every domain: 0.8.

**Overall 0.4785** · 3 of 9 domains at target.

| Domain | Score | Target | Met | Unmeasured |
| --- | --- | --- | --- | --- |
| layered_engineering | 1.0 | 0.8 | yes | 0 |
| structure_python | 0.9592 | 0.8 | yes | 0 |
| structure_polyglot | 0.3027 | 0.8 | no | 0 |
| runtime_surface | 0.4583 | 0.8 | no | 0 |
| load_model | 0.0 | 0.8 | no | 0 |
| target_architecture | 0.0 | 0.8 | no | 0 |
| transformation_plan | 0.6667 | 0.8 | no | 1 |
| report_clarity | 0.92 | 0.8 | yes | 0 |
| independent_proof | 0.0 | 0.8 | no | 0 |

## layered_engineering

| Indicator | Value |
| --- | --- |
| invariants_enforced | 1.0 |
| one_artifact_one_owner | 1.0 |
| policy_covers_every_file | 1.0 |
| policy_has_no_violations | 1.0 |
| tests_pass | 1.0 |

## structure_python

| Indicator | Value |
| --- | --- |
| entry_points_traced | 0.8367 |
| python_files_parsed | 1.0 |
| python_imports_resolved | 1.0 |
| symbols_extracted | 1.0 |

## structure_polyglot

| Indicator | Value |
| --- | --- |
| imports_resolved_outside_python | 0.067 |
| languages_seen | 13 |
| languages_with_depth | 0.5385 |

## runtime_surface

| Indicator | Value |
| --- | --- |
| detectors_finding_evidence | 0.3333 |
| detectors_implemented | 0.5833 |

## load_model

| Indicator | Value |
| --- | --- |
| entry_points_with_a_cost_record | 0.0 |
| projection_recorded | 0.0 |
| questions_answered | 0.0 |

## target_architecture

| Indicator | Value |
| --- | --- |
| components_assessed | 0.0 |
| decisions_with_alternatives | 0.0 |
| gap_matrix_resolved | 0.0 |

## transformation_plan

| Indicator | Value |
| --- | --- |
| predictions_verified | unmeasured |
| stages_with_predicted_effect | 1.0 |
| stages_with_rollback | 1.0 |
| stages_with_runnable_acceptance | 0.0 |

## report_clarity

| Indicator | Value |
| --- | --- |
| claims_with_evidence_and_falsifier | 1.0 |
| documents_declared | 1.0 |
| interpretation_declares_its_basis | 1.0 |
| output_contract_clean | 1.0 |
| top_findings_are_about_the_reader_s_code | 0.6 |

## independent_proof

| Indicator | Value |
| --- | --- |
| independent_reviews | 0.0 |

## Limits

- A score measures what the tool produced on the reports it was given, never how useful a reader found it. The independent_proof domain is the only one that asks that question.
- An indicator with no evidence is unmeasured, not zero and not one.
- Scores over a corpus of one project describe that project.
