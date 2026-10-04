# Step 3.1 — Agent 3 Foundation

## Purpose

Agent 3 is the Data Quality & Reasoning agent.

Its responsibility is to inspect the mapped SOV data, identify data-quality
issues and anomalies, explain why they matter, and produce evidence-backed
recommendations for human approval.

Agent 3 does not directly modify the source data.

All transformations are deferred to Agent 4.

---

## Position in the Pipeline

Agent 1
Sheet Discovery
        ↓
Agent 2
Schema Intelligence
        ↓
Agent 3
Data Quality & Reasoning
        ↓
Human Approval
        ↓
Agent 4
Controlled Transformation

---

## Core Principle

Deterministic validation happens before LLM reasoning.

The LLM must not replace deterministic validation.

The pipeline is:

1. Read mapped data
2. Run deterministic validation rules
3. Profile affected columns
4. Detect anomalies
5. Generate evidence
6. Ask the LLM for recommendations only where reasoning is useful
7. Produce structured recommendations
8. Send recommendations to human approval
9. Re-reason after rejection when appropriate
10. Escalate after the maximum retry count

---

## Agent 3 Responsibilities

Agent 3 must:

- validate field types
- detect missing values
- detect invalid values
- detect negative monetary values
- detect invalid categorical values
- detect impossible years
- detect invalid building/storey counts
- detect invalid sprinkler values
- detect duplicates
- detect statistical anomalies
- explain detected issues
- recommend possible actions
- provide confidence
- provide uncertainty
- provide before/after examples where applicable

Agent 3 must not:

- directly overwrite source data
- silently fill missing values
- invent values
- modify the workbook
- bypass human approval
- allow the LLM to override deterministic validation

---

## Validation Layers

### Layer 1 — Structural Validation

Check:

- expected columns
- duplicate columns
- missing columns
- unexpected columns
- row count
- column count
- data types

### Layer 2 — Field-Level Validation

Each target field has its own validation rules.

Examples:

Building Value:
- numeric
- non-negative
- currency-compatible

Storeys:
- integer-compatible
- >= 1

Number of Buildings:
- integer-compatible
- >= 1

Year Built:
- integer-compatible
- not greater than current year

Fire Sprinklers:
- allowed values only:
  - Y
  - N
  - Y13
  - Y(13R)

### Layer 3 — Statistical Validation

Use statistical evidence where appropriate.

Examples:

- IQR-based outlier detection
- MAD-based robust anomaly detection
- distribution profiling
- uniqueness
- missingness
- zero-rate
- range checks

Statistical anomalies are evidence, not automatic errors.

---

## Layer 4 — Cross-Field Validation

Detect contradictions between fields.

Examples:

Year Built > current year

Number of Buildings < 1

Storeys < 1

Potentially inconsistent monetary relationships

Duplicate Reference values

Cross-field checks should produce evidence rather than automatically
changing data.

---

## Issue Representation

Every detected issue should contain:

- source field
- target field
- row identifier
- issue type
- severity
- observed value
- expected condition
- evidence
- recommendation
- confidence
- uncertainty
- status

Suggested issue statuses:

- detected
- recommended
- approved
- rejected
- escalated
- resolved

---

## LLM Role

The LLM is used only after deterministic evidence has been collected.

The LLM receives:

- field name
- issue type
- deterministic validation results
- statistical evidence
- masked sample values
- relevant domain constraints

The LLM must return structured JSON.

The LLM must not:

- invent replacement values
- fill blanks without evidence
- change schema
- modify source data
- approve its own recommendation

---

## Human-in-the-Loop

Every proposed corrective operation must be reviewable.

The reviewer should see:

1. detected issue
2. evidence
3. proposed action
4. before value
5. proposed after value
6. confidence
7. uncertainty
8. rationale

The reviewer can:

- approve
- reject
- request re-reasoning

Rejected recommendations can be reconsidered up to two times.

After the retry limit, the issue is escalated.

---

## Output

Agent 3 produces a structured quality report.

Example:

{
    "field": "Year Built",
    "issue_type": "future_year",
    "row": 12,
    "observed_value": 2035,
    "severity": "high",
    "recommendation": null,
    "confidence": 0.99,
    "uncertainty": "No valid replacement value available",
    "status": "human_review_required"
}

Agent 3 does not apply the recommendation.

Agent 4 is responsible for applying only human-approved operations.

---

## Design Principle

Agent 3 is an investigation and reasoning layer.

It is not a cleaning script.

The system should prefer:

detect → explain → recommend → approve → transform

over:

detect → automatically modify