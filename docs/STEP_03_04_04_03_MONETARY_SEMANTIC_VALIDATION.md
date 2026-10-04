# Step 3.4.4.3 — Monetary Representation Validation

## Objective

Add semantic validation for monetary SOV fields.

The generic deterministic validator already checks numeric types and
non-negative values. This step focuses on monetary representation and
formatting.

## Applicable Fields

The monetary fields are:

- Building Value
- Contents
- BI
- Other

## Supported Representations

The validator should recognize common monetary representations such as:

- `1200000`
- `1,200,000`
- `$1,200,000`
- `1.2M`
- `1.2m`
- `750K`
- `$750K`
- `2.5B`

## Design Principles

1. Do not modify the DataFrame.
2. Do not perform monetary conversion.
3. Do not duplicate generic numeric validation.
4. Preserve the original observed value in the issue.
5. Detect representation patterns deterministically.
6. Keep transformation separate from validation.
7. Do not hardcode values from a particular dataset.

## Validation Scope

The validator should identify:

- recognizable monetary strings
- unrecognized monetary representations
- malformed suffix representations
- unexpected currency/text patterns

Numeric values that are already valid numeric representations should not
produce an issue.

## Examples

Valid representations:

- `1200000`
- `$1,200,000`
- `1.2M`
- `750K`

Potentially invalid:

- `$ABC`
- `1.2MM`
- `1,2,000`
- `USD ABC`

## Output

Detected issues should contain:

- issue_id
- row_index
- source_field
- target_field
- issue_type
- severity
- observed_value
- expected_condition
- evidence
- recommendation
- confidence
- uncertainty
- status

## Important

This validator does not convert:

`1.2M → 1200000`

That transformation belongs to the controlled transformation stage.