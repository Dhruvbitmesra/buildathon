# Step 2.8 — Field-Specific Evidence Scoring

## 1. Purpose

Column headers are not always sufficient to determine the intended
target field.

The column value profile provides additional evidence.

This step converts the existing ColumnProfile into field-specific
evidence scores for the 17 canonical SOV target fields.

The output is evidence, not a final mapping decision.

---

## 2. Position in the Pipeline

The current mapping pipeline is:

    Source Header
        ↓
    Header Normalization
        ↓
    Exact Matching
        ↓
    Domain Alias Matching
        ↓
    Fuzzy Matching
        ↓
    Column Value Profiling
        ↓
    Field-Specific Evidence
        ↓
    Embedding Retrieval
        ↓
    Cross-Encoder
        ↓
    LLM Reasoning
        ↓
    Human Review

---

## 3. Evidence Sources

Evidence is derived from the ColumnProfile.

Examples include:

- Numeric ratio
- String ratio
- Missing ratio
- Unique ratio
- Minimum
- Maximum
- Mean
- Median
- Year-like ratio
- Boolean-like ratio
- Sprinkler-like ratio
- ZIP-like ratio
- Currency-like ratio
- Top values

---

## 4. Field-Specific Evidence

Different target fields have different expected characteristics.

### Building Value

Useful evidence:

- High numeric ratio
- Currency-like values

### Contents

Useful evidence:

- High numeric ratio
- Currency-like values

### BI

Useful evidence:

- High numeric ratio
- Currency-like values

### Other

Useful evidence:

- High numeric ratio
- Currency-like values

### Zip

Useful evidence:

- ZIP-like values
- Integer-like numeric values

### Year Built

Useful evidence:

- High year-like ratio

### Storeys

Useful evidence:

- Numeric values
- Small positive integer values

### Number of Buildings

Useful evidence:

- Numeric values
- Small positive integer values

### Fire Sprinklers (Y/N)

Useful evidence:

- Sprinkler-like values
- Boolean-like values

### Address

Useful evidence:

- String values
- High uniqueness

### City

Useful evidence:

- String values
- Moderate uniqueness

### State

Useful evidence:

- String values
- Low/moderate uniqueness

### County

Useful evidence:

- String values
- Moderate uniqueness

### Country

Useful evidence:

- String values
- Low uniqueness

### Occupancy

Useful evidence:

- String values
- Repeated categorical values

### Construction

Useful evidence:

- String values
- Repeated categorical values

### Reference

Useful evidence:

- High uniqueness
- String or identifier-like values

---

## 5. Score Interpretation

Scores are normalized between:

    0.0 and 1.0

A higher score means that the observed column profile is more
consistent with the expected characteristics of the target field.

The score is not a probability.

It must not be interpreted as:

    P(target field | column)

unless a statistical probability model is explicitly developed and
validated.

---

## 6. Important Constraint

This layer must not directly map a column to a target field.

For example:

    Building Value score = 0.82

does not mean:

    matched_field = Building Value

The evidence will later be combined with:

- Header similarity
- Embedding similarity
- Cross-encoder ranking
- SOV memory
- LLM reasoning

---

## 7. Explainability

Each field evidence result should contain:

- Target field
- Overall evidence score
- Individual evidence components
- Human-readable reasons

Example:

    Building Value
    score: 0.84

    evidence:
        numeric_ratio: 1.00
        currency_like_ratio: 0.95

    reasons:
        - Column is predominantly numeric.
        - Values have monetary formatting.

---

## 8. No Dataset-Specific Hardcoding

The scoring rules describe general characteristics of the canonical
SOV fields.

They must not contain mappings specific to the four evaluation
datasets.

For example, this is prohibited:

    "Bldg Repl Cost New" -> Building Value

The header itself is handled by the mapping layers.

---

## 9. Definition of Done

Step 2.8 is complete when:

- Field-specific evidence rules are implemented.
- Evidence scores are between 0 and 1.
- Individual evidence components are exposed.
- Human-readable reasons are generated.
- The system does not directly perform final mapping.
- No evaluation-dataset-specific mappings are hardcoded.
- Unit tests pass.