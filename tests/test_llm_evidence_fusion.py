from app.agents.schema_mapping.agent import SchemaMappingAgent


def test_llm_confidence_is_preserved_as_llm_score():
    candidates = [
        {
            "target_field": "Building Value",
            "score": 0.0,
            "embedding_similarity": 0.60,
            "value_evidence_score": 1.0,
            "fuzzy_score": 0.0,
            "deterministic_score": 0.0,
            "semantic_score": 0.0,
            "llm_score": 0.92,
            "evidence_reasons": [
                "LLM identified Building Value."
            ],
            "method": "llm",
        }
    ]

    result = SchemaMappingAgent._merge_candidates(
        candidates
    )

    assert len(result) == 1

    candidate = result[0]

    assert candidate["target_field"] == "Building Value"
    assert candidate["llm_score"] == 0.92


def test_llm_and_value_evidence_are_fused():
    candidates = [
        {
            "target_field": "Building Value",
            "score": 0.0,
            "embedding_similarity": 0.0,
            "value_evidence_score": 1.0,
            "fuzzy_score": 0.0,
            "deterministic_score": 0.0,
            "semantic_score": 0.0,
            "llm_score": 0.92,
            "evidence_reasons": [
                "LLM identified Building Value."
            ],
            "method": "llm",
        }
    ]

    result = SchemaMappingAgent._merge_candidates(
        candidates
    )

    candidate = result[0]

    expected_score = (
        0.80 * 0.92
        + 0.20 * 1.00
    )

    assert abs(
        candidate["score"] - expected_score
    ) < 1e-6


def test_value_only_evidence_remains_below_assignment_threshold():
    candidates = [
        {
            "target_field": "Building Value",
            "score": 1.0,
            "embedding_similarity": 0.0,
            "value_evidence_score": 1.0,
            "fuzzy_score": 0.0,
            "deterministic_score": 0.0,
            "semantic_score": 0.0,
            "llm_score": 0.0,
            "evidence_reasons": [
                "Column is predominantly numeric."
            ],
            "method": "value_evidence",
        }
    ]

    result = SchemaMappingAgent._merge_candidates(
        candidates
    )

    candidate = result[0]

    assert candidate["score"] <= 0.49


def test_llm_without_value_evidence_still_uses_llm_confidence():
    candidates = [
        {
            "target_field": "BI",
            "score": 0.0,
            "embedding_similarity": 0.0,
            "value_evidence_score": 0.0,
            "fuzzy_score": 0.0,
            "deterministic_score": 0.0,
            "semantic_score": 0.0,
            "llm_score": 0.85,
            "evidence_reasons": [
                "LLM identified BI."
            ],
            "method": "llm",
        }
    ]

    result = SchemaMappingAgent._merge_candidates(
        candidates
    )

    candidate = result[0]

    expected_score = 0.80 * 0.85

    assert abs(
        candidate["score"] - expected_score
    ) < 1e-6