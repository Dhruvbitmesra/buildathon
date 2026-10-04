# Step 3.3.4 — Negative-Value Validation

## Purpose

Negative-value validation detects values that are mathematically valid
numbers but are not valid for the corresponding SOV field.

For example:

    Building Value = -500000

is a valid numeric value from a type perspective, but it is not a valid
exposure value.

Therefore, type validation and business-rule validation are separate.

---

## Fields Requiring Non-Negative Values

The initial implementation will validate:

### Monetary / Exposure Fields

- Building Value
- Contents
- BI
- Other

### Count Fields

- Storeys
- Number of Buildings

Negative values are not valid for these fields.

---

## Detection Rule

For each configured field:

    value < 0

produces:

    issue_type = negative_value

The validator must not modify the value.

---

## Missing Values

Missing values are handled by the missing-value validator.

Therefore:

    None
    NaN

must not produce a negative-value issue.

---

## Type Interaction

Negative-value validation should only evaluate numeric values.

For example:

    Building Value = "ABC"

is an `invalid_type` issue.

It should not additionally generate a `negative_value` issue.

This prevents multiple deterministic rules from reporting the same
underlying problem unnecessarily.

---

## Severity

### High

Use high severity for monetary exposure fields:

- Building Value
- Contents
- BI
- Other

A negative exposure value can materially affect downstream insurance
calculations.

### Medium

Use medium severity for count fields:

- Storeys
- Number of Buildings

---

## Confidence

A value that is explicitly less than zero is a deterministic violation.

Therefore:

    confidence = 1.0

---

## Evidence

Each issue should contain evidence describing:

- validation rule
- observed value
- minimum allowed value

Example:

```json
{
    "rule": "non_negative_value",
    "observed_value": -250000,
    "minimum_allowed": 0
}