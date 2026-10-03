from dataclasses import dataclass
from typing import Optional

from app.agents.schema_mapping.groq_client import (
    GroqLLMClient,
)
from app.agents.schema_mapping.llm_decision import (
    LLMMappingDecision,
)
from app.agents.schema_mapping.llm_prompt import (
    build_llm_decision_context,
)
from app.agents.schema_mapping.semantic_pipeline import (
    SemanticPipelineResult,
)
from app.agents.schema_mapping.llm_decision import (
    LLMMappingDecision,
    validate_llm_decision,
)

@dataclass
class MappingDecisionResult:
    """
    Final schema-mapping decision produced by the decision engine.
    """

    source_header: str
    target_field: Optional[str]
    confidence: float
    method: str
    human_review_required: bool
    reason: str
    semantic_category: Optional[str] = None
    semantic_score: Optional[float] = None
    semantic_margin: Optional[float] = None
    llm_decision: Optional[LLMMappingDecision] = None


def _semantic_decision(
    pipeline_result: SemanticPipelineResult,
) -> MappingDecisionResult | None:
    """
    Resolve mappings that are sufficiently clear without using
    the LLM.
    """

    evaluation = pipeline_result.evaluation

    if evaluation is None:
        return None

    if evaluation.top_candidate is None:
        return None

    if evaluation.category not in {"strong", "moderate"}:
        return None

    return MappingDecisionResult(
        source_header=pipeline_result.source_header,
        target_field=evaluation.top_candidate.target_field,
        confidence=evaluation.top_score,
        method="semantic",
        human_review_required=False,
        reason=(
            "Semantic pipeline produced a sufficiently clear "
            "candidate without requiring LLM reasoning."
        ),
        semantic_category=evaluation.category,
        semantic_score=evaluation.top_score,
        semantic_margin=evaluation.score_margin,
    )


def resolve_mapping(
    pipeline_result: SemanticPipelineResult,
    sample_values: list[str] | None = None,
    llm_client: GroqLLMClient | None = None,
) -> MappingDecisionResult:
    """
    Resolve a source header using semantic evidence first and
    the LLM only when semantic evidence is insufficient.
    """

    semantic_result = _semantic_decision(
        pipeline_result
    )

    if semantic_result is not None:
        return semantic_result

    context = build_llm_decision_context(
        pipeline_result,
        sample_values=sample_values,
    )

    client = llm_client or GroqLLMClient()

    decision = client.decide(context)

    # Enforce the human-review policy at the orchestration
    # boundary as well as inside the LLM client.
    decision = validate_llm_decision(decision)

    return MappingDecisionResult(
        source_header=pipeline_result.source_header,
        target_field=decision.target_field,
        confidence=decision.confidence,
        method="llm",
        human_review_required=decision.human_review_required,
        reason=decision.reason,
        semantic_category=(
            pipeline_result.evaluation.category
            if pipeline_result.evaluation
            else None
        ),
        semantic_score=(
            pipeline_result.evaluation.top_score
            if pipeline_result.evaluation
            else None
        ),
        semantic_margin=(
            pipeline_result.evaluation.score_margin
            if pipeline_result.evaluation
            else None
        ),
        llm_decision=decision,
    )