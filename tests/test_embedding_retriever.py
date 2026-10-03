import numpy as np
import pandas as pd

from app.agents.schema_mapping.embedding_retriever import (
    DEFAULT_MODEL_NAME,
    TOP_K,
    SemanticCandidate,
    _build_target_text,
    _cosine_similarity,
    _normalize_similarity,
    retrieve_semantic_candidates,
)
from app.agents.schema_mapping.target_schema import TARGET_FIELDS
from app.agents.schema_mapping.value_profiler import profile_column


def test_default_model_name():
    assert DEFAULT_MODEL_NAME == "BAAI/bge-small-en-v1.5"


def test_top_k():
    assert TOP_K == 3


def test_target_text_contains_schema_information():
    field = next(
        field
        for field in TARGET_FIELDS
        if field.name == "Building Value"
    )

    text = _build_target_text(field)

    assert "Building Value" in text
    assert field.description in text


def test_similarity_for_identical_normalized_vectors():
    source = np.array([1.0, 0.0, 0.0])

    targets = np.array(
        [
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
        ]
    )

    similarities = _cosine_similarity(
        source,
        targets,
    )

    assert np.isclose(similarities[0], 1.0)
    assert np.isclose(similarities[1], 0.0)


def test_similarity_is_normalized():
    assert _normalize_similarity(-0.5) == 0.0
    assert _normalize_similarity(0.5) == 0.5
    assert _normalize_similarity(1.5) == 1.0


def test_empty_header_returns_no_candidates():
    result = retrieve_semantic_candidates("")

    assert result.candidates == []
    assert result.error is None


def test_none_header_returns_no_candidates():
    result = retrieve_semantic_candidates(None)

    assert result.candidates == []
    assert result.error is None


def test_semantic_candidate_model():
    candidate = SemanticCandidate(
        target_field="Building Value",
        embedding_similarity=0.9,
        value_evidence_score=0.8,
        combined_score=0.875,
        matched_text="Building Value",
    )

    assert candidate.target_field == "Building Value"
    assert 0.0 <= candidate.combined_score <= 1.0


def test_retrieval_returns_top_three():
    profile = profile_column(
        "Unknown",
        pd.Series(
            [
                "$100000",
                "$200000",
                "$300000",
            ]
        ),
    )

    result = retrieve_semantic_candidates(
        "property value",
        profile=profile,
        top_k=3,
    )

    assert result.error is None
    assert len(result.candidates) <= 3


def test_candidates_are_sorted():
    profile = profile_column(
        "Unknown",
        pd.Series(
            [
                "$100000",
                "$200000",
                "$300000",
            ]
        ),
    )

    result = retrieve_semantic_candidates(
        "property value",
        profile=profile,
        top_k=3,
    )

    scores = [
        candidate.combined_score
        for candidate in result.candidates
    ]

    assert scores == sorted(
        scores,
        reverse=True,
    )


def test_assigned_fields_are_excluded():
    profile = profile_column(
        "Unknown",
        pd.Series(
            [
                "$100000",
                "$200000",
            ]
        ),
    )

    result = retrieve_semantic_candidates(
        "property value",
        profile=profile,
        assigned_fields={"Building Value"},
        top_k=3,
    )

    assert all(
        candidate.target_field != "Building Value"
        for candidate in result.candidates
    )


def test_value_evidence_is_included():
    profile = profile_column(
        "Unknown",
        pd.Series(
            [
                "Y",
                "N",
                "Y13",
                "Y(13R)",
            ]
        ),
    )

    result = retrieve_semantic_candidates(
        "sprinkler protection",
        profile=profile,
        top_k=3,
    )

    sprinkler_candidate = next(
        (
            candidate
            for candidate in result.candidates
            if candidate.target_field
            == "Fire Sprinklers (Y/N)"
        ),
        None,
    )

    assert sprinkler_candidate is not None
    assert sprinkler_candidate.value_evidence_score == 1.0


def test_result_contains_normalized_header():
    profile = profile_column(
        "Unknown",
        pd.Series(["Office", "Retail"]),
    )

    result = retrieve_semantic_candidates(
        "  Property Occupancy  ",
        profile=profile,
        top_k=3,
    )

    assert result.normalized_header == "property occupancy"