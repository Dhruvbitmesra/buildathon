# Step 3.2 — Quality Issue Schema

## Purpose

Agent 3 needs a standardized representation for every data-quality issue
detected during validation.

The issue schema acts as the contract between:

- deterministic validation
- statistical analysis
- LLM reasoning
- human approval
- Agent 4 transformation

A validation rule should detect an issue without directly modifying data.

---

## Design Goals

Each quality issue must answer:

1. What field is affected?
2. Which row is affected?
3. What is wrong?
4. What value was observed?
5. What was expected?
6. What evidence supports the issue?
7. How severe is the issue?
8. What action is recommended?
9. How confident is the system?
10. What uncertainty remains?
11. What is the current approval status?

---

## Issue Schema

The primary model is `QualityIssue`.

Suggested fields:

- `issue_id`
- `row_index`
- `source_field`
- `target_field`
- `issue_type`
- `severity`
- `observed_value`
- `expected_condition`
- `evidence`
- `recommendation`
- `confidence`
- `uncertainty`
- `status`

---

## Field Definitions

### issue_id

Unique identifier for the issue.

Example:

`DQ-000001`

This allows an issue to be tracked through the entire
Agent 3 → Human Review → Agent 4 pipeline.

---

### row_index

The original dataframe row associated with the issue.

Use the dataframe index rather than assuming that the row number starts
at 1.

---

### source_field

Original source column name.

Example:

`Year Built`

This is useful because the original workbook must remain traceable.

---

### target_field

Canonical SOV field after Agent 2 mapping.

Example:

`Year Built`

The source and target fields may differ.

Example:

`# Of Stories` → `Storeys`

---

### issue_type

Machine-readable category describing the problem.

Initial supported categories:

- `missing_value`
- `invalid_type`
- `negative_value`
- `invalid_category`
- `invalid_range`
- `future_year`
- `duplicate`
- `statistical_anomaly`
- `cross_field_conflict`

The list can be extended later.

---

### severity

Severity indicates the potential impact of the issue.

Allowed values:

- `low`
- `medium`
- `high`
- `critical`

Severity is not the same as confidence.

For example:

A future `Year Built` value can have:

- severity = `high`
- confidence = `0.99`

---

### observed_value

The actual value found in the source data.

Examples:

`2035`

`-250000`

`"Unknown"`

Values must be represented safely so that the schema remains serializable.

---

### expected_condition

Human-readable description of the expected condition.

Examples:

`Year Built must not exceed the current year.`

`Building Value must be non-negative.`

`Fire Sprinklers must be one of Y, N, Y13, Y(13R).`

---

### evidence

Structured evidence supporting the issue.

Evidence may contain:

- validation rule
- observed statistics
- value profile
- allowed values
- comparison values
- anomaly score
- related fields

Evidence should describe what the system observed.

It should not contain unsupported conclusions.

---

### recommendation

Optional proposed action.

Examples:

`Review source value`

`Normalize to Y`

`Remove duplicate row`

`No automatic correction recommended`

The recommendation is not an instruction to modify the data.

Only approved operations may later be executed by Agent 4.

---

### confidence

A value between 0 and 1 representing confidence in the detection or
recommendation.

This is not a probability.

Example:

```text
0.99