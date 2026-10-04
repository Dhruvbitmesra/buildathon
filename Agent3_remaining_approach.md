from pathlib import Path

content = r"""# Agent 3 — Remaining Implementation Approach
## SOVereign AI — Agentic SOV Cleansing & Intelligence System

**Purpose:** This document is the implementation handoff for the remaining work in Agent 3 (Data Quality & Reasoning). It is written so another coding agent can implement the remaining pieces without changing the established architecture or silently skipping requirements.

---

# 1. Agent 3 objective

Agent 3 is the **Data Quality & Reasoning Agent**.

Its job is to inspect the schema-mapped SOV data, detect data-quality problems, explain why each problem matters, propose safe recommendations, collect/track human decisions, and support a controlled re-reasoning loop.

The most important architectural rule is:

> **Agent 3 detects and recommends; it does not silently modify the source DataFrame.**

Actual approved transformations belong to Agent 4.

The challenge requires deterministic validation over every row so data-quality recall does not depend on the LLM. The LLM is used for recommendations/reasoning where deterministic rules cannot safely decide what should happen.

Source design requirements specify:
- deterministic-first validation;
- LLM reasoning only where useful;
- evidence-backed recommendations;
- before/after samples;
- rationale;
- confidence;
- uncertainty;
- human approval;
- re-reasoning up to two times after rejection;
- escalation when uncertainty remains.

---

# 2. Current Agent 3 status

The following work is already implemented and tested.

## 2.1 Foundation
- Agent 3 foundation exists.
- Data-quality package structure exists.
- Agent 3 follows typed issue/state-oriented design.

## 2.2 Quality issue contract
Implemented:
`app/agents/data_quality/issue_schema.py`

Current issue concepts include:
- `MISSING_VALUE`
- `INVALID_TYPE`
- `NEGATIVE_VALUE`
- `INVALID_CATEGORY`
- `INVALID_RANGE`
- `FUTURE_YEAR`
- `DUPLICATE`
- `STATISTICAL_ANOMALY`
- `CROSS_FIELD_CONFLICT`

Severity:
- LOW
- MEDIUM
- HIGH
- CRITICAL

Status:
- DETECTED
- RECOMMENDED
- APPROVED
- REJECTED
- ESCALATED
- RESOLVED

`QualityIssue` contains:
- issue ID
- row index
- source field
- target field
- issue type
- severity
- observed value
- expected condition
- evidence
- recommendation
- confidence
- uncertainty
- status

## 2.3 Deterministic validation
Implemented:
`app/agents/data_quality/validator.py`

Current deterministic checks:
1. missing values
2. type compatibility
3. negative values
4. categorical values
5. ranges
6. future years
7. duplicates
8. field-specific semantic validation
9. state validation
10. ZIP validation
11. monetary validation
12. sprinkler semantic validation
13. statistical anomaly validation

The validator does not modify the DataFrame.

## 2.4 Field-specific validation
Implemented:
`field_validator.py`

Covers:
- Reference
- Address
- City
- State
- ZIP
- County
- Country
- monetary fields
- Occupancy
- Construction
- Storeys
- Number of Buildings
- Year Built
- sprinkler field

## 2.5 Semantic validators
Implemented:
- `state_validator.py`
- `zip_validator.py`
- `monetary_validator.py`
- `sprinkler_validator.py`

ZIP is intentionally represented internally as `str`, because ZIP is an identifier and must preserve leading zeros such as `02108`.

Do NOT convert ZIP values to integers.

## 2.6 Statistical anomaly detection
Implemented:
`statistical_validator.py`

Current statistical approach:
- numeric SOV fields
- minimum sample size
- IQR method
- modified Z-score / MAD method
- issue severity based on evidence from statistical methods
- no DataFrame modification

Statistical anomaly detection is advisory evidence. An outlier is not automatically a bad value.

## 2.7 Quality aggregation
Implemented:
`quality_aggregator.py`

Produces `QualityReport` with:
- total issues
- issues by severity
- issues by type
- issues by field
- critical/high/medium/low counts
- human-review-required flag
- quality score
- complete issue list

Current score:
- starts at 100
- CRITICAL = 25 penalty
- HIGH = 15 penalty
- MEDIUM = 5 penalty
- LOW = 1 penalty
- bounded to [0,100]

Current tests for the aggregator pass.

## 2.8 Integration
The real `DeterministicValidator` output can now flow into `QualityAggregator`.

The integration tests pass.

---

# 3. Remaining Agent 3 work

The remaining work should be implemented in this order:

```text
STEP 3.6
Quality Decision / Human Review Policy
        ↓
STEP 3.7
Recommendation Engine
        ↓
STEP 3.8
Evidence + Before/After Representation
        ↓
STEP 3.9
Agent 3 Decision Contract
        ↓
STEP 3.10
Reflection / Re-reasoning Loop
        ↓
STEP 3.11
Agent 3 Orchestrator
        ↓
STEP 3.12
SOVState Integration
        ↓
STEP 3.13
Agent 3 Evaluation Harness
        ↓
STEP 3.14
Full Agent 3 Integration Tests
        ↓
STEP 3.15
Agent 3 Freeze / Regression Suite
```

Do not skip directly to the LLM.

---

# 4. STEP 3.6 — Quality Decision / Human Review Policy

## Goal

Convert raw quality issues into an explicit decision policy.

The system needs to answer:

> Does this issue require automatic recommendation, human approval, escalation, or no action?

The decision must be deterministic and auditable.

## Suggested decision categories

Create a decision enum:

```text
AUTO_SAFE_RECOMMENDATION
HUMAN_REVIEW_REQUIRED
ESCALATED
NO_ACTION
```

Do not automatically transform data here.

## Suggested policy

### LOW
Usually:
- recommendation may be generated;
- human approval is optional depending on operation risk.

### MEDIUM
Usually:
- recommendation allowed;
- approval required before transformation.

### HIGH
Always:
- human review required.

### CRITICAL
Always:
- human review required;
- block downstream transformation.

## Important distinction

Severity and confidence are different.

For example:

```text
HIGH severity + confidence 0.98
```

still requires human review.

Likewise:

```text
LOW severity + confidence 0.60
```

should not be treated as safe automatic correction.

The decision policy should consider:
- severity
- confidence
- issue type
- whether a proposed operation is reversible
- whether the value can be inferred safely
- whether the operation changes source information

---

# 5. STEP 3.7 — Recommendation Engine

Create a recommendation engine that consumes `QualityIssue` objects.

Suggested file:

```text
app/agents/data_quality/recommendation_engine.py
```

It should produce a structured recommendation.

Suggested contract:

```text
QualityRecommendation
---------------------
issue_id
action
operation
before_value
suggested_value
reason
evidence
confidence
uncertainty
requires_human_approval
```

Possible operations should be closed-list values, for example:

```text
KEEP
REVIEW
NORMALIZE
COERCE_TYPE
CANONICALIZE
FLAG
NO_ACTION
```

Do not allow arbitrary operation strings from the LLM.

The recommendation engine should first use deterministic logic.

Examples:

### Recognized sprinkler alias

```text
Input:
YES

Recommendation:
CANONICALIZE

Suggested:
Y

Confidence:
0.95

Approval:
Required
```

### Unknown sprinkler value

```text
Input:
MAYBE

Recommendation:
REVIEW

Suggested:
null

Approval:
Required
```

Never guess `MAYBE -> Y`.

### Negative Building Value

```text
Input:
-500000

Recommendation:
REVIEW

Suggested:
null

Approval:
Required
```

Never automatically convert it to zero.

---

# 6. STEP 3.8 — Evidence and before/after representation

Every recommendation must be explainable.

Create a structured evidence object.

Suggested fields:

```text
Evidence
--------
rule
observed_value
normalized_value
expected_condition
sample_values
statistical_context
field_context
reasoning_source
```

Not every field needs to be populated for every issue.

The important requirement is that every recommendation has a reason.

For example:

```json
{
  "rule": "sprinkler_semantics",
  "observed_value": "YES",
  "normalized_value": "YES",
  "expected_condition": "Canonical sprinkler values are Y, N, Y13, Y(13R)",
  "reason": "YES is a recognized alternate representation of Y"
}
```

Before/after must be explicit:

```text
before_value = "YES"
after_value = "Y"
```

For uncertain cases:

```text
before_value = "MAYBE"
after_value = null
```

Do not fabricate an after-value.

---

# 7. STEP 3.9 — Agent 3 Decision Contract

Create a single typed output contract for Agent 3.

Suggested file:

```text
app/agents/data_quality/decision_schema.py
```

Suggested top-level structure:

```text
Agent3Decision
--------------
issue_id
decision
recommendation
operation
before_value
after_value
confidence
uncertainty
evidence
requires_human_approval
reason
status
```

Potential statuses:

```text
DETECTED
RECOMMENDED
APPROVED
REJECTED
ESCALATED
RESOLVED
```

Use Pydantic.

All values must be validated.

Confidence must be:

```text
0.0 <= confidence <= 1.0
```

If an operation requires a human, the contract must make that explicit.

---

# 8. STEP 3.10 — Reflection / Re-reasoning loop

This is one of the important agentic features.

The intended flow is:

```text
Agent 2 schema mapping
        ↓
Agent 3 deterministic validation
        ↓
Agent 3 reasoning
        ↓
Human review
        ↓
REJECTED?
   ├── NO → continue
   │
   └── YES
        ↓
Re-reason
        ↓
Validation again
        ↓
Second rejection?
   ├── NO → continue
   │
   └── YES
        ↓
Escalate to human
```

Maximum automatic re-reasoning attempts:

```text
2
```

Do not create an infinite loop.

Suggested state:

```text
reasoning_attempt: int
max_reasoning_attempts: int = 2
previous_decisions: list
rejection_reasons: list
```

## Important rule

A rejection must contain a reason.

For example:

```text
Human rejection:
"Do not convert YES to Y because this client's convention uses YES explicitly."
```

The next reasoning attempt receives:
- original issue
- original evidence
- previous recommendation
- rejection reason

It must generate a new recommendation.

If still unresolved after two attempts:

```text
status = ESCALATED
```

---

# 9. STEP 3.11 — Agent 3 Orchestrator

Create:

```text
app/agents/data_quality/agent.py
```

The orchestrator should connect the pieces.

Suggested flow:

```text
input DataFrame
    ↓
DeterministicValidator
    ↓
QualityIssue[]
    ↓
QualityAggregator
    ↓
RecommendationEngine
    ↓
DecisionContract[]
    ↓
Human Review Gate
    ↓
Approved / Rejected
    ↓
Optional re-reasoning
    ↓
Final Agent3 result
```

Agent 3 should NOT modify the DataFrame.

It should return decisions that Agent 4 can later execute.

---

# 10. Agent 3 should not own transformation

This boundary is extremely important.

Agent 3:

```text
DETECT
EXPLAIN
RECOMMEND
REQUEST APPROVAL
```

Agent 4:

```text
APPLY APPROVED OPERATION
```

Therefore:

```text
Agent 3:
"YES → Y recommended"

Agent 4:
"Apply YES → Y because approved"
```

This prevents an LLM from silently changing insurance exposure data.

---

# 11. STEP 3.12 — SOVState integration

Agent 3 should eventually receive and update the shared typed state.

The shared state should contain information such as:

```text
source workbook metadata
selected sheets
schema mapping
mapping confidence
quality issues
quality report
recommendations
human decisions
reasoning attempts
escalations
audit information
```

Do not store unnecessary raw row data in long-lived agent state.

The Agent 3 state should make it possible for the UI to display:

```text
Issue
↓
Evidence
↓
Recommendation
↓
Confidence
↓
Human decision
↓
Reasoning history
```

---

# 12. STEP 3.13 — LLM reasoning

Only after deterministic validation and recommendation rules are complete should the LLM be integrated.

LLM responsibilities:

- interpret ambiguous issues;
- explain evidence;
- propose candidate recommendation;
- provide uncertainty;
- reason about cross-field conflicts;
- reconsider a rejected recommendation.

LLM must NOT:

- invent values;
- change arbitrary columns;
- choose a field outside the 17-field schema;
- silently fill missing values;
- override human rejection;
- directly mutate the DataFrame.

Use structured Pydantic output.

Temperature should remain 0.

Use only the necessary context.

For privacy:
- mask names/addresses before external LLM calls;
- send only necessary headers/evidence/sample values;
- never send entire raw SOV rows unnecessarily.

---

# 13. STEP 3.14 — Cross-field conflict detection

This should be added before Agent 3 is frozen.

Cross-field conflicts are important because individual fields can look valid while the combination is suspicious.

Examples:

### Year Built vs current year

Already covered by future-year validation.

### Storeys

```text
Storeys = 0
```

should be invalid.

### Number of Buildings

```text
Number of Buildings = 0
```

should be invalid.

### Monetary relationships

Potentially suspicious combinations can be flagged, but do not over-constrain the data.

For example:

```text
Building Value = 0
Contents = 500000
```

may be legitimate.

Do not automatically call it invalid.

### Sprinkler relationship

If a source contains an original numeric sprinkler representation such as:

```text
0
1
```

the system should use explicit domain evidence before recommending a conversion.

Do not blindly infer every numeric representation.

---

# 14. Statistical anomaly policy

Keep statistical anomalies separate from hard validation failures.

Example:

```text
Building Value:
100k
120k
110k
115k
25M
```

`25M` may be an outlier.

The correct result is:

```text
STATISTICAL_ANOMALY
```

not:

```text
INVALID_VALUE
```

The recommendation should say:

```text
Review this unusually large value.
```

It should not automatically replace it.

This distinction is important for insurance data.

---

# 15. Quality score policy

The current quality score is an intake-quality indicator.

It is NOT a probability that the dataset is correct.

Current interpretation:

```text
100 = no detected issues
lower score = more/severer detected issues
```

Keep the score deterministic and reproducible.

Do not allow an LLM to change the score.

After human approval/rejection, the system may calculate a separate final/resolved score if useful, but do not silently redefine the original intake score.

---

# 16. Human review policy

The human-review queue should prioritize:

```text
CRITICAL
HIGH
MEDIUM
LOW
```

Within a severity, prioritize:
1. unresolved
2. low-confidence
3. high-impact fields
4. cross-field conflicts
5. statistical anomalies

High-impact SOV fields include:
- Building Value
- Contents
- BI
- Occupancy
- Construction
- Storeys
- Number of Buildings
- Year Built
- Fire Sprinklers

The human must be able to:

```text
Approve
Reject
Escalate
```

A review action should record:

```text
issue_id
approver
decision
reason
timestamp
```

---

# 17. Auditability

Every Agent 3 decision should be traceable.

At minimum:

```text
issue_id
source_field
row_index
observed_value
issue_type
severity
recommendation
suggested_value
confidence
reason
human_decision
decision_reason
timestamp
reasoning_attempt
```

Agent 4 will later use this information to create the final transformation audit log.

---

# 18. Testing strategy

Do not only test individual classes.

Agent 3 needs four levels of tests.

## Level 1 — Unit tests

Test:
- decision policy
- recommendation engine
- decision schema
- evidence generation
- reflection counter
- escalation logic

## Level 2 — Validator integration

Already started and passing.

Continue to ensure:

```text
DataFrame
→ Validator
→ QualityIssue[]
→ QualityReport
```

## Level 3 — Agent 3 integration

Test:

```text
DataFrame
→ deterministic validation
→ aggregation
→ recommendation
→ decision
```

## Level 4 — Reflection integration

Test:

```text
first recommendation
→ human rejection
→ second reasoning
→ rejection
→ escalation
```

Also test:

```text
first recommendation
→ rejection
→ second recommendation
→ approval
```

And:

```text
approval on first attempt
→ no re-reasoning
```

---

# 19. Important regression tests

Do not lose the following behavior.

## ZIP

```text
"02108"
```

must remain:

```text
"02108"
```

Never convert it to `2108`.

## Sprinkler

Canonical:

```text
Y
N
Y13
Y(13R)
```

are valid.

Recognized alternatives may receive recommendations:

```text
YES
NO
SPRINKLERED
NOT SPRINKLERED
13R
Y 13
Y (13R)
```

Unknown:

```text
MAYBE
UNKNOWN
```

must require review.

## Negative monetary values

Must be detected.

Do not automatically change negative exposure values to zero.

## Future Year Built

Must be detected.

## Statistical outlier

Must be flagged as an anomaly, not automatically corrected.

## Missing values

Must remain missing unless a human-approved transformation later provides a justified value.

---

# 20. Suggested file structure after completion

```text
app/
└── agents/
    └── data_quality/
        ├── __init__.py
        ├── issue_schema.py
        ├── config.py
        ├── validator.py
        ├── field_validator.py
        ├── state_validator.py
        ├── zip_validator.py
        ├── monetary_validator.py
        ├── sprinkler_validator.py
        ├── statistical_validator.py
        ├── quality_aggregator.py
        ├── decision_policy.py
        ├── recommendation_engine.py
        ├── decision_schema.py
        ├── evidence_builder.py
        ├── reflection.py
        └── agent.py
```

Only create a new module when its responsibility is genuinely separate. Avoid creating unnecessary files.

---

# 21. Recommended implementation order

For every step, follow:

```text
1. Documentation
2. Code
3. Unit tests
4. Run tests
5. Integration test
6. Run full Agent 3 regression suite
7. Freeze the step
```

Do not implement multiple steps simultaneously.

The recommended order is:

### Step 3.6
Decision policy

### Step 3.7
Recommendation engine

### Step 3.8
Evidence builder / before-after representation

### Step 3.9
Pydantic decision contract

### Step 3.10
Reflection/reasoning loop

### Step 3.11
Agent 3 orchestrator

### Step 3.12
SOVState/LangGraph integration

### Step 3.13
Evaluation harness

### Step 3.14
End-to-end tests

### Step 3.15
Freeze

---

# 22. What NOT to do

Do not:
- rewrite working Agent 3 validators without a failing test;
- hard-code values from a particular sample workbook;
- automatically correct unknown values;
- let the LLM directly edit pandas DataFrames;
- use the LLM for deterministic validation;
- convert ZIP identifiers to integers;
- treat every statistical outlier as an error;
- create an unlimited reflection loop;
- allow arbitrary LLM operations;
- skip human approval for high-risk changes;
- send full raw SOV data to an external LLM unnecessarily;
- store row values in vector memory.

---

# 23. Definition of done for Agent 3

Agent 3 is complete when all of the following are true:

```text
[ ] Deterministic validation detects required anomalies
[ ] Statistical anomalies are detected separately
[ ] QualityIssue contract is stable
[ ] QualityReport is stable
[ ] Decision policy is deterministic
[ ] Recommendations are structured
[ ] Before/after values are explicit
[ ] Evidence is attached to every recommendation
[ ] Confidence and uncertainty are mandatory
[ ] High/Critical issues require human review
[ ] Unknown values are not automatically guessed
[ ] Reflection loop supports at most two retries
[ ] Rejected decisions are preserved
[ ] Repeated rejection escalates
[ ] Agent 3 does not modify the DataFrame
[ ] Agent 3 integrates with SOVState
[ ] Agent 3 output is suitable for Agent 4
[ ] Audit information is preserved
[ ] Unit tests pass
[ ] Integration tests pass
[ ] Regression suite passes
```

---

# 24. Final Agent 3 architecture

The completed architecture should be:

```text
                    ┌─────────────────────┐
                    │   Agent 2 Output    │
                    │ Schema Mapping      │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │ Deterministic       │
                    │ Validation          │
                    └──────────┬──────────┘
                               │
                ┌──────────────┼──────────────┐
                ▼              ▼              ▼
          Rule Checks     Semantic Checks   Statistical
          Missing        State/ZIP/etc.     Anomalies
          Types
          Range
          Category
                │              │              │
                └──────────────┼──────────────┘
                               ▼
                    ┌─────────────────────┐
                    │ Quality Aggregator  │
                    │ Score + Summary     │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │ Recommendation      │
                    │ Engine              │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │ LLM Reasoning       │
                    │ Only if Ambiguous   │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │ Human Review Gate   │
                    └──────────┬──────────┘
                               │
                    ┌──────────┴──────────┐
                    │                     │
                 APPROVE                REJECT
                    │                     │
                    ▼                     ▼
               Continue             Re-reason
                                          │
                                    max 2 attempts
                                          │
                              ┌───────────┴───────────┐
                              │                       │
                           RESOLVED               ESCALATED
                              │                       │
                              └───────────┬───────────┘
                                          ▼
                               Agent 3 Final Output
                                          │
                                          ▼
                                     Agent 4
                               Controlled Transform
```

---

# 25. Key principle for Claude

When implementing the remaining Agent 3 work:

> **Do not optimize for the number of features. Optimize for deterministic correctness, traceability, and safe human-controlled reasoning.**

The hackathon scoring explicitly rewards data-quality recall, agentic design, explainability, and human-in-the-loop behavior. Therefore, Agent 3 should demonstrate a clear separation:

```text
Deterministic rules
        ↓
Evidence
        ↓
Recommendation
        ↓
LLM reasoning only when needed
        ↓
Human approval
        ↓
Controlled downstream transformation
```

This is the intended architecture. Do not replace it with a generic "LLM checks the data" implementation.
"""

path = "/mnt/data/Agent3_remaining_approach.md"
Path(path).write_text(content, encoding="utf-8")
print(path)
