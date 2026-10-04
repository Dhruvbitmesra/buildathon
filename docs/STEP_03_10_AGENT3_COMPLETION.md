# Step 3.10 — Agent 3 Completion: Recommendations, Review Loop, Orchestrator

## Objective

Finish Agent 3 (Data Quality & Reasoning) so it:

- detects issues on every row without flooding on real Excel data;
- turns issues into grouped, explainable recommendations;
- applies a deterministic review policy;
- runs a human review gate with bounded re-reasoning;
- hands Agent 4 an approved, auditable change plan;
- never modifies the source DataFrame.

## Problems fixed in the detection layer

Found by running the validator on value shapes from `data/input/*.xlsx`:

| Problem | Fix |
|---|---|
| 9 tests failing: `field_types` used `"integer"` strings, config used `int` | `_check_types` accepts both (`TYPE_ALIASES`) |
| `field_validator.py` monetary/zip/year/categorical rules were stubs returning `None` | Stubs removed; those rules live in `validator.py` and the semantic validators |
| Excel stores ZIPs as floats (`75219.0`): 2 issues per cell, 865 rows -> 1,730 issues | Whole-number ZIPs are a lossless cast. Only 3-4 digit ZIPs (lost leading zeros) are flagged, with the padded candidate |
| `% Sprinklered` columns (`0.0`, `1.0`, `0.57`) got 2 issues each | Column-level scale (0-1 or 0-100): 0 -> N, full -> Y, partial -> HIGH review |
| Non-US rows (Spain/Portugal) flagged as invalid US states | State/ZIP rules only run when Country is blank or US |
| `"$1,200,000"`, `"1.2M"` reported as HIGH type errors | LOW `format_inconsistency` with exact numeric candidate |
| `"Texas"`, `"ny"`, `"Calif."`, `"V.I."` not reported (FR-3 inconsistent abbreviations) | LOW standardisation to the 2-letter code; territories added |
| Year Built `9999` / `0` (unknown placeholders) | `year_placeholder` rule; candidate is blank, never a guessed year |
| Year Built as a full date | `year_date_format` standardisation |
| Missing required column produced 0 issues | One dataset-level `column_not_mapped` issue per field |
| Fully empty column produced one issue per row | Collapsed into one `column_empty` issue |
| Same cell reported by several checks (e.g. future year + outlier) | `issue_consolidator.py` keeps one primary issue per cell; others attached as `related_issues` / `statistical_context` |
| Statistical noise: 271/863 Contents rows, 99 Storeys rows flagged | Monetary fields analysed on log10; a method is skipped when its spread is 0; severity is advisory (LOW/MEDIUM) |
| Numeric location numbers (`1.0`) flagged as type errors | Whole-number References are a lossless cast |
| `quality_score` saturates at 0 on any real file | Kept for compatibility; new `intake_quality_score` (severity-weighted share of clean cells), per-field `field_quality` (completeness, validity) and `row_flags` |
| `is_number()` rejected numpy integers | Uses `numbers.Real` |

New checks: `cross_field_validator.py` (ZIP prefix vs State, zero total insured value, US state on a foreign row, duplicate rows).

Every `QualityIssue` now has a stable `rule_id`.

## Architecture

```text
canonical DataFrame (+ Agent 2 mappings)          canonical_frame.py
        |
DeterministicValidator.validate_sov()             validator.py
   type / missing / negative / category / range / future year / duplicate
   state / zip / monetary / sprinkler / format / statistical
   + missing columns + cross-field + consolidation
        |
QualityAggregator.aggregate(issues, dataframe)    quality_aggregator.py
        |
RecommendationEngine.build()                      recommendation_engine.py
   group by pattern -> normalizer proposal -> re-validate candidate
   + column_mapping items from Agent 2
        |
DecisionPolicy                                    decision_policy.py
        |
ReviewLedger  <->  ReviewSession                  reflection.py
   approve / reject / edit / escalate / Approve All
   re-reasoning: LLM (GroqReasoner) -> RuleBasedReasoner -> escalate
        |
ApprovedChange[]  -> Agent 4
```

Orchestrator: `DataQualityAgent` in `agent.py` (`analyse`, `review_session`, `run(state)`).

## Shared normalizers (`normalizers.py`)

The before/after preview and Agent 4's transformation use the same pure
functions (`propose()` in Agent 3, `apply_operation()` in Agent 4), so
what the reviewer approves is exactly what is applied.

Closed operation list: `parse_monetary`, `parse_integer`, `extract_year`,
`pad_zip`, `standardise_state`, `canonicalize_sprinkler`,
`trim_whitespace`, `set_blank`, `set_value`, `rename_column`, `keep`.

## Recommendation contract (`recommendation_schema.py`)

- `action_type`: `column_mapping`, `data_correction`, `standardisation`, `flag_for_review` (FR-4)
- `operation` + `operation_params`
- `before_value`, `after_value`, `samples` (explicit before/after per row)
- `title`, `rationale`, `uncertainty` (mandatory, non-empty)
- `evidence` (rule, expected condition, observed values, statistical and field context)
- `detection_confidence` (the issue exists) and `fix_confidence` (the fix is right)
- `policy`, `policy_reasons`, `attempt`, `reasoning_source`, `status`

Validation: `flag_for_review` must be `keep`; `set_blank` cannot carry a
value; a rejection must give a reason; an edit must give a value.

## Grouping

One recommendation per pattern, keyed by field, rule, operation and
(for categorical values) the normalised source value. On SOV_Q8B3 (863
rows) the queue is 53 items, e.g. "Fire Sprinklers: change 'No' to 'N'
(395 rows)".

## Decision policy

| Case | Policy |
|---|---|
| Standardisation or column mapping, lossless, fix confidence >= 0.90, severity LOW/MEDIUM, deterministic, first attempt | `bulk_approvable` (eligible for Approve All) |
| Anything else (data corrections, flags, HIGH/CRITICAL, LLM output, re-reasoned) | `human_review_required` |

Nothing is applied without a human decision. Export is ready only when
no item is `recommended` or `escalated`.

## Review and re-reasoning

| Action | Result |
|---|---|
| Approve | `approved` (or `resolved` if escalated) |
| Edit | Human value, validated by the deterministic validator. A single value is refused for a group whose rows have different source values; use `{row_index: value}`. Column mappings accept one of the 17 target fields not already used |
| Reject (reason required) | Attempt < max: re-reason. Attempt = max: `escalated` |
| Reject an escalated item | `resolved`, source values kept |
| Escalate | `escalated` |

`max_reasoning_attempts = 2`: original + one re-reasoned attempt; the
second rejection escalates.

Re-reasoning guardrails, applied to every proposal (LLM or rule-based):

- operation must be allowed for the field;
- must not repeat a rejected proposal;
- `set_value` / `rename_column` values must be an allowed value or appear in the reviewer's note;
- one value may not replace different source values;
- every converted value is re-validated; failures are discarded.

The LLM receives only the field, rule, expected condition, up to 5
distinct observed values (Reference/Address/City masked) and the
reviewer's note; temperature 0; JSON output validated by Pydantic. Any
failure falls back to the rule-based reasoner, then to escalation.

## Agent 4 hand-off

`ReviewSession.approved_changes()` returns `ApprovedChange` objects with
`source_column`, `target_column`, `row_index`, `source_row`,
`transformation_applied`, `before_value`, `after_value`, `confidence`,
`rationale`, `approved_by`, `timestamp` and `reasoning_attempt` — the
FR-6 audit-log fields. Agent 4 applies them with
`normalizers.apply_operation()`.

## SOVState

New fields: `header_row`, `schema_mappings`, `canonical_data`,
`source_columns`, `quality_report`, `review_ledger`,
`agent3_fingerprint`, `agent_trace`. `DataQualityAgent.run(state)`
reads Agent 2's output and writes Agent 3's; failures are recorded in
`state.errors`.

## Evaluation

```bash
python -m tests.evaluate_agent3_real
```

Plants anomalies (missing, negative TIV, future year, Storeys 0, type
errors, currency text, invalid state, malformed ZIP, duplicate
reference) into the four real samples, using a fixed reference mapping
so Agent 2's accuracy does not affect the measurement.

Result: 70/70 planted anomalies detected (100%, target 90%), 100%
rationale coverage, DataFrames unchanged.

## Tests

| File | Level |
|---|---|
| `test_normalizers.py` | Unit |
| `test_validate_sov_pipeline.py` | Validator integration + regressions |
| `test_quality_metrics.py` | Report metrics |
| `test_recommendation_layer.py` | Contract, policy, engine |
| `test_agent3_review_flow.py` | Agent 3 integration, review loop, reasoner guardrails, SOVState |
| `test_agent3_real_samples.py` | Real-sample recall regression |

## Known limitations

- The data dictionary types Zip as Integer; Agent 3 keeps it as text to
  preserve leading zeros. Agent 4 must decide the export cell type.
- Numeric sprinkler coverage maps to `Y`; whether the system is `Y13`
  or `Y(13R)` cannot be inferred.
- `GroqReasoner` is tested with a fake client only.
- The reviewer's note is sent to the LLM as written.
- Approving a column-mapping change requires re-running `analyse()`
  (pass `previous=` to keep decisions on unchanged items).
