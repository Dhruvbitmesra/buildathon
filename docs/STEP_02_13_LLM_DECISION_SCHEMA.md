# Step 2.13 — LLM Decision Schema

## Objective

Define a strict, validated contract for LLM-based schema mapping.

The LLM is used only after deterministic and local semantic
methods have produced evidence.

---

## LLM Input

The eventual LLM context can contain:

- source header
- normalized header
- semantic candidates
- candidate scores
- value-profile evidence
- limited masked sample values

Raw SOV rows are not sent to the LLM.

---

## LLM Output

The LLM must return:

```text
target_field
confidence
reason
human_review_required