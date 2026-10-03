# STEP 02.21 — Deterministic Evidence Integration into Agent 2

## Objective

Integrate the deterministic schema-matching components already implemented
in Agent 2 into the final SchemaMappingAgent orchestration.

The current Agent 2 primarily relies on the semantic pipeline. This means
that exact matches, domain aliases, fuzzy matches, and field-specific value
evidence are not sufficiently represented in the final global assignment.

This step combines all available evidence before the final one-to-one
assignment.

---

## Why This Step Is Necessary

The SOV schema contains many domain-specific columns whose meaning cannot
always be determined from semantic similarity alone.

Examples include:

- Building
- Street
- # Of Stories
- % Sprinklered
- BPP
- EDP
- Loc #

A column can have weak embedding similarity while having very strong
domain-specific value evidence.

For example:

    # Of Stories
        values → 3, 3, 3, 1, 3

The values strongly support the target:

    Storeys

Similarly:

    % Sprinklered
        values → 0, 0, 0, 0, 0

requires domain-specific reasoning because the target field is:

    Fire Sprinklers (Y/N)

---

## Existing Components

The following components already exist and must be reused:

1. Header normalization
2. Exact matching
3. Domain aliases
4. Fuzzy matching
5. Value profiling
6. Field-specific evidence
7. BGE embedding retrieval
8. Cross-encoder reranking
9. Semantic evaluation
10. LLM fallback
11. Hungarian one-to-one assignment

No dataset-specific hardcoding should be introduced.

---

## Evidence Priority

The system follows deterministic-first reasoning.

Preferred order:

1. Exact canonical match
2. Domain alias match
3. Strong fuzzy match
4. Strong value evidence
5. Semantic embedding evidence
6. Cross-encoder evidence
7. LLM reasoning
8. Human review

The ordering does not mean later evidence is ignored. Multiple evidence
sources can contribute to the final score.

---

## Candidate Evidence

Every source column should produce candidate target fields.

Each candidate may contain:

- target_field
- score
- exact_match
- alias_match
- fuzzy_score
- embedding_similarity
- cross_encoder_score
- value_evidence_score
- evidence_reasons
- method

---

## Deterministic Evidence

### Exact Match

If a normalized source header exactly matches a canonical target field,
the candidate receives strong evidence.

Example:

    City → City
    State → State
    Occupancy → Occupancy

---

### Domain Alias

Insurance-specific terminology is supported through the domain alias
dictionary.

Examples:

    Bldg Repl Cost → Building Value
    # Of Buildings → Number of Buildings
    # Of Stories → Storeys
    % Sprinklered → Fire Sprinklers (Y/N)

---

### Fuzzy Matching

RapidFuzz is used for near matches.

The configured fuzzy threshold remains:

    0.75

---

## Value Evidence

Column values are profiled independently from the header.

Evidence can include:

- numeric ratio
- string ratio
- integer-like values
- year-like values
- boolean values
- sprinkler values
- currency values
- ZIP-like values
- missingness
- unique ratio
- value patterns

This prevents a semantically weak header from being incorrectly rejected
when its values strongly support a target field.

---

## Combined Candidate Score

The implementation should preserve strong deterministic signals while
still allowing semantic evidence.

Conceptually:

    final_score =
        deterministic_evidence
        + semantic_evidence
        + value_evidence

The exact weights should be implemented centrally rather than duplicated
across modules.

---

## One-to-One Assignment

After candidates are generated for every source column:

    source columns × target fields

are represented as a score matrix.

The Hungarian algorithm performs the final global assignment.

Each target field can be assigned at most once.

Columns below the minimum assignment threshold remain unresolved.

---

## Important Constraint

Do not hardcode dataset-specific mappings.

Incorrect:

    if source_header == "Building":
        target = "Building Value"

Correct:

    use header normalization
    + domain aliases
    + value evidence
    + semantic evidence

This allows the system to generalize to unseen SOV workbooks.

---

## LLM Safety

LLM output must never be trusted blindly.

If the LLM returns:

    confidence = None

or any invalid structured response:

1. reject the response
2. do not crash Agent 2
3. preserve deterministic/semantic candidates
4. mark the column unresolved or human-review-required if necessary

The LLM is a fallback reasoning layer, not the source of truth.

---

## Expected Improvements

The B4ID real run should improve mappings such as:

    Building → Building Value
    Street → Address
    # Of Stories → Storeys
    % Sprinklered → Fire Sprinklers (Y/N)

while irrelevant columns may remain unresolved.

Examples of legitimately unresolved fields may include:

    Loc #
    Bldg.
    Outside City Limits
    Owned/ Leased
    Protection Class
    Square Footage
    Alarm

depending on the target schema and available evidence.

---

## Success Criteria

Step 2.21 is successful when:

1. Existing unit tests remain passing.
2. Deterministic matchers participate in Agent 2.
3. Value evidence participates in Agent 2.
4. No dataset-specific mapping rules are introduced.
5. Malformed LLM output does not crash Agent 2.
6. B4ID produces sensible mappings for:
   - Building
   - Street
   - # Of Stories
   - % Sprinklered
7. Global one-to-one assignment remains enforced.
8. Low-confidence mappings remain available for human review.

---

## Next Step

After this step passes:

    Step 2.22 — Real Agent 2 Evaluation Across All SOV Files

The four real SOV workbooks will be evaluated before beginning Agent 3.