# Step 2.5 — Domain Alias Dictionary

## 1. Purpose

SOV source files frequently use abbreviations, shortened terminology,
and common insurance/property terminology instead of the exact target
schema names.

The Domain Alias Dictionary provides generic domain vocabulary that can
be used during schema matching.

---

## 2. Design Principle

The dictionary contains domain knowledge, not dataset-specific
mappings.

Allowed:

    "bldg" -> building terminology

    "bi" -> business interruption terminology

    "repl" -> replacement terminology

Not allowed:

    A specific dataset column is manually mapped because it appeared
    in one of the evaluation files.

---

## 3. Target Fields

Aliases are organized around the 17 canonical target fields:

- Reference
- Address
- City
- State
- Zip
- County
- Country
- Building Value
- Contents
- BI
- Occupancy
- Construction
- Storeys
- Number of Buildings
- Year Built
- Fire Sprinklers (Y/N)
- Other

---

## 4. Normalization

Every alias must pass through the same header normalization function
used by the deterministic matcher.

Therefore:

    "Bldg_Value"

and:

    "bldg value"

can be represented consistently.

---

## 5. Matching Role

The alias dictionary is used before fuzzy and semantic matching.

Pipeline:

    Source Header
        ↓
    Header Normalization
        ↓
    Exact Canonical Match
        ↓
    Domain Alias Match
        ↓
    Fuzzy Matching
        ↓
    Embedding Retrieval
        ↓
    Cross-Encoder
        ↓
    LLM Reasoning
        ↓
    Human Review

---

## 6. Safety

The dictionary must never contain raw row values.

It must also not contain:

- Customer names
- Addresses
- Policy numbers
- Location records
- Dataset-specific examples as direct mappings

Only reusable terminology is stored.

---

## 7. Definition of Done

Step 2.5 is complete when:

- Domain aliases are stored separately from matching logic.
- Aliases are normalized.
- Every alias maps to one canonical target field.
- Dataset-specific hardcoding is avoided.
- Duplicate aliases are detected.
- Unit tests pass.