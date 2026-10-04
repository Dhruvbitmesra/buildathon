import pandas as pd
import pytest

from app.agents.data_quality.issue_schema import IssueType
from app.agents.data_quality.monetary_validator import (
    MonetarySemanticValidator,
)


@pytest.fixture
def validator():
    return MonetarySemanticValidator()


def test_numeric_monetary_value_is_valid(validator):
    df = pd.DataFrame({
        "Building Value": [1200000],
    })

    assert validator.validate(df) == []


def test_comma_formatted_monetary_value_is_valid(validator):
    df = pd.DataFrame({
        "Building Value": ["1,200,000"],
    })

    assert validator.validate(df) == []


def test_dollar_formatted_monetary_value_is_valid(validator):
    df = pd.DataFrame({
        "Building Value": ["$1,200,000"],
    })

    assert validator.validate(df) == []


def test_million_suffix_is_valid(validator):
    df = pd.DataFrame({
        "Building Value": ["1.2M"],
    })

    assert validator.validate(df) == []


def test_thousand_suffix_is_valid(validator):
    df = pd.DataFrame({
        "Contents": ["750K"],
    })

    assert validator.validate(df) == []


def test_billion_suffix_is_valid(validator):
    df = pd.DataFrame({
        "BI": ["2.5B"],
    })

    assert validator.validate(df) == []


def test_dollar_suffix_is_valid(validator):
    df = pd.DataFrame({
        "Other": ["$750K"],
    })

    assert validator.validate(df) == []


def test_invalid_monetary_text_is_detected(validator):
    df = pd.DataFrame({
        "Building Value": ["$ABC"],
    })

    issues = validator.validate(df)

    assert len(issues) == 1
    assert issues[0].issue_type == IssueType.INVALID_TYPE


def test_invalid_suffix_is_detected(validator):
    df = pd.DataFrame({
        "Building Value": ["1.2MM"],
    })

    issues = validator.validate(df)

    assert len(issues) == 1


def test_malformed_comma_format_is_detected(validator):
    df = pd.DataFrame({
        "Building Value": ["1,2,000"],
    })

    issues = validator.validate(df)

    assert len(issues) == 1


def test_unrecognized_currency_text_is_detected(validator):
    df = pd.DataFrame({
        "Building Value": ["USD ABC"],
    })

    issues = validator.validate(df)

    assert len(issues) == 1


def test_missing_monetary_value_is_skipped(validator):
    df = pd.DataFrame({
        "Building Value": [None],
    })

    assert validator.validate(df) == []


def test_unknown_field_is_skipped(validator):
    df = pd.DataFrame({
        "Unknown": ["$1.2M"],
    })

    assert validator.validate(df) == []


def test_validator_does_not_modify_dataframe(validator):
    df = pd.DataFrame({
        "Building Value": ["$1,200,000", "$ABC"],
    })

    original = df.copy(deep=True)

    validator.validate(df)

    pd.testing.assert_frame_equal(df, original)