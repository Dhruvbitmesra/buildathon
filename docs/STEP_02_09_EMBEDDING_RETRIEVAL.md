# Step 2.9 — Semantic Embedding Retrieval

## 1. Purpose

Fuzzy matching compares the lexical similarity of headers.

However, two headers may have similar meanings while using very
different words.

Semantic embeddings provide a second form of evidence based on the
meaning of the text.

---

## 2. Position in the Pipeline

The schema mapping pipeline is:

    Source Header
        ↓
    Normalization
        ↓
    Exact Matching
        ↓
    Domain Alias Matching
        ↓
    Fuzzy Matching
        ↓
    Column Value Profiling
        ↓
    Field-Specific Evidence
        ↓
    Semantic Embeddings
        ↓
    Top-3 Candidates
        ↓
    Cross-Encoder Reranking
        ↓
    LLM Reasoning
        ↓
    Human Review

---

## 3. Embedding Model

The semantic retrieval layer uses a local BGE-small style
sentence-transformer model.

The model runs locally rather than sending source headers to an
external embedding API.

This supports the project's privacy requirement.

---

## 4. What Is Embedded

The retrieval vocabulary contains:

- Canonical target field names
- Target field descriptions
- Approved domain aliases

The system should create a semantic representation of the target
schema rather than embedding raw SOV rows.

---

## 5. Candidate Retrieval

For an unresolved source header:

1. Normalize the header.
2. Create its embedding.
3. Compare it with the target vocabulary embeddings.
4. Calculate cosine similarity.
5. Aggregate candidates belonging to the same canonical target field.
6. Incorporate field-specific value evidence.
7. Return the top three target-field candidates.

The embedding layer does not make the final mapping decision.

---

## 6. Value Evidence

Semantic similarity is combined with the value profile.

For example:

    Source:
        "Property Value"

    Semantic candidates:
        Building Value
        Contents
        Other

If the column profile is strongly numeric and currency-like, the
value evidence increases the relevance of monetary target fields.

---

## 7. Candidate Count

The retrieval stage returns at most:

    Top 3

canonical target-field candidates.

These candidates are passed to later stages.

---

## 8. Confidence

Embedding similarity is represented on a 0–1 scale.

However, embedding similarity must not automatically be treated as a
probability.

The result is evidence for downstream reasoning.

---

## 9. Local Processing

The embedding model operates locally.

No complete source SOV rows are sent to the embedding model as
semantic memory.

The semantic index contains schema information rather than customer
row data.

---

## 10. No Dataset-Specific Hardcoding

The embedding retrieval layer must not contain rules such as:

    "Bldg Repl Cost New" -> "Building Value"

Specific source headers are allowed as test cases, but they must not
be embedded as special-case production logic.

---

## 11. Graceful Degradation

If the embedding model cannot be loaded:

- Do not crash the complete mapping system.
- Return an explicit retrieval error/state.
- Allow the workflow to continue using earlier deterministic
  evidence or escalate to a later fallback.

---

## 12. Definition of Done

Step 2.9 is complete when:

- The embedding dependency is installed.
- A local embedding model can be loaded.
- Target schema text can be embedded.
- Source headers can be embedded.
- Cosine similarity can be calculated.
- Top-3 target candidates can be retrieved.
- Value evidence can be incorporated.
- No raw SOV rows are stored in the semantic index.
- Unit tests pass.