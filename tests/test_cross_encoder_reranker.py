from unittest.mock import patch

from app.agents.schema_mapping.cross_encoder_reranker import (
    _build_rerank_score,
    _normalize_score,
    rerank_semantic_candidates,
)
from app.agents.schema_mapping.embedding_retriever import (
    SemanticCandidate,
    SemanticRetrievalResult,
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


def test_normalize_score():

    assert _normalize_score(0.0) == 0.5
    assert _normalize_score(10.0) > 0.99
    assert _normalize_score(-10.0) < 0.01


def test_rerank_score_is_bounded():

    score = _build_rerank_score(
        cross_encoder_score=1.0,
        embedding_similarity=1.0,
        value_evidence_score=1.0,
    )

    assert score == 1.0


def test_rerank_score_uses_all_evidence():

    score = _build_rerank_score(
        cross_encoder_score=0.8,
        embedding_similarity=0.6,
        value_evidence_score=0.4,
    )

    expected = (
        0.60 * 0.8
        + 0.25 * 0.6
        + 0.15 * 0.4
    )

    assert score == round(expected, 6)


def test_cross_encoder_reranks_candidates():

    candidates = [
        make_candidate(
            "Building Value",
            0.90,
            0.80,
            0.875,
        ),
        make_candidate(
            "Contents",
            0.88,
            0.80,
            0.860,
        ),
        make_candidate(
            "Other",
            0.70,
            0.80,
            0.725,
        ),
    ]

    fake_model = type(
        "FakeCrossEncoder",
        (),
        {
            "predict": lambda self, pairs, show_progress_bar=False: [
                0.2,
                2.0,
                0.1,
            ]
        },
    )()

    retrieval_result = SemanticRetrievalResult(
        source_header="Property Value",
        normalized_header="property value",
        candidates=candidates,
        model_name="BAAI/bge-small-en-v1.5",
    )

    with patch(
        "app.agents.schema_mapping.cross_encoder_reranker.load_cross_encoder",
        return_value=fake_model,
    ):

        result = rerank_semantic_candidates(
            retrieval_result
        )

    assert result.error is None
    assert len(result.candidates) == 3

    assert result.candidates[0].target_field == "Contents"


def test_cross_encoder_preserves_candidate_information():

    candidate = make_candidate(
        "Building Value",
        0.91,
        0.94,
        0.918,
    )

    fake_model = type(
        "FakeCrossEncoder",
        (),
        {
            "predict": lambda self, pairs, show_progress_bar=False: [
                1.0
            ]
        },
    )()

    retrieval_result = SemanticRetrievalResult(
        source_header="Property Value",
        normalized_header="property value",
        candidates=[candidate],
        model_name="BAAI/bge-small-en-v1.5",
    )

    with patch(
        "app.agents.schema_mapping.cross_encoder_reranker.load_cross_encoder",
        return_value=fake_model,
    ):

        result = rerank_semantic_candidates(
            retrieval_result
        )

    reranked = result.candidates[0]

    assert reranked.target_field == "Building Value"
    assert reranked.embedding_similarity == 0.91
    assert reranked.value_evidence_score == 0.94
    assert reranked.combined_score == 0.918
    assert reranked.cross_encoder_score > 0.7
    assert reranked.rerank_score > 0.0


def test_empty_candidates():

    retrieval_result = SemanticRetrievalResult(
        source_header="Unknown",
        normalized_header="unknown",
        candidates=[],
        model_name="BAAI/bge-small-en-v1.5",
    )

    result = rerank_semantic_candidates(
        retrieval_result
    )

    assert result.candidates == []
    assert result.error is None


def test_cross_encoder_failure_gracefully_degrades():

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

    retrieval_result = SemanticRetrievalResult(
        source_header="Property Value",
        normalized_header="property value",
        candidates=candidates,
        model_name="BAAI/bge-small-en-v1.5",
    )

    with patch(
        "app.agents.schema_mapping.cross_encoder_reranker.load_cross_encoder",
        side_effect=RuntimeError("Model unavailable"),
    ):

        result = rerank_semantic_candidates(
            retrieval_result
        )

    assert result.error == "Model unavailable"

    assert len(result.candidates) == 2

    assert (
        result.candidates[0].target_field
        == "Building Value"
    )

    assert (
        result.candidates[1].target_field
        == "Contents"
    )

    assert (
        result.candidates[0].rerank_score
        == 0.90
    )


def test_cross_encoder_pairs_use_header_and_target_description():

    candidate = make_candidate(
        "Building Value",
        0.90,
        0.90,
        0.90,
    )

    captured_pairs = []

    fake_model = type(
        "FakeCrossEncoder",
        (),
        {
            "predict": lambda self, pairs, show_progress_bar=False: (
                captured_pairs.extend(pairs) or [1.0]
            )
        },
    )()

    retrieval_result = SemanticRetrievalResult(
        source_header="Bldg Repl Cost",
        normalized_header="bldg repl cost",
        candidates=[candidate],
        model_name="BAAI/bge-small-en-v1.5",
    )

    with patch(
        "app.agents.schema_mapping.cross_encoder_reranker.load_cross_encoder",
        return_value=fake_model,
    ):

        rerank_semantic_candidates(
            retrieval_result
        )

    assert len(captured_pairs) == 1

    source_text, target_text = captured_pairs[0]

    assert source_text == "Bldg Repl Cost"
    assert "Building Value" in target_text
    assert "Description" in target_text