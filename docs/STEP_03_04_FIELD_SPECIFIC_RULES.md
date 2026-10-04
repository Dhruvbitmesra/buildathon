# Step 3.4 — Field-Specific Validation Rules

## Objective

Extend the deterministic validation layer with rules that understand
the meaning of canonical SOV fields.

Generic type validation answers questions such as:

    "Is Storeys an integer?"

Field-specific validation answers questions such as:

    "Is Storeys a positive integer that represents a plausible
     number of building levels?"

The field-specific layer must remain deterministic.

LLMs are not used to decide whether a value violates a hard rule.

---

## Validation Principle

Agent 3 follows:

    Generic Type Validation
            ↓
    Field-Specific Validation
            ↓
    Statistical Validation
            ↓
    Cross-Field Validation
            ↓
    LLM Reasoning

Field-specific rules produce QualityIssue objects.

They do not modify the DataFrame.

---

# Canonical SOV Fields

The validator operates on the canonical 17-field schema:

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

---

# Field-Specific Rules

## Reference

Purpose:

Identify a location/exposure record.

Rules:

- Must not contain an empty string when present.
- Duplicate values are handled by the duplicate validator.
- No artificial Reference value should be generated.

The validator should not impose a universal formatting pattern because
Reference formats may differ between source systems.

---

## Address

Purpose:

Physical location address.

Rules:

- Must be string-like.
- Empty values are handled by missing-value validation.
- Extremely short non-empty values may be suspicious but should not
  automatically be classified as invalid.

Address quality should therefore primarily be reported as evidence,
rather than a hard failure.

---

## City

Purpose:

Location city.

Rules:

- Must be string-like.
- Missing values are handled separately.
- Numeric-only values should be considered invalid.

---

## State

Purpose:

US state name or state code.

Rules:

- Must be string-like.
- Empty values are handled separately.
- Numeric-only values are invalid.
- State semantic validation should allow both names and standard
  abbreviations.

Examples:

    California
    CA
    New York
    NY

Unknown state values should become quality issues rather than being
automatically corrected.

---

## Zip

Purpose:

Postal/ZIP code.

Rules:

- Must be numeric/integer-compatible.
- Must not be negative.
- A five-digit US ZIP is the expected common structure.
- Leading-zero ZIP codes must not be converted incorrectly.

The validator should distinguish between:

    invalid type
    invalid range
    suspicious ZIP structure

ZIP validation should not modify the value.

---

## County

Purpose:

County associated with the location.

Rules:

- Must be string-like.
- Missing values are handled separately.
- Numeric-only values are suspicious.

No universal county naming format should be imposed.

---

## Country

Purpose:

Country associated with the location.

Rules:

- Must be string-like.
- Missing values are handled separately.

No automatic country normalization is performed at this stage.

---

## Building Value

Purpose:

Replacement/reported value associated with the building.

Rules:

- Must be numeric or numeric-compatible.
- Must not be negative.
- Currency symbols and formatted numeric values should be handled
  during normalization before strict numeric validation.
- Zero is allowed by the deterministic rule.

Examples of values that may require normalization:

    $1,200,000
    1.2M
    2500000

The validator itself should report malformed values rather than
silently modifying them.

---

## Contents

Purpose:

Value of contents/exposure.

Rules:

- Must be numeric or numeric-compatible.
- Must not be negative.
- Zero is allowed.

---

## BI

Purpose:

Business interruption value.

Rules:

- Must be numeric or numeric-compatible.
- Must not be negative.
- Zero is allowed.

---

## Occupancy

Purpose:

Type/use of the insured location.

Rules:

- Must be string-like.
- Empty values are handled separately.
- Numeric-only values are suspicious.
- No universal fixed category list is imposed because occupancy
  categories can vary by dataset.

---

## Construction

Purpose:

Construction classification.

Rules:

- Must be string-like.
- Empty values are handled separately.
- Numeric-only values are suspicious.
- No dataset-specific construction vocabulary is hardcoded.

---

## Storeys

Purpose:

Number of building storeys.

Rules:

- Must be integer-compatible.
- Must be at least 1.
- Must not be negative.
- Fractional values are invalid.

Examples:

    1       valid
    5       valid
    20      valid
    0       invalid
    -2      invalid
    2.5     invalid

---

## Number of Buildings

Purpose:

Number of buildings represented by the record.

Rules:

- Must be integer-compatible.
- Must be at least 1.
- Must not be negative.
- Fractional values are invalid.

Examples:

    1       valid
    5       valid
    0       invalid
    -1      invalid
    2.5     invalid

---

## Year Built

Purpose:

Original construction year.

Rules:

- Must be integer-compatible.
- Must not be negative.
- Must not exceed the current year.
- Fractional years are invalid.

Examples:

    1985    valid
    2020    valid
    2027    invalid when current year is 2026
    0       technically invalid/suspicious and handled by range rules
    1985.5  invalid

---

## Fire Sprinklers (Y/N)

Allowed canonical values:

    Y
    N
    Y13
    Y(13R)

Rules:

- Values outside the approved set are invalid.
- Missing values remain missing.
- No automatic conversion is performed.

---

## Other

Purpose:

Other numeric exposure/value.

Rules:

- Must be numeric or numeric-compatible.
- Must not be negative.
- Zero is allowed.

---

# Hard Rules vs Suspicion Rules

Not every unusual value should be treated as a hard error.

### Hard deterministic violations

Examples:

- negative Building Value
- Storeys = 0
- Number of Buildings = 0
- Year Built > current year
- invalid sprinkler code
- fractional Number of Buildings

These produce deterministic QualityIssue objects.

### Suspicious values

Examples:

- unusually short Address
- numeric-looking City
- unfamiliar Occupancy category
- unusual Construction label
- unusual ZIP structure

These should be represented as lower-confidence evidence and can later
be considered by statistical or LLM reasoning.

---

# No Automatic Repair

Field-specific validation must never:

- fill missing values
- replace invalid values
- convert categories automatically
- invent ZIP codes
- infer states
- change monetary values

Its responsibility is:

    Detect
      ↓
    Explain
      ↓
    Recommend later

Transformation happens only after approval.