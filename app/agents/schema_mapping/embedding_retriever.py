from functools import lru_cache
from typing import Optional

import numpy as np
from pydantic import BaseModel, Field
from sentence_transformers import SentenceTransformer

from app.agents.schema_mapping.header_normalizer import normalize_header
from app.agents.schema_mapping.target_schema import TARGET_FIELDS
from app.agents.schema_mapping.field_evidence import (
    FieldEvidence,
    score_field_evidence,
)
from app.state.sov_state import ColumnProfile


DEFAULT_MODEL_NAME = "BAAI/bge-small-en-v1.5"
TOP_K = 3


class SemanticCandidate(BaseModel):
    target_field: str
    embedding_similarity: float
    value_evidence_score: float = 0.0
    combined_score: float = 0.0
    matched_text: str
    evidence_reasons: list[str] = Field(default_factory=list)


class SemanticRetrievalResult(BaseModel):
    source_header: str
    normalized_header: str
    candidates: list[SemanticCandidate] = Field(
        default_factory=list
    )
    model_name: str
    error: Optional[str] = None


def _build_target_text(field) -> str:
    """
    Build the semantic representation of one canonical target field.

    Only schema-level information is embedded.
    """

    aliases = ", ".join(field.aliases)

    return (
        f"Field: {field.name}. "
        f"Description: {field.description}. "
        f"Aliases: {aliases}."
    )


@lru_cache(maxsize=1)
def load_embedding_model(
    model_name: str = DEFAULT_MODEL_NAME,
) -> SentenceTransformer:
    """
    Load the local sentence-transformer model once and cache it.
    """

    return SentenceTransformer(model_name)


def _normalize_similarity(
    similarity: float,
) -> float:
    return max(
        0.0,
        min(1.0, float(similarity)),
    )


# Target-schema embeddings never change for a given model; encoding
# them once per process instead of once per source column removes most
# of Agent 2's per-column cost.
_TARGET_EMBEDDING_CACHE: dict[int, tuple[list[str], np.ndarray]] = {}


def _build_target_embeddings(
    model: SentenceTransformer,
) -> tuple[list[str], np.ndarray]:
    """
    Build (or reuse) embeddings for the canonical target schema.

    Returns:

        target field names
        normalized embedding matrix
    """

    cached = _TARGET_EMBEDDING_CACHE.get(id(model))

    if cached is not None:
        return cached

    target_names: list[str] = []

    target_texts: list[str] = []

    for field in TARGET_FIELDS:
        target_names.append(field.name)
        target_texts.append(
            _build_target_text(field)
        )

    embeddings = model.encode(
        target_texts,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )

    _TARGET_EMBEDDING_CACHE[id(model)] = (target_names, embeddings)

    return target_names, embeddings


def _cosine_similarity(
    source_embedding: np.ndarray,
    target_embeddings: np.ndarray,
) -> np.ndarray:
    """
    Calculate cosine similarity between one source embedding and
    all target embeddings.

    Embeddings are normalized, so the dot product is cosine similarity.
    """

    return np.dot(
        target_embeddings,
        source_embedding,
    )


def _build_value_evidence_lookup(
    profile: Optional[ColumnProfile],
) -> dict[str, FieldEvidence]:
    if profile is None:
        return {}

    return {
        evidence.target_field: evidence
        for evidence in score_field_evidence(profile)
    }


def retrieve_semantic_candidates(
    source_header: object,
    profile: Optional[ColumnProfile] = None,
    assigned_fields: Optional[set[str]] = None,
    top_k: int = TOP_K,
    model_name: str = DEFAULT_MODEL_NAME,
) -> SemanticRetrievalResult:
    """
    Retrieve semantic target-field candidates for an unresolved
    source header.

    The result contains at most top_k canonical target fields.
    """

    source_text = (
        ""
        if source_header is None
        else str(source_header)
    )

    normalized_header = normalize_header(
        source_header
    )

    result = SemanticRetrievalResult(
        source_header=source_text,
        normalized_header=normalized_header,
        model_name=model_name,
    )

    if not normalized_header:
        return result

    assigned_fields = assigned_fields or set()

    try:
        model = load_embedding_model(
            model_name
        )

        target_names, target_embeddings = (
            _build_target_embeddings(model)
        )

        source_embedding = model.encode(
            [normalized_header],
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )[0]

        similarities = _cosine_similarity(
            source_embedding,
            target_embeddings,
        )

    except Exception as exc:
        return result.model_copy(
            update={
                "error": str(exc),
            }
        )

    value_evidence = _build_value_evidence_lookup(
        profile
    )

    candidates: list[SemanticCandidate] = []

    for index, target_field in enumerate(target_names):
        if target_field in assigned_fields:
            continue

        embedding_similarity = _normalize_similarity(
            similarities[index]
        )

        evidence = value_evidence.get(
            target_field
        )

        evidence_score = (
            evidence.score
            if evidence is not None
            else 0.0
        )

        reasons = (
            evidence.reasons
            if evidence is not None
            else []
        )

        # Semantic similarity remains the dominant signal.
        # Value evidence provides supporting information.
        combined_score = (
            0.75 * embedding_similarity
            + 0.25 * evidence_score
        )

        candidates.append(
            SemanticCandidate(
                target_field=target_field,
                embedding_similarity=embedding_similarity,
                value_evidence_score=evidence_score,
                combined_score=_normalize_similarity(
                    combined_score
                ),
                matched_text=target_field,
                evidence_reasons=reasons,
            )
        )

    candidates.sort(
        key=lambda candidate: candidate.combined_score,
        reverse=True,
    )

    result.candidates = candidates[:top_k]

    return result