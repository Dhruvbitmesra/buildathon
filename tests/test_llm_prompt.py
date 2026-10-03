from app.agents.schema_mapping.llm_decision import (
    LLMDecisionContext,
)
from app.agents.schema_mapping.llm_prompt import (
    SYSTEM_PROMPT,
    build_llm_decision_context,
    build_llm_user_prompt,
)
from app.agents.schema_mapping.semantic_pipeline import (
    SemanticPipelineResult,
)
from app.agents.schema_mapping.embedding_retriever import (
    SemanticCandidate,
    SemanticRetrievalResult,
)


def make_pipeline_result():

    candidates = [
        SemanticCandidate(
            target_field="Building Value",
            embedding_similarity=0.91,
            value_evidence_score=0.94,
            combined_score=0.74,
            matched_text="Building Value",
            evidence_reasons=[
                "Column contains monetary values."
            ],
        ),
        SemanticCandidate(
            target_field="Contents",
            embedding_similarity=0.72,
            value_evidence_score=0.80,
            combined_score=0.51,
            matched_text="Contents",
            evidence_reasons=[
                "Column contains monetary values."
            ],
        ),
    ]

    retrieval = SemanticRetrievalResult(
        source_header="Bldg Repl Cost",
        normalized_header="bldg repl cost",
        candidates=candidates,
        model_name="BAAI/bge-small-en-v1.5",
    )

    return SemanticPipelineResult(
        source_header="Bldg Repl Cost",
        normalized_header="bldg repl cost",
        retrieval=retrieval,
        status="moderate",
    )


def test_system_prompt_contains_core_rules():

    assert "canonical SOV target field" in SYSTEM_PROMPT
    assert "Never invent a new target field" in SYSTEM_PROMPT
    assert "Do not fill missing values" in SYSTEM_PROMPT
    assert "human review" in SYSTEM_PROMPT.lower()


def test_build_llm_decision_context():

    result = make_pipeline_result()

    context = build_llm_decision_context(
        result,
        sample_values=[
            "$1,000,000",
            "$2,500,000",
            "$750,000",
            "$900,000",
            "$1,200,000",
            "$999,999",
        ],
    )

    assert isinstance(context, LLMDecisionContext)

    assert context.source_header == "Bldg Repl Cost"

    assert len(context.candidates) == 2

    assert (
        context.candidates[0]["target_field"]
        == "Building Value"
    )

    # Maximum five samples.
    assert len(context.sample_values) == 5


def test_candidate_scores_are_rounded():

    result = make_pipeline_result()

    context = build_llm_decision_context(result)

    candidate = context.candidates[0]

    assert candidate["score"] == 0.74
    assert candidate["embedding_similarity"] == 0.91
    assert candidate["value_evidence_score"] == 0.94


def test_user_prompt_contains_evidence():

    result = make_pipeline_result()

    context = build_llm_decision_context(
        result,
        sample_values=["$1,000,000"],
    )

    prompt = build_llm_user_prompt(context)

    assert "Bldg Repl Cost" in prompt
    assert "bldg repl cost" in prompt
    assert "Building Value" in prompt
    assert "$1,000,000" in prompt


def test_empty_samples_are_allowed():

    result = make_pipeline_result()

    context = build_llm_decision_context(
        result,
        sample_values=None,
    )

    assert context.sample_values == []


def test_only_five_samples_are_sent():

    result = make_pipeline_result()

    samples = [f"value_{i}" for i in range(20)]

    context = build_llm_decision_context(
        result,
        sample_values=samples,
    )

    assert len(context.sample_values) == 5
    assert context.sample_values == samples[:5]


def test_prompt_is_string():

    context = LLMDecisionContext(
        source_header="State",
        normalized_header="state",
        candidates=[],
        column_profile={},
        sample_values=[],
    )

    prompt = build_llm_user_prompt(context)

    assert isinstance(prompt, str)
    assert len(prompt) > 0