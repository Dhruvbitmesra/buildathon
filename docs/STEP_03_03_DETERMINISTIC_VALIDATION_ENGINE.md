# Step 3.3 — Deterministic Validation Engine

## Purpose

The Deterministic Validation Engine is the first validation layer of
Agent 3.

It inspects the mapped SOV dataframe using explicit validation rules.

The engine must not use an LLM.

Its purpose is to identify objective data-quality violations and produce
structured QualityIssue objects.

---

## Input

The validation engine receives:

- a pandas DataFrame
- mapped SOV field names
- the current validation context

Example:

    DataFrame
        ↓
    Deterministic Validator
        ↓
    QualityIssue objects

---

## Output

The validator returns:

    list[QualityIssue]

Each issue contains:

- issue ID
- row index
- source field
- target field
- issue type
- severity
- observed value
- expected condition
- evidence
- confidence
- uncertainty
- status

---

## Validation Categories

The first implementation supports:

### 1. Missing Values

Detect missing values in fields where a value is expected.

Examples:

- missing Reference
- missing Address
- missing State
- missing Building Value

Missing values should not automatically be replaced.

---

### 2. Invalid Types

Detect values that cannot be interpreted according to the target
field's expected type.

Examples:

- non-numeric Building Value
- non-integer Storeys
- non-integer Number of Buildings
- invalid Year Built

---

### 3. Negative Values

Detect negative values in fields that should not contain negative
monetary or count values.

Examples:

- Building Value < 0
- Contents < 0
- BI < 0
- Other < 0
- Storeys < 0
- Number of Buildings < 0

---

### 4. Invalid Categories

Detect values outside an allowed categorical vocabulary.

The initial implementation will particularly validate:

Fire Sprinklers (Y/N)

Allowed values:

- Y
- N
- Y13
- Y(13R)

---

### 5. Invalid Ranges

Detect values outside explicitly defined valid ranges.

Examples:

- Storeys < 1
- Number of Buildings < 1

---

### 6. Future Year

Detect Year Built values greater than the current calendar year.

Example:

    Year Built = 2035
    Current Year = 2026

This becomes a future_year issue.

---

### 7. Duplicates

Detect duplicate values where uniqueness is expected.

The first implementation will focus on duplicate Reference values.

---

## Important Design Rule

The validation engine only detects issues.

It does not modify the dataframe.

For example:

    Year Built = 2035

must produce:

    QualityIssue(
        issue_type="future_year"
    )

It must NOT change:

    2035 → 1995

Any approved correction will be handled later by Agent 4.

---

## Confidence

Deterministic rules can produce high-confidence findings.

For example:

    Fire Sprinklers = "MAYBE"

when the allowed values are:

    Y, N, Y13, Y(13R)

has deterministic confidence close to 1.0.

The confidence represents confidence in the detected violation.

It is not a probability.

---

## Severity

Initial severity guidelines:

### Critical

Issues that can make the output unusable or fundamentally unsafe.

### High

Issues that can materially affect insurance exposure data.

Examples:

- negative monetary values
- future Year Built
- invalid sprinkler value

### Medium

Issues that require review but may not materially invalidate the
record.

Examples:

- missing non-critical values
- duplicate references

### Low

Minor quality concerns that do not immediately prevent processing.

---

## Evidence

Every issue should contain deterministic evidence.

Example:

```json
{
    "rule": "year_built_not_future",
    "observed_year": 2035,
    "current_year": 2026
}