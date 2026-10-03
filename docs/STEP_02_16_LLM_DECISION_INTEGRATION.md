# Step 2.16 — LLM Decision Integration

## Objective

Integrate the validated semantic schema-mapping pipeline with
the Groq LLM reasoning layer.

The LLM is used only when deterministic and semantic evidence
does not produce a sufficiently clear mapping.

---

## Decision Policy

```text
Semantic Evaluation
        |
        +-- Strong ------> Semantic decision
        |
        +-- Moderate ----> Semantic decision
        |
        +-- Ambiguous ---> LLM reasoning
        |
        +-- Weak --------> LLM reasoning