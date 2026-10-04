# Step 3.4.3 — Field-Specific Validation Integration

## Objective

Integrate the standalone `FieldSpecificValidator` into the existing
`DeterministicValidator`.

The integration must preserve all existing validation behavior.

## Architecture

The deterministic validation pipeline becomes:

1. Generic validation
2. Field-specific validation
3. Combined QualityIssue list

Both layers produce `QualityIssue` objects.

## Important Constraint

The field-specific validator must not replace the generic validator.

Both validators serve different purposes.

Generic validation handles structural constraints such as:

- missing values
- expected types
- negative values
- allowed categories
- configured ranges
- future years
- duplicate references

Field-specific validation handles semantic field behavior such as:

- positive integer semantics
- monetary semantics
- ZIP semantics
- suspicious numeric-only text
- field-specific categorical rules

## No Data Modification

The integrated validator must never modify the input DataFrame.

## No Automatic Repair

Detected issues are reported only.

Repair and recommendation are handled by later Agent 3 stages.

## Output

The final result remains:

    list[QualityIssue]

The caller should not need to know whether an issue came from
generic validation or field-specific validation.