# Step 2.14 — LLM Evidence & Prompt Builder

## Objective

Convert the output of the semantic schema-matching pipeline into
a controlled evidence package for the LLM.

The LLM should reason from evidence rather than receiving the
entire SOV dataset.

---

## Pipeline

```text
Semantic Pipeline
      ↓
Evidence Builder
      ↓
Validated LLM Context
      ↓
Prompt
      ↓
Groq
      ↓
openai/gpt-oss-120b