"""Level 1: contract, decision policy and recommendation engine."""

import pandas as pd
import pytest
from pydantic import ValidationError

from app.agents.data_quality.decision_policy import DecisionPolicy
from app.agents.data_quality.issue_schema import IssueSeverity, IssueType
from app.agents.data_quality.normalizers import Operation
from app.agents.data_quality.recommendation_engine import RecommendationEngine
from app.agents.data_quality.recommendation_schema import (
    ActionType,
    Evidence,
    ReasoningSource,
    Recommendation,
    ReviewAction,
    ReviewDecision,
    ReviewPolicy,
)
from app.agents.data_quality.validator import DeterministicValidator


YEAR = 2026


def make_rec(**overrides) -> Recommendation:
    data = dict(
        recommendation_id="REC-1",
        action_type=ActionType.STANDARDISATION,
        operation=Operation.STANDARDISE_STATE,
        target_field="State",
        rule_id="state_non_canonical",
        severity=IssueSeverity.LOW,
        affected_rows=[0],
        affected_row_count=1,
        before_value="Texas",
        after_value="TX",
        title="t",
        rationale="r",
        uncertainty="u",
        evidence=Evidence(rule_id="state_non_canonical", expected_condition="c"),
        detection_confidence=1.0,
        fix_confidence=0.97,
        lossless=True,
    )
    data.update(overrides)
    return Recommendation(**data)


def build(frame, mappings=None):
    issues = DeterministicValidator().validate_sov(frame, current_year=YEAR)
    return RecommendationEngine().build(
        issues, frame, mappings=mappings, current_year=YEAR
    )


def find(recs, **criteria):
    matches = [
        rec
        for rec in recs
        if all(getattr(rec, key) == value for key, value in criteria.items())
    ]
    assert matches, f"no recommendation matching {criteria}"
    return matches[0]


# ---------------------------------------------------------------------
# Contract
# ---------------------------------------------------------------------


def test_confidence_must_be_between_zero_and_one():
    with pytest.raises(ValidationError):
        make_rec(fix_confidence=1.5)


def test_rationale_and_uncertainty_are_mandatory():
    with pytest.raises(ValidationError):
        make_rec(rationale="")

    with pytest.raises(ValidationError):
        make_rec(uncertainty="")


def test_flag_for_review_cannot_change_values():
    with pytest.raises(ValidationError):
        make_rec(action_type=ActionType.FLAG_FOR_REVIEW)


def test_set_blank_cannot_carry_a_value():
    with pytest.raises(ValidationError):
        make_rec(
            action_type=ActionType.DATA_CORRECTION,
            operation=Operation.SET_BLANK,
            after_value=0,
        )


def test_every_recommendation_requires_human_approval():
    assert make_rec().requires_human_approval is True


def test_rejection_requires_reason():
    with pytest.raises(ValidationError):
        ReviewAction(recommendation_id="R", decision=ReviewDecision.REJECT, reviewer="a")

    with pytest.raises(ValidationError):
        ReviewAction(
            recommendation_id="R", decision=ReviewDecision.REJECT, reviewer="a", reason="  "
        )


def test_edit_requires_value():
    with pytest.raises(ValidationError):
        ReviewAction(recommendation_id="R", decision=ReviewDecision.EDIT, reviewer="a")

    action = ReviewAction(
        recommendation_id="R", decision=ReviewDecision.EDIT, reviewer="a", edited_value=None
    )
    assert action.edited_value is None


# ---------------------------------------------------------------------
# Decision policy
# ---------------------------------------------------------------------


def test_lossless_high_confidence_standardisation_is_bulk_approvable():
    policy, _ = DecisionPolicy().evaluate(make_rec())

    assert policy == ReviewPolicy.BULK_APPROVABLE


@pytest.mark.parametrize(
    "overrides",
    [
        {"severity": IssueSeverity.HIGH},
        {"severity": IssueSeverity.CRITICAL},
        {"fix_confidence": 0.6},
        {"lossless": False},
        {"action_type": ActionType.DATA_CORRECTION},
        {"reasoning_source": ReasoningSource.LLM},
        {"attempt": 2},
    ],
)
def test_risky_recommendations_need_individual_review(overrides):
    policy, reasons = DecisionPolicy().evaluate(make_rec(**overrides))

    assert policy == ReviewPolicy.HUMAN_REVIEW_REQUIRED
    assert reasons


def test_high_severity_with_high_confidence_still_needs_review():
    policy, _ = DecisionPolicy().evaluate(
        make_rec(severity=IssueSeverity.HIGH, fix_confidence=0.99)
    )

    assert policy == ReviewPolicy.HUMAN_REVIEW_REQUIRED


# ---------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------


def test_same_alias_is_grouped_into_one_recommendation():
    frame = pd.DataFrame({"Fire Sprinklers (Y/N)": ["YES"] * 40 + ["Yes"] * 2 + ["NO"]})
    recs = build(frame)

    yes = find(recs, after_value="Y")
    assert yes.affected_row_count == 42
    assert yes.action_type == ActionType.STANDARDISATION
    assert yes.policy == ReviewPolicy.BULK_APPROVABLE
    assert find(recs, after_value="N").affected_row_count == 1


def test_unknown_sprinkler_is_flagged_never_guessed():
    rec = find(build(pd.DataFrame({"Fire Sprinklers (Y/N)": ["MAYBE", "Y"]})),
               issue_type=IssueType.INVALID_CATEGORY)

    assert rec.action_type == ActionType.FLAG_FOR_REVIEW
    assert rec.operation == Operation.KEEP
    assert rec.after_value == "MAYBE"
    assert rec.policy == ReviewPolicy.HUMAN_REVIEW_REQUIRED


def test_negative_building_value_is_never_zeroed():
    rec = find(build(pd.DataFrame({"Building Value": [100.0, -500000.0]})),
               issue_type=IssueType.NEGATIVE_VALUE)

    assert rec.operation == Operation.KEEP
    assert rec.after_value == -500000.0


def test_missing_values_stay_missing():
    rec = find(build(pd.DataFrame({"Address": ["1 Main St", None]})),
               issue_type=IssueType.MISSING_VALUE)

    assert rec.operation == Operation.KEEP
    assert rec.after_value is None


def test_statistical_outlier_is_flagged_not_corrected():
    frame = pd.DataFrame({"Building Value": [100e3, 120e3, 110e3, 115e3, 105e3, 125e3, 25e9]})
    rec = find(build(frame), issue_type=IssueType.STATISTICAL_ANOMALY)

    assert rec.operation == Operation.KEEP
    assert rec.evidence.statistical_context


def test_numeric_sprinkler_is_a_data_correction_not_bulk():
    rec = find(build(pd.DataFrame({"Fire Sprinklers (Y/N)": [0.0, 1.0, 0.0]})), after_value="N")

    assert rec.action_type == ActionType.DATA_CORRECTION
    assert rec.policy == ReviewPolicy.HUMAN_REVIEW_REQUIRED
    assert rec.operation_params == {"scale": 1.0}


def test_negative_amount_written_as_text_is_a_negative_value():
    # "-$500" is detected as what it is: a negative insured value.
    rec = find(build(pd.DataFrame({"Building Value": ["-$500"]})), target_field="Building Value")

    assert rec.issue_type == IssueType.NEGATIVE_VALUE
    assert rec.severity == IssueSeverity.HIGH
    assert rec.action_type == ActionType.FLAG_FOR_REVIEW


def test_converted_value_that_still_fails_is_flagged():
    # Safety net: a format issue whose conversion would still break a
    # rule is downgraded to a flag, never offered as a fix.
    from app.agents.data_quality.issue_schema import QualityIssue

    issue = QualityIssue(
        issue_id="x",
        row_index=0,
        source_field="Building Value",
        target_field="Building Value",
        issue_type=IssueType.FORMAT_INCONSISTENCY,
        severity=IssueSeverity.LOW,
        observed_value="(500)",
        expected_condition="c",
        confidence=1.0,
        uncertainty="u",
    )
    frame = pd.DataFrame({"Building Value": ["(500)"]})

    rec = RecommendationEngine().build([issue], frame, current_year=YEAR)[0]

    assert rec.action_type == ActionType.FLAG_FOR_REVIEW
    assert "still fail" in rec.uncertainty


def test_before_after_samples_are_explicit():
    rec = find(build(pd.DataFrame({"Building Value": ["$1,200,000", "1.2M"]})),
               operation=Operation.PARSE_MONETARY)

    assert [(s.before, s.after) for s in rec.samples] == [
        ("$1,200,000", 1200000.0),
        ("1.2M", 1200000.0),
    ]


def test_every_recommendation_has_rationale_and_evidence():
    frame = pd.DataFrame(
        {
            "Reference": ["A", "A", None],
            "Zip": ["2108", "ABCDE", 75219.0],
            "Building Value": ["$1M", -1, "TBD"],
            "Year Built": [2099, 9999, "1985"],
            "Fire Sprinklers (Y/N)": ["YES", "MAYBE", 0.57],
        }
    )

    for rec in build(frame):
        assert rec.rationale.strip()
        assert rec.uncertainty.strip()
        assert rec.evidence.rule_id
        assert 0.0 <= rec.fix_confidence <= 1.0


def test_recommendation_ids_are_stable_across_runs():
    frame = pd.DataFrame({"State": ["Texas", "XX"], "Building Value": [-1, 5]})

    first = [rec.recommendation_id for rec in build(frame)]
    second = [rec.recommendation_id for rec in build(frame)]

    assert first == second


def test_column_mappings_become_recommendations():
    recs = build(
        pd.DataFrame({"Reference": ["A"]}),
        mappings=[
            {"source_header": "Bldg Repl Cost", "target_field": "Building Value",
             "score": 0.91, "method": "semantic"},
            {"source_header": "Fire Prot.", "target_field": "Fire Sprinklers (Y/N)",
             "score": 0.6, "method": "semantic"},
            {"source_header": "Unresolved_Col_7", "target_field": None, "score": 0.31},
        ],
    )

    high = find(recs, source_column="Bldg Repl Cost")
    low = find(recs, source_column="Fire Prot.")
    unmapped = find(recs, source_column="Unresolved_Col_7")

    assert high.action_type == ActionType.COLUMN_MAPPING
    assert high.policy == ReviewPolicy.BULK_APPROVABLE
    assert low.policy == ReviewPolicy.HUMAN_REVIEW_REQUIRED
    assert unmapped.action_type == ActionType.FLAG_FOR_REVIEW
    assert recs[0].action_type == ActionType.COLUMN_MAPPING


def test_queue_is_ordered_by_severity():
    frame = pd.DataFrame({"State": ["Texas"], "Building Value": [-1.0]})
    severities = [rec.severity for rec in build(frame) if rec.target_field in {"State", "Building Value"}]

    assert severities[0] == IssueSeverity.HIGH
    assert severities[-1] == IssueSeverity.LOW
