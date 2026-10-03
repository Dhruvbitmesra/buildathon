from unittest.mock import patch

from app.agents.schema_mapping.cross_encoder_reranker import (
    CrossEncoderRerankingResult,
    RerankedCandidate,
)
from app.agents.schema_mapping.embedding_retriever import (
    SemanticCandidate,
    SemanticRetrievalResult,
)
from app.agents.schema_mapping.semantic_pipeline import (
    run_semantic_pipeline,
)
from app.agents.schema_mapping.semantic_evaluator import (
    SemanticEvaluationResult,
)


def make_retrieval_result():
    candidates = [
        SemanticCandidate(
            target_field="Building Value",
            embedding_similarity=0.91,
            value_evidence_score=0.94,
            combined_score=0.918,
            matched_text="Building Value",
            evidence_reasons=[
                "Column contains monetary values."
            ],
        ),
        SemanticCandidate(
            target_field="Contents",
            embedding_similarity=0.83,
            value_evidence_score=0.94,
            combined_score=0.858,
            matched_text="Contents",
            evidence_reasons=[
                "Column contains monetary values."
            ],
        ),
        SemanticCandidate(
            target_field="Other",
            embedding_similarity=0.71,
            value_evidence_score=0.94,
            combined_score=0.768,
            matched_text="Other",
            evidence_reasons=[
                "Column contains monetary values."
            ],
        ),
    ]

    return SemanticRetrievalResult(
        source_header="Property Value",
        normalized_header="property value",
        candidates=candidates,
        model_name="BAAI/bge-small-en-v1.5",
    )


def make_reranking_result():
    candidates = [
        RerankedCandidate(
            target_field="Building Value",
            embedding_similarity=0.91,
            value_evidence_score=0.94,
            combined_score=0.918,
            cross_encoder_score=0.95,
            rerank_score=0.945,
            matched_text="Building Value",
            evidence_reasons=[
                "Column contains monetary values."
            ],
        ),
        RerankedCandidate(
            target_field="Contents",
            embedding_similarity=0.83,
            value_evidence_score=0.94,
            combined_score=0.858,
            cross_encoder_score=0.60,
            rerank_score=0.685,
            matched_text="Contents",
            evidence_reasons=[
                "Column contains monetary values."
            ],
        ),
        RerankedCandidate(
            target_field="Other",
            embedding_similarity=0.71,
            value_evidence_score=0.94,
            combined_score=0.768,
            cross_encoder_score=0.40,
            rerank_score=0.520,
            matched_text="Other",
            evidence_reasons=[
                "Column contains monetary values."
            ],
        ),
    ]

    return CrossEncoderRerankingResult(
        source_header="Property Value",
        normalized_header="property value",
        candidates=candidates,
        model_name="cross-encoder/ms-marco-MiniLM-L-6-v2",
    )


def test_pipeline_connects_retrieval_reranking_and_evaluation():

    retrieval = make_retrieval_result()
    reranking = make_reranking_result()

    with patch(
        "app.agents.schema_mapping.semantic_pipeline."
        "retrieve_semantic_candidates",
        return_value=retrieval,
    ), patch(
        "app.agents.schema_mapping.semantic_pipeline."
        "rerank_semantic_candidates",
        return_value=reranking,
    ):

        result = run_semantic_pipeline(
            source_header="Property Value"
        )

    assert result.source_header == "Property Value"
    assert result.retrieval == retrieval
    assert result.reranking == reranking

    assert result.evaluation is not None
    assert result.evaluation.top_candidate is not None

    assert (
        result.evaluation.top_candidate.target_field
        == "Building Value"
    )

    assert result.status == "strong"


def test_pipeline_uses_reranked_scores_for_evaluation():

    retrieval = make_retrieval_result()
    reranking = make_reranking_result()

    with patch(
        "app.agents.schema_mapping.semantic_pipeline."
        "retrieve_semantic_candidates",
        return_value=retrieval,
    ), patch(
        "app.agents.schema_mapping.semantic_pipeline."
        "rerank_semantic_candidates",
        return_value=reranking,
    ):

        result = run_semantic_pipeline(
            source_header="Property Value"
        )

    assert result.evaluation is not None

    top = result.evaluation.top_candidate

    assert top is not None

    assert top.target_field == "Building Value"

    assert top.combined_score == 0.945


def test_pipeline_handles_retrieval_failure():

    retrieval = SemanticRetrievalResult(
        source_header="Unknown",
        normalized_header="unknown",
        candidates=[],
        model_name="BAAI/bge-small-en-v1.5",
        error="Embedding model unavailable",
    )

    with patch(
        "app.agents.schema_mapping.semantic_pipeline."
        "retrieve_semantic_candidates",
        return_value=retrieval,
    ):

        result = run_semantic_pipeline(
            source_header="Unknown"
        )

    assert result.status == "unresolved"

    assert result.reranking is None
    assert result.evaluation is None

    assert len(result.errors) == 1
    assert "retrieval failed" in result.errors[0].lower()


def test_pipeline_handles_no_candidates():

    retrieval = SemanticRetrievalResult(
        source_header="Unknown",
        normalized_header="unknown",
        candidates=[],
        model_name="BAAI/bge-small-en-v1.5",
    )

    with patch(
        "app.agents.schema_mapping.semantic_pipeline."
        "retrieve_semantic_candidates",
        return_value=retrieval,
    ):

        result = run_semantic_pipeline(
            source_header="Unknown"
        )

    assert result.status == "unresolved"
    assert result.reranking is None
    assert result.evaluation is None

    assert "No semantic candidates" in result.errors[0]


def test_pipeline_records_cross_encoder_failure():

    retrieval = make_retrieval_result()

    reranking = make_reranking_result().model_copy(
        update={
            "error": "Cross-encoder unavailable",
        }
    )

    with patch(
        "app.agents.schema_mapping.semantic_pipeline."
        "retrieve_semantic_candidates",
        return_value=retrieval,
    ), patch(
        "app.agents.schema_mapping.semantic_pipeline."
        "rerank_semantic_candidates",
        return_value=reranking,
    ):

        result = run_semantic_pipeline(
            source_header="Property Value"
        )

    assert result.reranking is not None
    assert result.reranking.error == "Cross-encoder unavailable"

    assert len(result.errors) == 1
    assert "cross-encoder" in result.errors[0].lower()

    # Pipeline still evaluates the fallback candidates.
    assert result.evaluation is not None


def test_pipeline_accepts_custom_cross_encoder():

    retrieval = make_retrieval_result()
    reranking = make_reranking_result()

    with patch(
        "app.agents.schema_mapping.semantic_pipeline."
        "retrieve_semantic_candidates",
        return_value=retrieval,
    ), patch(
        "app.agents.schema_mapping.semantic_pipeline."
        "rerank_semantic_candidates",
        return_value=reranking,
    ) as mocked_rerank:

        run_semantic_pipeline(
            source_header="Property Value",
            cross_encoder_model_name="custom-model",
        )

    mocked_rerank.assert_called_once_with(
        retrieval_result=retrieval,
        model_name="custom-model",
    )