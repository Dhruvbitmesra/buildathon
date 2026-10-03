
from app.agents.schema_mapping.decision_engine import (
    MappingDecisionResult,
    resolve_mapping,
)
from app.agents.schema_mapping.llm_decision import (
    LLMMappingDecision,
)
from app.agents.schema_mapping.semantic_pipeline import (
    SemanticPipelineResult,
)
from app.agents.schema_mapping.embedding_retriever import (
    SemanticCandidate,
    SemanticRetrievalResult,
)

from app.agents.schema_mapping.semantic_evaluator import (
    SemanticEvaluationResult,
)

class FakeLLMClient:

    def __init__(self, decision):

        self.decision = decision
        self.called = False

    def decide(self, context):

        self.called = True

        return self.decision


def make_pipeline(
    category="strong",
    top_field="Building Value",
    top_score=0.74,
    margin=0.60,
):

    candidates = [
        SemanticCandidate(
            target_field=top_field,
            embedding_similarity=0.82,
            value_evidence_score=0.95,
            combined_score=top_score,
            matched_text=top_field,
            evidence_reasons=[
                "Monetary values detected."
            ],
        ),
        SemanticCandidate(
            target_field="Contents",
            embedding_similarity=0.61,
            value_evidence_score=0.80,
            combined_score=0.51,
            matched_text="Contents",
            evidence_reasons=[],
        ),
    ]

    retrieval = SemanticRetrievalResult(
        source_header="Bldg Repl Cost",
        normalized_header="bldg repl cost",
        candidates=candidates,
        model_name="BAAI/bge-small-en-v1.5",
    )

    top_candidate = candidates[0]

    second_candidate = candidates[1]

    evaluation = SemanticEvaluationResult(
        source_header="Bldg Repl Cost",
        normalized_header="bldg repl cost",
        candidates=candidates,
        top_candidate=top_candidate,
        second_candidate=second_candidate,
        top_score=top_score,
        second_score=0.51,
        score_margin=margin,
        category=category,
        evidence_summary=[
            "Monetary values detected."
        ],
    )

    return SemanticPipelineResult(
        source_header="Bldg Repl Cost",
        normalized_header="bldg repl cost",
        retrieval=retrieval,
        evaluation=evaluation,
        status=category,
    )


def test_strong_semantic_result_skips_llm():

    pipeline = make_pipeline(
        category="strong",
    )

    fake_llm = FakeLLMClient(
        LLMMappingDecision(
            target_field="Contents",
            confidence=0.99,
            reason="Should never be called.",
        )
    )

    result = resolve_mapping(
        pipeline,
        llm_client=fake_llm,
    )

    assert isinstance(
        result,
        MappingDecisionResult,
    )

    assert result.target_field == "Building Value"
    assert result.method == "semantic"
    assert result.human_review_required is False
    assert fake_llm.called is False


def test_moderate_semantic_result_skips_llm():

    pipeline = make_pipeline(
        category="moderate",
        top_score=0.68,
        margin=0.30,
    )

    fake_llm = FakeLLMClient(
        LLMMappingDecision(
            target_field="Contents",
            confidence=0.99,
            reason="Should never be called.",
        )
    )

    result = resolve_mapping(
        pipeline,
        llm_client=fake_llm,
    )

    assert result.target_field == "Building Value"
    assert result.method == "semantic"
    assert fake_llm.called is False


def test_ambiguous_result_uses_llm():

    pipeline = make_pipeline(
        category="ambiguous",
        top_score=0.56,
        margin=0.04,
    )

    fake_llm = FakeLLMClient(
        LLMMappingDecision(
            target_field="Building Value",
            confidence=0.91,
            reason="The header and monetary values indicate "
                   "building replacement cost.",
        )
    )

    result = resolve_mapping(
        pipeline,
        sample_values=[
            "1000000",
            "2500000",
        ],
        llm_client=fake_llm,
    )

    assert result.target_field == "Building Value"
    assert result.method == "llm"
    assert result.confidence == 0.91
    assert result.human_review_required is False
    assert result.llm_decision is not None
    assert fake_llm.called is True


def test_weak_result_uses_llm():

    pipeline = make_pipeline(
        category="weak",
        top_score=0.31,
        margin=0.02,
    )

    fake_llm = FakeLLMClient(
        LLMMappingDecision(
            target_field=None,
            confidence=0.31,
            reason="Insufficient evidence.",
        )
    )

    result = resolve_mapping(
        pipeline,
        llm_client=fake_llm,
    )

    assert result.target_field is None
    assert result.method == "llm"
    assert result.human_review_required is True
    assert fake_llm.called is True


def test_llm_review_flag_is_preserved():

    pipeline = make_pipeline(
        category="ambiguous",
        top_score=0.55,
        margin=0.03,
    )

    fake_llm = FakeLLMClient(
        LLMMappingDecision(
            target_field="Building Value",
            confidence=0.48,
            reason="Evidence is insufficient.",
            human_review_required=True,
        )
    )

    result = resolve_mapping(
        pipeline,
        llm_client=fake_llm,
    )

    assert result.target_field == "Building Value"
    assert result.method == "llm"
    assert result.human_review_required is True
    assert result.confidence == 0.48