# Step 2.6 — Fuzzy Matching

## 1. Purpose

Fuzzy matching handles source SOV headers that are similar to a target
field but are not exact matches.

Examples:

    "Building Values"
    "Building Val"
    "Bulding Value"
    "No Buildings"

may be similar to canonical target fields.

---

## 2. Position in the Mapping Pipeline

The mapping pipeline is:

    Source Header
        ↓
    Normalization
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

Fuzzy matching must not override an already successful exact match.

---

## 3. Similarity Algorithm

RapidFuzz is used for lexical similarity.

The implementation compares a normalized source header against
normalized canonical target names and approved domain aliases.

The best candidate is selected based on the highest similarity score.

---

## 4. Threshold

The challenge specification requires a RapidFuzz threshold of:

    >= 0.75

RapidFuzz returns scores on a 0–100 scale.

Therefore:

    75 / 100 = 0.75

The implementation converts the score to the range:

    0.0–1.0

A fuzzy candidate is accepted only when:

    confidence >= 0.75

---

## 5. Candidate Generation

For each unresolved source header:

1. Normalize the header.
2. Compare against canonical target names.
3. Compare against approved domain aliases.
4. Keep the best candidate for each target field.
5. Rank candidates by similarity.
6. Accept the best candidate only if its score reaches 0.75.

---

## 6. One-to-One Assignment

A target field already assigned by an earlier deterministic layer
must not be silently assigned again.

Fuzzy matching therefore receives the set of already assigned target
fields.

---

## 7. Unresolved Headers

If the best fuzzy score is below 0.75:

    matched_field = None

The column is passed to the semantic embedding layer.

Fuzzy matching should not force a weak mapping.

---

## 8. Confidence

For an accepted fuzzy match:

    confidence = similarity / 100

Example:

    RapidFuzz score = 87.5

    confidence = 0.875

---

## 9. Explainability

Every fuzzy result should expose:

- Source header
- Normalized header
- Candidate target
- Similarity score
- Confidence
- Match method
- Deterministic status

This information will later be included in the mapping evidence shown
to the human reviewer.

---

## 10. Safety

Fuzzy matching is lexical.

It does not understand the meaning of a column.

For example, lexical similarity alone should not be considered sufficient
evidence for semantically ambiguous columns.

Those cases continue to the embedding and LLM layers.

---

## 11. Definition of Done

Step 2.6 is complete when:

- RapidFuzz is installed.
- Normalized headers are compared.
- Canonical names and domain aliases are considered.
- Scores are converted to 0–1 confidence.
- The 0.75 threshold is enforced.
- Existing assignments are protected.
- Weak matches remain unresolved.
- Unit tests pass.