import pandas as pd
import pytest

from app.agents.data_quality.field_validator import (
    FieldSpecificValidator,
)
from app.agents.data_quality.issue_schema import IssueType


@pytest.fixture
def validator():
    return FieldSpecificValidator()


def test_valid_positive_integer(validator):
    df = pd.DataFrame({
        "Storeys": [1, 5, 20],
    })

    issues = validator.validate(df)

    assert issues == []




def test_zero_building_value_is_valid(validator):
    df = pd.DataFrame({
        "Building Value": [0],
    })

    issues = validator.validate(df)

    assert issues == []



def test_valid_sprinkler_values(validator):
    df = pd.DataFrame({
        "Fire Sprinklers (Y/N)": [
            "Y",
            "N",
            "Y13",
            "Y(13R)",
        ],
    })

    issues = validator.validate(df)

    assert issues == []


def test_numeric_only_state_is_flagged(validator):
    df = pd.DataFrame({
        "State": ["12345"],
    })

    issues = validator.validate(df)

    assert len(issues) == 1
    assert issues[0].issue_type == IssueType.INVALID_TYPE
    assert issues[0].source_field == "State"


def test_numeric_only_county_is_flagged(validator):
    df = pd.DataFrame({
        "County": ["12345"],
    })

    issues = validator.validate(df)

    assert len(issues) == 1
    assert issues[0].issue_type == IssueType.INVALID_TYPE


def test_numeric_only_occupancy_is_flagged(validator):
    df = pd.DataFrame({
        "Occupancy": ["12345"],
    })

    issues = validator.validate(df)

    assert len(issues) == 1
    assert issues[0].issue_type == IssueType.INVALID_TYPE

def test_numeric_only_construction_is_flagged(validator):
    df = pd.DataFrame({
        "Construction": ["12345"],
    })

    issues = validator.validate(df)

    assert len(issues) == 1
    assert issues[0].issue_type == IssueType.INVALID_TYPE

def test_numeric_zip_is_not_treated_as_text_issue(validator):
    df = pd.DataFrame({
        "Zip": [80001],
    })

    issues = validator.validate(df)

    assert issues == []

def test_current_year_is_valid(validator):
    df = pd.DataFrame({
        "Year Built": [2026],
    })

    issues = validator.validate(
        df,
        current_year=2026,
    )

    assert issues == []


def test_numeric_only_city_is_flagged(validator):
    df = pd.DataFrame({
        "City": ["12345"],
    })

    issues = validator.validate(df)

    assert len(issues) == 1
    assert issues[0].issue_type == IssueType.INVALID_TYPE


def test_missing_values_are_skipped(validator):
    df = pd.DataFrame({
        "Storeys": [None],
        "Building Value": [None],
        "Year Built": [None],
    })

    issues = validator.validate(df)

    assert issues == []


def test_validator_does_not_modify_dataframe(validator):
    df = pd.DataFrame({
        "Storeys": [0],
        "Building Value": [-100],
    })

    original = df.copy(deep=True)

    validator.validate(df)

    pd.testing.assert_frame_equal(df, original)