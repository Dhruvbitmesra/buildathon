# Step 3.3.9 — Deterministic Validation Configuration

## Objective

Centralize the deterministic validation rules for the canonical SOV schema.

The validator should receive a configuration describing:

- required fields
- expected field types
- non-negative numeric fields
- allowed categorical values
- valid numeric ranges
- fields requiring future-year checks
- fields requiring uniqueness checks

This keeps validation independent of any specific input workbook.

## Design Principle

The validator contains generic validation logic.

The SOV configuration contains domain-specific rules.

Therefore:

    Generic Validator
          +
    SOV Validation Configuration
          ↓
    QualityIssue objects

The validator must not modify the input DataFrame.

It only detects and reports issues.

## Canonical SOV Rules

The target schema contains 17 fields:

1. Reference
2. Address
3. City
4. State
5. Zip
6. County
7. Country
8. Building Value
9. Contents
10. BI
11. Occupancy
12. Construction
13. Storeys
14. Number of Buildings
15. Year Built
16. Fire Sprinklers (Y/N)
17. Other

## Missing Values

Missing values remain missing.

They must never be converted to:

- 0
- N/A
- "N/A"
- "Unknown"

Missing values are reported as quality issues when the field is configured as required.

## Type Rules

Canonical types:

| Field | Type |
|---|---|
| Reference | string |
| Address | string |
| City | string |
| State | string |
| Zip | integer |
| County | string |
| Country | string |
| Building Value | float |
| Contents | float |
| BI | float |
| Occupancy | string |
| Construction | string |
| Storeys | integer |
| Number of Buildings | integer |
| Year Built | integer |
| Fire Sprinklers (Y/N) | string |
| Other | float |

## Non-Negative Fields

The following numeric exposure/count fields should not contain negative values:

- Zip
- Building Value
- Contents
- BI
- Storeys
- Number of Buildings
- Other

Year Built is handled separately through range/future-year validation.

## Categorical Rules

Fire Sprinklers (Y/N) allows:

- Y
- N
- Y13
- Y(13R)

The comparison should be normalized for whitespace/case where appropriate, but the exported canonical values remain unchanged.

## Range Rules

Examples:

- Storeys >= 1
- Number of Buildings >= 1
- Year Built >= 0

Range validation must remain deterministic.

## Future Year

Year Built must not exceed the current year.

## Duplicate Reference

Reference should be unique when configured as a unique identifier.

## Output

Every detected problem must become a `QualityIssue`.

The validator must not automatically repair data.

Repair recommendations are handled later by the reasoning/HITL stages.