from functools import lru_cache
from typing import Optional

from pydantic import BaseModel, Field
from sentence_transformers import CrossEncoder

from app.agents.schema_mapping.embedding_retriever import (
    SemanticCandidate,
    SemanticRetrievalResult,
)
from app.agents.schema_mapping.target_schema import TARGET_FIELDS


DEFAULT_CROSS_ENCODER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"


class RerankedCandidate(BaseModel):
    """Candidate enriched with cross-encoder relevance."""

    target_field: str

    embedding_similarity: float
    value_evidence_score: float
    combined_score: float

    cross_encoder_score: float
    rerank_score: float

    matched_text: str
    evidence_reasons: list[str] = Field(default_factory=list)


class CrossEncoderRerankingResult(BaseModel):
    """Result of cross-encoder candidate reranking."""

    source_header: str
    normalized_header: str

    candidates: list[RerankedCandidate] = Field(
        default_factory=list
    )

    model_name: str

    error: Optional[str] = None


@lru_cache(maxsize=2)
def load_cross_encoder(
    model_name: str = DEFAULT_CROSS_ENCODER_MODEL,
) -> CrossEncoder:
    """Load and cache the cross-encoder model."""

    return CrossEncoder(model_name)


def _build_target_text(target_field_name: str) -> str:
    """Build semantic text describing a target field."""

    for field in TARGET_FIELDS:
        if field.name == target_field_name:
            aliases = ", ".join(field.aliases)

            return (
                f"Field: {field.name}. "
                f"Description: {field.description}. "
                f"Aliases: {aliases}."
            )

    return f"Field: {target_field_name}."


def _normalize_score(score: float) -> float:
    """
    Normalize a cross-encoder score to the range 0-1.

    MS MARCO-style cross-encoders can produce arbitrary logits.
    A sigmoid converts the raw score into a bounded relevance value.
    """

    import math

    score = float(score)

    try:
        return 1.0 / (1.0 + math.exp(-score))
    except OverflowError:
        return 0.0 if score < 0 else 1.0


def _build_rerank_score(
    cross_encoder_score: float,
    embedding_similarity: float,
    value_evidence_score: float,
) -> float:
    """
    Combine cross-encoder relevance with existing evidence.

    Cross-encoder receives the largest weight because this step
    exists specifically to refine semantic ranking.
    """

    score = (
        0.60 * cross_encoder_score
        + 0.25 * embedding_similarity
        + 0.15 * value_evidence_score
    )

    return round(
        max(0.0, min(1.0, score)),
        6,
    )


def rerank_semantic_candidates(
    retrieval_result: SemanticRetrievalResult,
    model_name: str = DEFAULT_CROSS_ENCODER_MODEL,
) -> CrossEncoderRerankingResult:
    """
    Rerank retrieved semantic candidates using a cross-encoder.

    If the cross-encoder fails, the original candidate information
    is returned in the same order with an error attached.
    """

    candidates = retrieval_result.candidates

    if not candidates:
        return CrossEncoderRerankingResult(
            source_header=retrieval_result.source_header,
            normalized_header=retrieval_result.normalized_header,
            candidates=[],
            model_name=model_name,
            error=retrieval_result.error,
        )

    try:
        model = load_cross_encoder(model_name)

        pairs = [
            (
                retrieval_result.source_header,
                _build_target_text(candidate.target_field),
            )
            for candidate in candidates
        ]

        raw_scores = model.predict(
            pairs,
            show_progress_bar=False,
        )

    except Exception as exc:
        fallback_candidates = [
            RerankedCandidate(
                target_field=candidate.target_field,
                embedding_similarity=candidate.embedding_similarity,
                value_evidence_score=candidate.value_evidence_score,
                combined_score=candidate.combined_score,
                cross_encoder_score=0.0,
                rerank_score=candidate.combined_score,
                matched_text=candidate.matched_text,
                evidence_reasons=candidate.evidence_reasons,
            )
            for candidate in candidates
        ]

        return CrossEncoderRerankingResult(
            source_header=retrieval_result.source_header,
            normalized_header=retrieval_result.normalized_header,
            candidates=fallback_candidates,
            model_name=model_name,
            error=str(exc),
        )

    reranked_candidates: list[RerankedCandidate] = []

    for candidate, raw_score in zip(
        candidates,
        raw_scores,
    ):
        cross_encoder_score = _normalize_score(
            float(raw_score)
        )

        rerank_score = _build_rerank_score(
            cross_encoder_score=cross_encoder_score,
            embedding_similarity=candidate.embedding_similarity,
            value_evidence_score=candidate.value_evidence_score,
        )

        reranked_candidates.append(
            RerankedCandidate(
                target_field=candidate.target_field,
                embedding_similarity=candidate.embedding_similarity,
                value_evidence_score=candidate.value_evidence_score,
                combined_score=candidate.combined_score,
                cross_encoder_score=round(
                    cross_encoder_score,
                    6,
                ),
                rerank_score=rerank_score,
                matched_text=candidate.matched_text,
                evidence_reasons=candidate.evidence_reasons,
            )
        )

    reranked_candidates.sort(
        key=lambda candidate: candidate.rerank_score,
        reverse=True,
    )

    return CrossEncoderRerankingResult(
        source_header=retrieval_result.source_header,
        normalized_header=retrieval_result.normalized_header,
        candidates=reranked_candidates,
        model_name=model_name,
        error=None,
    )