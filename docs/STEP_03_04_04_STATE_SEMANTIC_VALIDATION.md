# Step 3.4.4.1 — State Semantic Validation

## Objective

Add a domain-specific validation layer for the SOV `State` field.

The generic deterministic validator already checks:

- missing values
- basic types
- numeric-only text
- other structural constraints

This step adds semantic validation to identify state values that do not represent
a recognized state code or state name.

## Why This Is Needed

A value can be technically a string while still being semantically invalid.

Examples:

- `CA` → valid
- `California` → valid
- `Californiaa` → invalid
- `CAL` → suspicious/invalid
- `12345` → invalid

Therefore, type validation alone is insufficient.

## Design Principles

1. Do not modify the source DataFrame.
2. Do not perform automatic correction.
3. Report evidence for every detected issue.
4. Keep the state vocabulary configurable.
5. Do not hardcode dataset-specific values.
6. Preserve the existing deterministic-first architecture.
7. Avoid duplicating generic validation rules.

## Validation Flow

State value
    ↓
Missing?
    ↓
Generic validation
    ↓
State semantic validator
    ↓
Normalize representation
    ↓
Check recognized state code/name
    ↓
Valid → no issue
Invalid → QualityIssue

## Supported Representations

The validator should recognize:

- official two-letter state codes
- official full state names

The vocabulary should be maintained separately from the validator logic.

## Output

Invalid state values should produce:

- issue_id
- row_index
- source_field
- target_field
- issue_type
- severity
- observed_value
- expected_condition
- evidence
- confidence
- uncertainty
- status

The validator must not replace or modify the invalid value.

## Testing

Tests should cover:

- valid state code
- valid full state name
- invalid state value
- numeric-only state
- missing state
- multiple invalid states
- DataFrame immutability