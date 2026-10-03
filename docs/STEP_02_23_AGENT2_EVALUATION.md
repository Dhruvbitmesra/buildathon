# STEP 02.23 — Agent 2 Evaluation & Error Analysis

## 1. Objective

Evaluate the real-world performance of Agent 2 Schema Intelligence before
making further changes to the mapping algorithm.

The evaluation focuses on:

- mapping correctness
- unresolved columns
- incorrect assignments
- target-field collisions
- evidence quality
- global assignment behavior
- human-review decisions
- failure reasons

This step is analysis only.

No mapping logic should be changed until the failure patterns are understood.

---

## 2. Current Agent 2 Baseline

The current real B4ID run produced:

- Source columns: 28
- Automatic mappings: 12
- Unresolved columns: 16
- Targets used: 12
- Warnings: 0
- Test suite: 186 passed

The current system successfully avoids forcing unsupported source columns
into the canonical schema.

---

## 3. Expected Behavior

Agent 2 must map a source column to one of the 17 canonical SOV fields only
when sufficient evidence exists.

Otherwise:

    target_field = None
    human_review_required = True

The system must never create a mapping merely because a target field is
available.

---

## 4. Real B4ID Evaluation

### Expected mappings

The following source columns have strong evidence for these canonical fields:

| Source Column | Expected Target | Evidence |
|---|---|---|
| Street | Address | Address-like string values |
| City | City | Exact header |
| State | State | Exact header |
| Zip | Zip | Exact header + numeric ZIP values |
| Building | Building Value | Monetary building values |
| BPP | Contents | Insurance domain alias |
| Other | Other | Exact header |
| Occupancy | Occupancy | Exact header |
| Construction Type | Construction | Domain alias |
| # Of Buildings | Number of Buildings | Domain alias + small integer values |
| # Of Stories | Storeys | Domain alias + small integer values |
| Year Built | Year Built | Exact header + year pattern |
| % Sprinklered | Fire Sprinklers (Y/N) | Domain alias + binary values |

---

## 5. Expected Unresolved Columns

The following fields may legitimately remain unresolved because they are
not part of the 17-field canonical SOV schema or lack sufficient evidence:

- Loc #
- Bldg.
- Outside City Limits
- Owned/ Leased
- 2024 - Increase 10%
- Improvements & Betterments
- Extra Expense
- Unnamed: 13
- EDP
- Valuation
- Protection Class
- Square Footage
- Alarm

Repeated increase columns should not automatically map to a canonical
field simply because they contain numeric monetary values.

---

## 6. Current Failure

The most important current failure is:

    Building → unresolved

The source values are monetary:

    250000
    120000
    7316910
    ...

Therefore the column has strong value evidence for:

    Building Value

However, Agent 2 currently leaves it unresolved.

This indicates that the problem is probably not value profiling itself.

The likely area to investigate is the interaction between:

1. semantic candidate generation
2. deterministic/domain candidates
3. candidate scoring
4. candidate eligibility
5. Hungarian one-to-one assignment

---

## 7. Important Diagnostic Question

Determine why:

    Building → Building Value

does not survive the global assignment.

Specifically inspect:

- all candidates generated for `Building`
- score for `Building Value`
- score for competing targets
- evidence components
- whether `Building Value` was already assigned to another source column
- whether the competing mapping had stronger evidence
- whether the candidate was removed by the eligibility threshold
- whether the score was altered during candidate merging

---

## 8. Candidate Evidence to Inspect

For every source column, record:

```text
source_header
target_field
final_score
deterministic_score
fuzzy_score
semantic_score
embedding_similarity
value_evidence_score
llm_score
method
human_review_required
reason