# Step 2.11 — Cross-Encoder Reranking

## Objective

Improve semantic schema matching by reranking the top candidates
returned by the BGE embedding retrieval layer.

---

## Why Cross-Encoder?

The embedding model performs independent encoding:

```text
Source Header → embedding
Target Field  → embedding