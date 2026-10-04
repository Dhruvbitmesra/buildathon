from app.agents.schema_mapping.llm_decision import (
    LLMDecisionContext,
)
from app.agents.schema_mapping.semantic_pipeline import (
    SemanticPipelineResult,
)


SYSTEM_PROMPT = """
You are an insurance SOV schema-mapping reasoning agent.

Your task is to map an ambiguous source column header to exactly
one canonical SOV target field or null.

You must reason only from the evidence provided.

Rules:

1. Select only from the provided canonical target fields.
2. Never invent a new target field.
3. If evidence is insufficient, return null.
4. Do not modify or transform source data.
5. Do not fill missing values.
6. Use the column profile and candidate evidence when available.
7. Prefer evidence from the header meaning and value profile.
8. Do not treat model scores as probabilities.
9. If the evidence is ambiguous, require human review.
10. Return the requested structured JSON fields only.
""".strip()


def _candidate_to_dict(candidate) -> dict:
    """Convert a semantic candidate into LLM-safe evidence."""

    return {
        "target_field": candidate.target_field,
        "score": round(candidate.combined_score, 6),
        "embedding_similarity": round(
            candidate.embedding_similarity,
            6,
        ),
        "value_evidence_score": round(
            candidate.value_evidence_score,
            6,
        ),
        "evidence_reasons": candidate.evidence_reasons,
    }


def mask_sample(value: object) -> str:
    """
    Replace letters/digits with a/A/9 in values that may identify a
    person, company or address: three or more words, or two or more
    words containing a digit. Short codes and single words are kept
    ("TX", "Y", "1985", "Masonry"), so the model still sees the column's
    kind of content.

        "505 Gentry Memorial Hwy"     -> "999 Aaaaaa Aaaaaaaa Aaa"
        "Sonae Client A Portugal SA"  -> "Aaaaa Aaaaaa A Aaaaaaaa AA"
    """

    text = str(value)
    words = text.split()
    sensitive = len(words) >= 3 or (
        len(words) >= 2 and any(ch.isdigit() for ch in text)
    )

    if not sensitive:
        return text

    return "".join(
        "9" if ch.isdigit() else "A" if ch.isupper() else "a" if ch.isalpha() else ch
        for ch in text
    )


def build_llm_decision_context(
    pipeline_result: SemanticPipelineResult,
    sample_values: list[str] | None = None,
) -> LLMDecisionContext:
    """
    Build a controlled evidence package for the LLM.

    The semantic retrieval candidates are the primary evidence.
    Evaluation metadata is used separately by the pipeline and
    is not required to construct the LLM context.
    """

    candidates = [
        _candidate_to_dict(candidate)
        for candidate in pipeline_result.retrieval.candidates
    ]

    column_profile = {}

    if pipeline_result.retrieval.candidates:
        top_candidate = pipeline_result.retrieval.candidates[0]

        column_profile = {
            "top_target_field": top_candidate.target_field,
            "top_embedding_similarity": round(
                top_candidate.embedding_similarity,
                6,
            ),
            "top_value_evidence_score": round(
                top_candidate.value_evidence_score,
                6,
            ),
        }

    # Never send more than five explicitly supplied samples, and send
    # only the shape of values that could identify a person, company or
    # address.
    safe_samples = [mask_sample(value) for value in list(sample_values or [])[:5]]

    return LLMDecisionContext(
        source_header=pipeline_result.source_header,
        normalized_header=pipeline_result.normalized_header,
        candidates=candidates,
        column_profile=column_profile,
        sample_values=safe_samples,
    )


def build_llm_user_prompt(
    context: LLMDecisionContext,
) -> str:
    """
    Build the user prompt from the validated evidence context.
    """

    return f"""
Determine the canonical SOV field for this source column.

SOURCE HEADER:
{context.source_header}

NORMALIZED HEADER:
{context.normalized_header}

CANDIDATE EVIDENCE:
{context.candidates}

COLUMN EVIDENCE:
{context.column_profile}

MASKED SAMPLE VALUES:
{context.sample_values}

Return a structured decision containing:

- target_field
- confidence
- reason
- human_review_required
""".strip()