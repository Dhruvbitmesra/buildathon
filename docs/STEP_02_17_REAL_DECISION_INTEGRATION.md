# Step 2.17 — Real Decision-Engine Integration

## Objective

Validate the complete schema-mapping decision pipeline using
real embedding, reranking, semantic evaluation, and LLM
components.

---

## Full Pipeline

```text
Source Header
     ↓
BGE Embedding Retrieval
     ↓
Cross-Encoder Reranking
     ↓
Semantic Evaluation
     ↓
Decision Engine
     │
     ├── Strong / Moderate
     │       ↓
     │   Semantic Decision
     │
     └── Ambiguous / Weak
             ↓
        LLM Evidence Context
             ↓
        Groq API
             ↓
        openai/gpt-oss-120b
             ↓
        Pydantic Validation
             ↓
        Final Decision