from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.agents.schema_mapping.target_schema import (
    TARGET_FIELDS,
)


TARGET_FIELD_NAMES = {
    field.name
    for field in TARGET_FIELDS
}


class LLMMappingDecision(BaseModel):
    """
    Structured decision returned by the LLM for an ambiguous
    schema-mapping case.
    """

    model_config = ConfigDict(extra="forbid")

    target_field: Optional[str] = None

    confidence: float = Field(
        ge=0.0,
        le=1.0,
    )

    reason: str = Field(
        min_length=1,
    )

    human_review_required: bool = False

    @field_validator("confidence", mode="before")
    @classmethod
    def coerce_verbal_confidence(cls, value):
        """
        Models sometimes answer "high" instead of a number. Map the
        common words conservatively instead of failing the column.
        """

        if isinstance(value, str):
            verbal = {"high": 0.85, "medium": 0.6, "low": 0.3}
            text = value.strip().lower()

            if text in verbal:
                return verbal[text]

        return value

    @field_validator("target_field")
    @classmethod
    def validate_target_field(
        cls,
        value: Optional[str],
    ) -> Optional[str]:
        """
        Ensure the LLM can only select one of the canonical
        target fields or null.
        """

        if value is None:
            return None

        if value not in TARGET_FIELD_NAMES:
            raise ValueError(
                f"Invalid target field: {value!r}. "
                "The value must be one of the canonical "
                "SOV target fields or null."
            )

        return value


class LLMDecisionContext(BaseModel):
    """
    Evidence package that can be supplied to the LLM.

    This object intentionally contains metadata/evidence rather
    than raw SOV rows.
    """

    model_config = ConfigDict(extra="forbid")

    source_header: str

    normalized_header: str

    candidates: list[dict] = Field(
        default_factory=list,
    )

    column_profile: dict = Field(
        default_factory=dict,
    )

    sample_values: list[str] = Field(
        default_factory=list,
    )


def validate_llm_decision(
    decision: LLMMappingDecision,
) -> LLMMappingDecision:
    """
    Validate business-level constraints on an LLM decision.

    A high-confidence decision can proceed without human review.
    A null mapping or lower-confidence result requires review.
    """

    if decision.target_field is None:
        decision.human_review_required = True

    if decision.confidence < 0.50:
        decision.human_review_required = True

    return decision