# STEP 02.24 — LLM Evidence Fusion

## 1. Objective

The purpose of this step is to correctly integrate the decision produced by the
LLM into the Agent 2 candidate-evidence system.

The LLM should not directly bypass the global assignment system.

Instead, its decision must become an explicit evidence signal that can be
combined with:

- deterministic matching
- domain aliases
- fuzzy matching
- value evidence
- embedding similarity
- cross-encoder evidence

The final candidate must then pass through the existing one-to-one global
assignment and minimum-score safety gate.

---

# 2. Problem Discovered in Step 2.23

The Agent 2 diagnostic showed that the LLM can correctly identify a target
field, but the LLM confidence was not always being transferred into the
candidate's `llm_score`.

For example:

```text
Source header:
Building

Sample values:
250000
120000
7316910