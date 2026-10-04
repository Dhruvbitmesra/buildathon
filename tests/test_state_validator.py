import pandas as pd
import pytest

from app.agents.data_quality.issue_schema import (
    IssueType,
)
from app.agents.data_quality.state_validator import StateSemanticValidator


@pytest.fixture
def validator():
    return StateSemanticValidator()


def test_valid_state_code(validator):
    df = pd.DataFrame({"State": ["CA"]})

    issues = validator.validate(df)

    assert issues == []


def test_valid_full_state_name(validator):
    df = pd.DataFrame({"State": ["California"]})

    issues = validator.validate(df)

    assert issues == []


def test_state_code_is_case_insensitive(validator):
    df = pd.DataFrame({"State": ["ca"]})

    issues = validator.validate(df)

    assert issues == []


def test_invalid_state_value_is_detected(validator):
    df = pd.DataFrame({"State": ["Californiaa"]})

    issues = validator.validate(df)

    assert len(issues) == 1
    assert issues[0].issue_type == IssueType.INVALID_CATEGORY
    assert issues[0].source_field == "State"


def test_invalid_three_letter_state_code_is_detected(validator):
    df = pd.DataFrame({"State": ["CAL"]})

    issues = validator.validate(df)

    assert len(issues) == 1


def test_missing_state_is_skipped(validator):
    df = pd.DataFrame({"State": [None]})

    issues = validator.validate(df)

    assert issues == []


def test_multiple_invalid_states_are_detected(validator):
    df = pd.DataFrame({
        "State": ["CA", "Californiaa", "XYZ", "NY"],
    })

    issues = validator.validate(df)

    assert len(issues) == 2


def test_validator_does_not_modify_dataframe(validator):
    df = pd.DataFrame({
        "State": ["CA", "Californiaa"],
    })

    original = df.copy(deep=True)

    validator.validate(df)

    pd.testing.assert_frame_equal(df, original)