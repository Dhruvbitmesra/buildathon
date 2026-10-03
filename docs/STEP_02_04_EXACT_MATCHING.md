# Step 2.4 — Deterministic Exact Matching

## 1. Purpose

The first mapping layer of the Schema Intelligence Agent performs
deterministic exact matching.

The objective is to resolve headers that can be confidently matched
without fuzzy matching, embeddings, or an LLM.

---

## 2. Input

The matcher receives a source SOV header.

Example:

    "Building Value"

The header is normalized before comparison.

Example:

    " Building_Value "

becomes:

    "building value"

---

## 3. Matching Sources

A normalized source header is compared against:

1. Canonical target field names
2. Approved domain aliases

For example:

    "building value"

can match:

    "Building Value"

and an approved alias such as:

    "building value"

---

## 4. Important Constraint

This layer must not perform fuzzy or semantic matching.

It must only return a match when the normalized source header exactly
matches a canonical field name or an approved alias.

---

## 5. One-to-One Constraint

A target field should not be assigned to multiple source columns
through deterministic exact matching.

If a target field has already been assigned, another source column
matching the same target should not silently overwrite it.

The conflict must remain visible for later resolution.

---

## 6. Output

The matcher should return structured information containing:

- Source header
- Normalized source header
- Matched target field
- Match method
- Confidence
- Whether the result is deterministic

For an exact match:

    match_method = "exact"

    confidence = 1.0

    deterministic = true

For an unresolved header:

    matched_field = None

    match_method = None

    confidence = 0.0

    deterministic = false

---

## 7. Why This Layer Comes First

Deterministic matching is:

- Fast
- Explainable
- Reproducible
- Easy to test
- Independent of an LLM
- Less susceptible to hallucination

Only unresolved headers should proceed to more expensive
matching techniques.

---

## 8. Failure Handling

The matcher should not raise an exception merely because a header
cannot be mapped.

An unresolved header should be returned as unresolved so that later
layers can process it.

---

## 9. Testing Requirements

Tests must verify:

- Canonical field matching
- Alias matching
- Case-insensitive matching through normalization
- Whitespace handling
- Unresolved headers
- Confidence values
- Match method
- Deterministic flag
- Duplicate target protection

---

## 10. Definition of Done

Step 2.4 is complete when:

- Exact matching is implemented.
- Canonical names are supported.
- Approved aliases are supported.
- No fuzzy or semantic matching occurs.
- Results are structured.
- Duplicate target assignment is detected.
- Unit tests pass.