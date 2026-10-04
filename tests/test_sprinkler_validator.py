import pandas as pd
import pytest

from app.agents.data_quality.issue_schema import IssueType
from app.agents.data_quality.sprinkler_validator import (
    SprinklerSemanticValidator,
)


FIELD = "Fire Sprinklers (Y/N)"


@pytest.fixture
def validator():
    return SprinklerSemanticValidator()


def test_canonical_y_is_valid(validator):
    df = pd.DataFrame({FIELD: ["Y"]})

    assert validator.validate(df) == []


def test_canonical_n_is_valid(validator):
    df = pd.DataFrame({FIELD: ["N"]})

    assert validator.validate(df) == []


def test_canonical_y13_is_valid(validator):
    df = pd.DataFrame({FIELD: ["Y13"]})

    assert validator.validate(df) == []


def test_canonical_y13r_is_valid(validator):
    df = pd.DataFrame({FIELD: ["Y(13R)"]})

    assert validator.validate(df) == []


def test_yes_is_detected_as_alternate(validator):
    df = pd.DataFrame({FIELD: ["Yes"]})

    issues = validator.validate(df)

    assert len(issues) == 1
    assert issues[0].issue_type == IssueType.INVALID_CATEGORY
    assert issues[0].evidence["candidate_canonical_value"] == "Y"


def test_no_is_detected_as_alternate(validator):
    df = pd.DataFrame({FIELD: ["No"]})

    issues = validator.validate(df)

    assert len(issues) == 1
    assert issues[0].evidence["candidate_canonical_value"] == "N"


def test_sprinklered_is_detected_as_alternate(validator):
    df = pd.DataFrame({FIELD: ["Sprinklered"]})

    issues = validator.validate(df)

    assert len(issues) == 1
    assert issues[0].evidence["candidate_canonical_value"] == "Y"


def test_not_sprinklered_is_detected_as_alternate(validator):
    df = pd.DataFrame({FIELD: ["Not Sprinklered"]})

    issues = validator.validate(df)

    assert len(issues) == 1
    assert issues[0].evidence["candidate_canonical_value"] == "N"


def test_unknown_sprinkler_value_requires_review(validator):
    df = pd.DataFrame({FIELD: ["Maybe"]})

    issues = validator.validate(df)

    assert len(issues) == 1
    assert issues[0].severity.value == "high"
    assert issues[0].evidence["candidate_canonical_value"] \
        if "candidate_canonical_value" in issues[0].evidence else True


def test_missing_sprinkler_value_is_skipped(validator):
    df = pd.DataFrame({FIELD: [None]})

    assert validator.validate(df) == []


def test_validator_does_not_modify_dataframe(validator):
    df = pd.DataFrame({
        FIELD: ["Y", "Yes", "Maybe"],
    })

    original = df.copy(deep=True)

    validator.validate(df)

    pd.testing.assert_frame_equal(df, original)