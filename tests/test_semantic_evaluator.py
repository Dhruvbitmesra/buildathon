from app.agents.schema_mapping.embedding_retriever import (
    SemanticCandidate,
    SemanticRetrievalResult,
)
from app.agents.schema_mapping.semantic_evaluator import (
    evaluate_semantic_candidates,
)


def make_candidate(
    target_field: str,
    embedding_similarity: float,
    value_evidence_score: float,
    combined_score: float,
) -> SemanticCandidate:
    return SemanticCandidate(
        target_field=target_field,
        embedding_similarity=embedding_similarity,
        value_evidence_score=value_evidence_score,
        combined_score=combined_score,
        matched_text=target_field,
        evidence_reasons=[
            f"Evidence supports {target_field}."
        ],
    )


def test_strong_semantic_candidate():

    candidates = [
        make_candidate(
            "Building Value",
            0.91,
            0.94,
            0.918,
        ),
        make_candidate(
            "Contents",
            0.83,
            0.94,
            0.858,
        ),
        make_candidate(
            "Other",
            0.71,
            0.94,
            0.768,
        ),
    ]

    result = evaluate_semantic_candidates(
        SemanticRetrievalResult(
            source_header="Property Value",
            normalized_header="property value",
            candidates=candidates,
            model_name="BAAI/bge-small-en-v1.5",
        )
    )

    assert result.top_candidate is not None
    assert result.top_candidate.target_field == "Building Value"

    assert result.second_candidate is not None
    assert result.second_candidate.target_field == "Contents"

    assert result.top_score == 0.918
    assert result.second_score == 0.858

    assert result.score_margin == 0.060

    # This test represents the old BGE combined-score scale.
    # The score is high, but the margin is below the strong
    # reranking threshold.
    assert result.category == "ambiguous"


def test_strong_candidate_with_large_margin():

    candidates = [
        make_candidate(
            "Building Value",
            0.95,
            0.96,
            0.953,
        ),
        make_candidate(
            "Contents",
            0.62,
            0.80,
            0.665,
        ),
    ]

    result = evaluate_semantic_candidates(
        SemanticRetrievalResult(
            source_header="Building Replacement Cost",
            normalized_header="building replacement cost",
            candidates=candidates,
            model_name="BAAI/bge-small-en-v1.5",
        )
    )

    assert result.top_candidate.target_field == "Building Value"
    assert result.category == "strong"
    assert result.score_margin > 0.20


def test_moderate_candidate():

    candidates = [
        make_candidate(
            "State",
            0.80,
            0.80,
            0.696,
        ),
        make_candidate(
            "Country",
            0.40,
            0.40,
            0.156,
        ),
    ]

    result = evaluate_semantic_candidates(
        SemanticRetrievalResult(
            source_header="State",
            normalized_header="state",
            candidates=candidates,
            model_name="BAAI/bge-small-en-v1.5",
        )
    )

    assert result.category == "moderate"


def test_ambiguous_candidates():

    candidates = [
        make_candidate(
            "Building Value",
            0.86,
            0.90,
            0.564,
        ),
        make_candidate(
            "Construction",
            0.84,
            0.89,
            0.525,
        ),
    ]

    result = evaluate_semantic_candidates(
        SemanticRetrievalResult(
            source_header="Building",
            normalized_header="building",
            candidates=candidates,
            model_name="BAAI/bge-small-en-v1.5",
        )
    )

    assert result.category == "ambiguous"
    assert result.score_margin < 0.08


def test_weak_candidate():

    candidates = [
        make_candidate(
            "Other",
            0.51,
            0.45,
            0.495,
        ),
        make_candidate(
            "Contents",
            0.48,
            0.40,
            0.460,
        ),
    ]

    result = evaluate_semantic_candidates(
        SemanticRetrievalResult(
            source_header="Unknown Property Field",
            normalized_header="unknown property field",
            candidates=candidates,
            model_name="BAAI/bge-small-en-v1.5",
        )
    )

    assert result.category == "weak"


def test_unresolved_when_no_candidates():

    result = evaluate_semantic_candidates(
        SemanticRetrievalResult(
            source_header="Unknown",
            normalized_header="unknown",
            candidates=[],
            model_name="BAAI/bge-small-en-v1.5",
        )
    )

    assert result.top_candidate is None
    assert result.second_candidate is None

    assert result.top_score == 0.0
    assert result.second_score == 0.0
    assert result.score_margin == 0.0

    assert result.category == "unresolved"


def test_unresolved_when_retrieval_failed():

    result = evaluate_semantic_candidates(
        SemanticRetrievalResult(
            source_header="Building Value",
            normalized_header="building value",
            candidates=[],
            model_name="BAAI/bge-small-en-v1.5",
            error="Embedding model failed to load.",
        )
    )

    assert result.category == "unresolved"
    assert result.retrieval_error == "Embedding model failed to load."

    assert any(
        "No semantic candidate" in reason
        for reason in result.evidence_summary
    )


def test_evidence_summary_contains_candidate_information():

    candidates = [
        make_candidate(
            "Year Built",
            0.93,
            0.98,
            0.943,
        ),
        make_candidate(
            "Storeys",
            0.70,
            0.50,
            0.650,
        ),
    ]

    result = evaluate_semantic_candidates(
        SemanticRetrievalResult(
            source_header="Construction Year",
            normalized_header="construction year",
            candidates=candidates,
            model_name="BAAI/bge-small-en-v1.5",
        )
    )

    summary = "\n".join(result.evidence_summary)

    assert "Year Built" in summary
    assert "Storeys" in summary
    assert "Embedding similarity" in summary
    assert "Value evidence score" in summary
    assert "Candidate margin" in summary


def test_candidate_order_is_preserved():

    candidates = [
        make_candidate(
            "Building Value",
            0.90,
            0.90,
            0.90,
        ),
        make_candidate(
            "Contents",
            0.80,
            0.80,
            0.80,
        ),
    ]

    result = evaluate_semantic_candidates(
        SemanticRetrievalResult(
            source_header="Property Value",
            normalized_header="property value",
            candidates=candidates,
            model_name="BAAI/bge-small-en-v1.5",
        )
    )

    assert result.candidates[0].target_field == "Building Value"
    assert result.candidates[1].target_field == "Contents"