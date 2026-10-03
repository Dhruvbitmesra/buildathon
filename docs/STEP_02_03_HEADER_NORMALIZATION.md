# Step 2.3 — Header Normalization

## 1. Purpose

The Schema Intelligence Agent receives source SOV headers that may contain:

- Different capitalization
- Leading or trailing spaces
- Underscores
- Hyphens
- Punctuation
- Parentheses
- Multiple spaces
- Common formatting variations

Before deterministic or fuzzy matching is performed, headers must be normalized.

Normalization does not decide which target field a source column represents.

It only creates a consistent representation for comparison.

---

## 2. Example

Source:

    " Bldg_Repl_Cost_New "

Normalized:

    "bldg repl cost new"

Another source:

    "BUILDING-VALUE"

Normalized:

    "building value"

---

## 3. Normalization Rules

The normalization pipeline should:

1. Convert the value to a string.
2. Strip leading and trailing whitespace.
3. Convert text to lowercase.
4. Replace underscores with spaces.
5. Replace hyphens with spaces.
6. Replace punctuation with spaces.
7. Normalize repeated whitespace.
8. Return the normalized string.

---

## 4. Important Constraint

Normalization must not perform semantic mapping.

For example:

    "Bldg Repl Cost New"

may normalize to:

    "bldg repl cost new"

It must NOT directly become:

    "building value"

Semantic mapping belongs to the Schema Intelligence Agent.

---

## 5. Why This Separation Matters

Keeping normalization separate from mapping prevents dataset-specific hardcoding.

Normalization is a generic preprocessing operation.

Mapping uses multiple evidence sources:

- Exact matching
- Domain aliases
- Fuzzy similarity
- Value profiles
- Embedding similarity
- Cross-encoder ranking
- Approved SOV memory
- LLM reasoning for unresolved ambiguity

---

## 6. Failure Handling

If a source header is:

- Empty
- Missing
- None
- Not usable as text

the normalization function should return an empty string rather than raising an exception.

---

## 7. Testing Requirements

Tests must verify:

- Lowercase conversion
- Whitespace removal
- Underscore handling
- Hyphen handling
- Punctuation handling
- Repeated whitespace
- Empty values
- None values
- Preservation of meaningful words
- No semantic mapping during normalization

---

## 8. Definition of Done

Step 2.3 is complete when:

- A reusable header normalization function exists.
- Normalization is deterministic.
- Normalization does not perform semantic mapping.
- Unit tests cover the required cases.
- All Step 2.3 tests pass.