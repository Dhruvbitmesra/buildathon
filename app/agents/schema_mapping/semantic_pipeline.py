from typing import Optional

from pydantic import BaseModel, Field

from app.agents.schema_mapping.cross_encoder_reranker import (
    CrossEncoderRerankingResult,
    rerank_semantic_candidates,
)
from app.agents.schema_mapping.embedding_retriever import (
    SemanticRetrievalResult,
    retrieve_semantic_candidates,
)
from app.agents.schema_mapping.semantic_evaluator import (
    SemanticEvaluationResult,
    evaluate_semantic_candidates,
)
from app.state.sov_state import ColumnProfile


class SemanticPipelineResult(BaseModel):
    """Complete result of the semantic schema-matching pipeline."""

    source_header: str
    normalized_header: str

    retrieval: SemanticRetrievalResult
    reranking: Optional[CrossEncoderRerankingResult] = None
    evaluation: Optional[SemanticEvaluationResult] = None

    status: str = "unresolved"

    errors: list[str] = Field(default_factory=list)


def run_semantic_pipeline(
    source_header: str,
    profile: Optional[ColumnProfile] = None,
    assigned_fields: Optional[set[str]] = None,
    retrieval_top_k: int = 3,
    cross_encoder_model_name: Optional[str] = None,
) -> SemanticPipelineResult:
    """
    Run the complete semantic schema-matching pipeline.

    Pipeline:

        BGE Retrieval
             ↓
        Cross-Encoder Reranking
             ↓
        Semantic Evaluation

    The function does not make a final schema-mapping decision.
    """

    errors: list[str] = []

    # ---------------------------------------------------------
    # Step 1: BGE semantic retrieval
    # ---------------------------------------------------------

    retrieval = retrieve_semantic_candidates(
        source_header=source_header,
        profile=profile,
        assigned_fields=assigned_fields,
        top_k=retrieval_top_k,
    )

    if retrieval.error:
        errors.append(
            f"Semantic retrieval failed: {retrieval.error}"
        )

        return SemanticPipelineResult(
            source_header=retrieval.source_header,
            normalized_header=retrieval.normalized_header,
            retrieval=retrieval,
            reranking=None,
            evaluation=None,
            status="unresolved",
            errors=errors,
        )

    if not retrieval.candidates:
        return SemanticPipelineResult(
            source_header=retrieval.source_header,
            normalized_header=retrieval.normalized_header,
            retrieval=retrieval,
            reranking=None,
            evaluation=None,
            status="unresolved",
            errors=["No semantic candidates were retrieved."],
        )

    # ---------------------------------------------------------
    # Step 2: Cross-encoder reranking
    # ---------------------------------------------------------

    if cross_encoder_model_name is None:
        reranking = rerank_semantic_candidates(
            retrieval_result=retrieval,
        )
    else:
        reranking = rerank_semantic_candidates(
            retrieval_result=retrieval,
            model_name=cross_encoder_model_name,
        )

    if reranking.error:
        errors.append(
            f"Cross-encoder reranking failed: {reranking.error}"
        )

    # ---------------------------------------------------------
    # Step 3: Convert reranked candidates back into the
    # semantic candidate representation used by evaluation.
    # ---------------------------------------------------------

    evaluation_candidates = []

    for candidate in reranking.candidates:
        from app.agents.schema_mapping.embedding_retriever import (
            SemanticCandidate,
        )

        evaluation_candidates.append(
            SemanticCandidate(
                target_field=candidate.target_field,
                embedding_similarity=candidate.embedding_similarity,
                value_evidence_score=candidate.value_evidence_score,
                combined_score=candidate.rerank_score,
                matched_text=candidate.matched_text,
                evidence_reasons=candidate.evidence_reasons,
            )
        )

    evaluation_input = SemanticRetrievalResult(
        source_header=retrieval.source_header,
        normalized_header=retrieval.normalized_header,
        candidates=evaluation_candidates,
        model_name=retrieval.model_name,
        error=None,
    )

    # ---------------------------------------------------------
    # Step 4: Semantic evaluation
    # ---------------------------------------------------------

    evaluation = evaluate_semantic_candidates(
        retrieval_result=evaluation_input,
    )

    status = evaluation.category

    return SemanticPipelineResult(
        source_header=retrieval.source_header,
        normalized_header=retrieval.normalized_header,
        retrieval=retrieval,
        reranking=reranking,
        evaluation=evaluation,
        status=status,
        errors=errors,
    )