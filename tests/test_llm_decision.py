import pytest
from pydantic import ValidationError

from app.agents.schema_mapping.llm_decision import (
    LLMDecisionContext,
    LLMMappingDecision,
    validate_llm_decision,
)


def test_valid_building_value_decision():

    decision = LLMMappingDecision(
        target_field="Building Value",
        confidence=0.91,
        reason=(
            "The header indicates a property value and "
            "the column contains monetary values."
        ),
        human_review_required=False,
    )

    validated = validate_llm_decision(decision)

    assert validated.target_field == "Building Value"
    assert validated.confidence == 0.91
    assert validated.human_review_required is False


def test_valid_null_decision_requires_review():

    decision = LLMMappingDecision(
        target_field=None,
        confidence=0.30,
        reason="The available evidence is insufficient.",
        human_review_required=False,
    )

    validated = validate_llm_decision(decision)

    assert validated.target_field is None
    assert validated.human_review_required is True


def test_low_confidence_requires_review():

    decision = LLMMappingDecision(
        target_field="Building Value",
        confidence=0.40,
        reason="Some evidence supports this field.",
        human_review_required=False,
    )

    validated = validate_llm_decision(decision)

    assert validated.human_review_required is True


def test_confidence_zero_is_valid():

    decision = LLMMappingDecision(
        target_field=None,
        confidence=0.0,
        reason="No useful evidence was found.",
    )

    validated = validate_llm_decision(decision)

    assert validated.confidence == 0.0
    assert validated.human_review_required is True


def test_confidence_one_is_valid():

    decision = LLMMappingDecision(
        target_field="State",
        confidence=1.0,
        reason="The header exactly identifies the state field.",
    )

    validated = validate_llm_decision(decision)

    assert validated.confidence == 1.0


def test_invalid_target_field_is_rejected():

    with pytest.raises(ValidationError):

        LLMMappingDecision(
            target_field="Premium Amount",
            confidence=0.90,
            reason="Invalid field.",
        )


def test_confidence_above_one_is_rejected():

    with pytest.raises(ValidationError):

        LLMMappingDecision(
            target_field="Building Value",
            confidence=1.10,
            reason="Invalid confidence.",
        )


def test_confidence_below_zero_is_rejected():

    with pytest.raises(ValidationError):

        LLMMappingDecision(
            target_field="Building Value",
            confidence=-0.10,
            reason="Invalid confidence.",
        )


def test_extra_fields_are_rejected():

    with pytest.raises(ValidationError):

        LLMMappingDecision(
            target_field="Building Value",
            confidence=0.90,
            reason="Valid mapping.",
            unexpected_field="should fail",
        )


def test_decision_context():

    context = LLMDecisionContext(
        source_header="Bldg Repl Cost",
        normalized_header="bldg repl cost",
        candidates=[
            {
                "target_field": "Building Value",
                "score": 0.74,
            },
            {
                "target_field": "BI",
                "score": 0.13,
            },
        ],
        column_profile={
            "numeric_ratio": 1.0,
            "currency_ratio": 0.98,
        },
        sample_values=[
            "1000000",
            "2500000",
        ],
    )

    assert context.source_header == "Bldg Repl Cost"
    assert len(context.candidates) == 2
    assert len(context.sample_values) == 2