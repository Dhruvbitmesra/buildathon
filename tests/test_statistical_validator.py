import pandas as pd
import pytest

from app.agents.data_quality.issue_schema import (
    IssueSeverity,
    IssueType,
)
from app.agents.data_quality.statistical_validator import (
    StatisticalAnomalyValidator,
)


FIELD = "Building Value"


@pytest.fixture
def validator():
    return StatisticalAnomalyValidator()


def test_validator_requires_dataframe(validator):
    with pytest.raises(TypeError):
        validator.validate(["not", "a", "dataframe"])


def test_missing_field_is_skipped(validator):
    df = pd.DataFrame({"Other Field": [1, 2, 3, 4, 5]})

    issues = validator.validate(df)

    assert issues == []


def test_small_sample_is_skipped(validator):
    df = pd.DataFrame(
        {
            FIELD: [100, 110, 120, 130]
        }
    )

    issues = validator.validate(df)

    assert issues == []


def test_normal_values_are_not_flagged(validator):
    df = pd.DataFrame(
        {
            FIELD: [
                100,
                105,
                110,
                115,
                120,
                125,
                130,
            ]
        }
    )

    issues = validator.validate(df)

    assert issues == []


def test_extreme_value_is_detected(validator):
    df = pd.DataFrame(
        {
            FIELD: [
                100,
                105,
                110,
                115,
                120,
                125,
                130,
                10000,
            ]
        }
    )

    issues = validator.validate(df)

    assert len(issues) >= 1

    issue = next(
        issue for issue in issues
        if issue.row_index == 7
    )

    assert issue.issue_type == IssueType.STATISTICAL_ANOMALY
    assert issue.source_field == FIELD
    assert issue.observed_value == 10000


def test_anomaly_contains_statistical_evidence(validator):
    df = pd.DataFrame(
        {
            FIELD: [
                100,
                105,
                110,
                115,
                120,
                125,
                130,
                10000,
            ]
        }
    )

    issues = validator.validate(df)

    issue = next(
        issue for issue in issues
        if issue.row_index == 7
    )

    assert "methods" in issue.evidence
    assert "sample_size" in issue.evidence
    assert "q1" in issue.evidence
    assert "q3" in issue.evidence
    assert "iqr" in issue.evidence
    assert "modified_z_score" in issue.evidence


def test_missing_values_are_ignored(validator):
    df = pd.DataFrame(
        {
            FIELD: [
                100,
                110,
                None,
                120,
                130,
                140,
            ]
        }
    )

    issues = validator.validate(df)

    assert all(issue.observed_value is not None for issue in issues)


def test_multiple_statistical_fields_are_checked(validator):
    df = pd.DataFrame(
        {
            "Building Value": [
                100,
                110,
                120,
                130,
                140,
                150,
                10000,
            ],
            "Contents": [
                50,
                55,
                60,
                65,
                70,
                75,
                5000,
            ],
        }
    )

    issues = validator.validate(df)

    fields = {issue.source_field for issue in issues}

    assert "Building Value" in fields
    assert "Contents" in fields


def test_validator_does_not_modify_dataframe(validator):
    df = pd.DataFrame(
        {
            FIELD: [
                100,
                105,
                110,
                115,
                120,
                125,
                10000,
            ]
        }
    )

    original = df.copy(deep=True)

    validator.validate(df)

    pd.testing.assert_frame_equal(df, original)