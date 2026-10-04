import pandas as pd
import pytest

from app.agents.data_quality.issue_schema import IssueType
from app.agents.data_quality.zip_validator import ZipSemanticValidator


@pytest.fixture
def validator():
    return ZipSemanticValidator()


def test_five_digit_zip_is_valid(validator):
    df = pd.DataFrame({"Zip": ["02110"]})

    assert validator.validate(df) == []


def test_nine_digit_zip_is_valid(validator):
    df = pd.DataFrame({"Zip": ["021101234"]})

    assert validator.validate(df) == []


def test_zip_plus_four_is_valid(validator):
    df = pd.DataFrame({"Zip": ["02110-1234"]})

    assert validator.validate(df) == []


def test_short_zip_is_invalid(validator):
    df = pd.DataFrame({"Zip": ["123"]})

    issues = validator.validate(df)

    assert len(issues) == 1
    assert issues[0].issue_type == IssueType.INVALID_TYPE


def test_six_digit_zip_is_invalid(validator):
    df = pd.DataFrame({"Zip": ["123456"]})

    issues = validator.validate(df)

    assert len(issues) == 1


def test_non_numeric_zip_is_invalid(validator):
    df = pd.DataFrame({"Zip": ["ABCDE"]})

    issues = validator.validate(df)

    assert len(issues) == 1


def test_invalid_zip_plus_four_is_invalid(validator):
    df = pd.DataFrame({"Zip": ["12345-ABC"]})

    issues = validator.validate(df)

    assert len(issues) == 1


def test_missing_zip_is_skipped(validator):
    df = pd.DataFrame({"Zip": [None]})

    assert validator.validate(df) == []


def test_validator_does_not_modify_dataframe(validator):
    df = pd.DataFrame({"Zip": ["02110", "123"]})
    original = df.copy(deep=True)

    validator.validate(df)

    pd.testing.assert_frame_equal(df, original)