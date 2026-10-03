# Step 2.10 — Semantic Candidate Evaluation

## Objective

Evaluate the candidates produced by semantic retrieval and later
reranking.

The evaluator does not directly approve a schema mapping.

It determines the strength and ambiguity of the available evidence.

---

## Evidence

The evaluation considers:

1. Candidate score
2. Score separation from the second candidate
3. Embedding similarity
4. Value evidence
5. Evidence reasons

---

## Candidate Categories

The evaluation policy uses both absolute score and candidate margin.

### Strong

```text
score >= 0.70
AND
margin >= 0.20