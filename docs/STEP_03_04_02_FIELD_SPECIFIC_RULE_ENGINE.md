# Step 3.4.2 — Field-Specific Rule Engine

## Objective

Implement a deterministic engine that interprets the semantic rules
defined in `FIELD_RULES` and converts violations into `QualityIssue`
objects.

The engine does not modify the input DataFrame.

## Supported Rule Types

The first implementation supports:

- positive_integer
- monetary
- zip
- year
- categorical
- text

## Processing Flow

DataFrame
    ↓
FIELD_RULES
    ↓
Field-specific rule engine
    ↓
Rule evaluation
    ↓
QualityIssue objects

## Positive Integer

Used for:

- Storeys
- Number of Buildings

Rules:

- value must be integer-compatible
- value must be >= configured minimum
- fractional values are invalid

## Monetary

Used for:

- Building Value
- Contents
- BI
- Other

Rules:

- value must be numeric-compatible
- negative values are invalid
- zero is allowed

## ZIP

Rules:

- value must be integer-compatible
- value must not be negative
- five-digit ZIP values are the normal expected structure
- leading zeros must not be silently lost

ZIP structure violations should be reported separately from type errors.

## Year

Used for Year Built.

Rules:

- integer-compatible
- minimum configured value
- cannot exceed current year

## Categorical

Used for Fire Sprinklers (Y/N).

Values must belong to the configured allowed-value set.

## Text

For configured text fields:

- value must be string-like
- numeric-only values can be flagged as suspicious/invalid according
  to the field configuration

## Design Constraints

The engine must:

1. Be deterministic.
2. Produce `QualityIssue` objects.
3. Preserve the original observed value.
4. Include evidence explaining the violation.
5. Never modify the DataFrame.
6. Never automatically repair data.
7. Work from `FIELD_RULES`, not dataset-specific column names.