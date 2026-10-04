# Step 3.4.4.4 — Fire Sprinkler Semantic Validation

## Objective

Add domain-specific semantic validation for the SOV
`Fire Sprinklers (Y/N)` field.

The generic validator already checks whether a value belongs to the
canonical target categories:

- Y
- N
- Y13
- Y(13R)

This step identifies recognizable alternate representations that may
require controlled transformation later.

## Canonical Values

The target schema permits:

- Y
- N
- Y13
- Y(13R)

## Recognized Alternate Representations

Examples that may appear in source SOV files:

- Yes
- No
- Sprinklered
- Not Sprinklered
- 13R
- Y 13
- Y(13R)

These should be detected as semantic representations rather than
automatically modified.

## Invalid / Ambiguous Values

Examples:

- Maybe
- Unknown
- Partial
- ABC

These should generate a quality issue.

## Design Principles

1. Do not modify the DataFrame.
2. Do not automatically normalize values.
3. Preserve the original observed value.
4. Distinguish canonical values from alternate representations.
5. Provide evidence for downstream transformation.
6. Do not duplicate the generic category validator.

## Validation Flow

Raw sprinkler value
    ↓
Missing?
    ↓
Canonical value?
    ├── Yes → valid
    ↓
Recognized alternate representation?
    ├── Yes → semantic issue/recommendation
    ↓
Unknown representation
    └── invalid/ambiguous issue

## Agent 4 Interaction

This validator only identifies semantic representations.

For example:

Yes
    ↓
Agent 3 identifies alternate representation
    ↓
Human approval / transformation decision
    ↓
Agent 4 may transform to Y

Agent 3 must never directly modify the source value.

## Output

Issues should contain:

- observed value
- canonical candidate where applicable
- evidence
- confidence
- recommendation
- uncertainty
- status