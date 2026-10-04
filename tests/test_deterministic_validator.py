import pandas as pd
import pytest

from app.agents.data_quality.validator import DeterministicValidator


def test_validator_accepts_dataframe():
    dataframe = pd.DataFrame(
        {
            "Reference": ["REF001", "REF002"],
            "Building Value": [100000.0, 200000.0],
        }
    )

    validator = DeterministicValidator()

    issues = validator.validate(dataframe)

    assert isinstance(issues, list)
    assert issues == []


def test_validator_rejects_non_dataframe():
    validator = DeterministicValidator()

    with pytest.raises(TypeError):
        validator.validate(
            {
                "Reference": ["REF001"],
            }
        )


def test_validator_does_not_modify_dataframe():
    dataframe = pd.DataFrame(
        {
            "Reference": ["REF001"],
            "Building Value": [-1000.0],
        }
    )

    original = dataframe.copy(deep=True)

    validator = DeterministicValidator()
    validator.validate(dataframe)

    pd.testing.assert_frame_equal(dataframe, original)


def test_missing_value_is_detected():
    dataframe = pd.DataFrame(
        {
            "Reference": ["REF001", "REF002"],
            "Address": ["ABC Street", None],
        }
    )

    validator = DeterministicValidator()

    issues = validator.validate(
        dataframe,
        required_fields={"Address"},
    )

    assert len(issues) == 1

    issue = issues[0]

    assert issue.issue_type.value == "missing_value"
    assert issue.source_field == "Address"
    assert issue.target_field == "Address"
    assert issue.row_index == 1
    assert issue.confidence == 1.0


def test_missing_fields_are_skipped():
    dataframe = pd.DataFrame(
        {
            "Reference": ["REF001"],
        }
    )

    validator = DeterministicValidator()

    issues = validator.validate(
        dataframe,
        required_fields={"Address"},
    )

    assert issues == []


def test_multiple_missing_values_are_detected():
    dataframe = pd.DataFrame(
        {
            "Reference": [None, "REF002", None],
        }
    )

    validator = DeterministicValidator()

    issues = validator.validate(
        dataframe,
        required_fields={"Reference"},
    )

    assert len(issues) == 2

    assert {issue.row_index for issue in issues} == {0, 2}


def test_missing_value_does_not_modify_dataframe():
    dataframe = pd.DataFrame(
        {
            "Address": ["ABC Street", None],
        }
    )

    original = dataframe.copy(deep=True)

    validator = DeterministicValidator()

    validator.validate(
        dataframe,
        required_fields={"Address"},
    )

    pd.testing.assert_frame_equal(dataframe, original)

def test_valid_integer_values_are_accepted():
    dataframe = pd.DataFrame(
        {
            "Storeys": [1, 2, 10],
        }
    )

    validator = DeterministicValidator()

    issues = validator.validate(
        dataframe,
        field_types={
            "Storeys": "integer",
        },
    )

    assert issues == []


def test_invalid_integer_value_is_detected():
    dataframe = pd.DataFrame(
        {
            "Storeys": [1, 2.5, 3],
        }
    )

    validator = DeterministicValidator()

    issues = validator.validate(
        dataframe,
        field_types={
            "Storeys": "integer",
        },
    )

    assert len(issues) == 1

    issue = issues[0]

    assert issue.issue_type.value == "invalid_type"
    assert issue.source_field == "Storeys"
    assert issue.row_index == 1
    assert issue.observed_value == 2.5


def test_whole_number_float_is_integer_compatible():
    dataframe = pd.DataFrame(
        {
            "Storeys": [1.0, 2.0, 3.0],
        }
    )

    validator = DeterministicValidator()

    issues = validator.validate(
        dataframe,
        field_types={
            "Storeys": "integer",
        },
    )

    assert issues == []


def test_valid_float_values_are_accepted():
    dataframe = pd.DataFrame(
        {
            "Building Value": [
                100000,
                250000.50,
                500000.0,
            ],
        }
    )

    validator = DeterministicValidator()

    issues = validator.validate(
        dataframe,
        field_types={
            "Building Value": "float",
        },
    )

    assert issues == []


def test_invalid_float_value_is_detected():
    dataframe = pd.DataFrame(
        {
            "Building Value": [
                100000.0,
                "ABC",
                250000.0,
            ],
        }
    )

    validator = DeterministicValidator()

    issues = validator.validate(
        dataframe,
        field_types={
            "Building Value": "float",
        },
    )

    assert len(issues) == 1

    issue = issues[0]

    assert issue.issue_type.value == "invalid_type"
    assert issue.source_field == "Building Value"
    assert issue.row_index == 1
    assert issue.observed_value == "ABC"
    assert issue.severity.value == "high"


def test_valid_string_values_are_accepted():
    dataframe = pd.DataFrame(
        {
            "Address": [
                "123 Main Street",
                "456 Oak Avenue",
            ],
        }
    )

    validator = DeterministicValidator()

    issues = validator.validate(
        dataframe,
        field_types={
            "Address": "string",
        },
    )

    assert issues == []


def test_invalid_string_value_is_detected():
    dataframe = pd.DataFrame(
        {
            "Address": [
                "123 Main Street",
                12345,
            ],
        }
    )

    validator = DeterministicValidator()

    issues = validator.validate(
        dataframe,
        field_types={
            "Address": "string",
        },
    )

    assert len(issues) == 1

    issue = issues[0]

    assert issue.issue_type.value == "invalid_type"
    assert issue.source_field == "Address"
    assert issue.row_index == 1


def test_missing_values_are_not_reported_as_invalid_type():
    dataframe = pd.DataFrame(
        {
            "Storeys": [1, None, 3],
        }
    )

    validator = DeterministicValidator()

    issues = validator.validate(
        dataframe,
        field_types={
            "Storeys": "integer",
        },
    )

    assert issues == []


def test_unknown_field_is_skipped():
    dataframe = pd.DataFrame(
        {
            "Reference": ["REF001"],
        }
    )

    validator = DeterministicValidator()

    issues = validator.validate(
        dataframe,
        field_types={
            "Storeys": "integer",
        },
    )

    assert issues == []


def test_unsupported_type_is_rejected():
    dataframe = pd.DataFrame(
        {
            "Storeys": [1, 2],
        }
    )

    validator = DeterministicValidator()

    with pytest.raises(ValueError):
        validator.validate(
            dataframe,
            field_types={
                "Storeys": "date",
            },
        )


def test_type_validation_does_not_modify_dataframe():
    dataframe = pd.DataFrame(
        {
            "Building Value": [100000.0, "ABC"],
        }
    )

    original = dataframe.copy(deep=True)

    validator = DeterministicValidator()

    validator.validate(
        dataframe,
        field_types={
            "Building Value": "float",
        },
    )

    pd.testing.assert_frame_equal(dataframe, original)

def test_negative_building_value_is_detected():
    dataframe = pd.DataFrame(
        {
            "Building Value": [100000.0, -50000.0, 250000.0],
        }
    )

    validator = DeterministicValidator()

    issues = validator.validate(
        dataframe,
        non_negative_fields={"Building Value"},
    )

    assert len(issues) == 1

    issue = issues[0]

    assert issue.issue_type.value == "negative_value"
    assert issue.source_field == "Building Value"
    assert issue.row_index == 1
    assert issue.observed_value == -50000.0
    assert issue.severity.value == "high"
    assert issue.confidence == 1.0


def test_negative_count_value_is_detected():
    dataframe = pd.DataFrame(
        {
            "Number of Buildings": [1, -2, 3],
        }
    )

    validator = DeterministicValidator()

    issues = validator.validate(
        dataframe,
        non_negative_fields={"Number of Buildings"},
    )

    assert len(issues) == 1

    issue = issues[0]

    assert issue.issue_type.value == "negative_value"
    assert issue.row_index == 1
    assert issue.severity.value == "medium"


def test_multiple_negative_values_are_detected():
    dataframe = pd.DataFrame(
        {
            "Building Value": [-1000.0, 2000.0, -3000.0],
        }
    )

    validator = DeterministicValidator()

    issues = validator.validate(
        dataframe,
        non_negative_fields={"Building Value"},
    )

    assert len(issues) == 2
    assert {issue.row_index for issue in issues} == {0, 2}


def test_zero_is_valid_for_negative_value_check():
    dataframe = pd.DataFrame(
        {
            "Other": [0.0, 1000.0],
        }
    )

    validator = DeterministicValidator()

    issues = validator.validate(
        dataframe,
        non_negative_fields={"Other"},
    )

    assert issues == []


def test_missing_value_is_not_negative():
    dataframe = pd.DataFrame(
        {
            "Building Value": [100000.0, None],
        }
    )

    validator = DeterministicValidator()

    issues = validator.validate(
        dataframe,
        non_negative_fields={"Building Value"},
    )

    assert issues == []


def test_non_numeric_value_is_not_reported_as_negative():
    dataframe = pd.DataFrame(
        {
            "Building Value": ["ABC"],
        }
    )

    validator = DeterministicValidator()

    issues = validator.validate(
        dataframe,
        non_negative_fields={"Building Value"},
    )

    assert issues == []


def test_negative_value_does_not_modify_dataframe():
    dataframe = pd.DataFrame(
        {
            "Building Value": [-50000.0],
        }
    )

    original = dataframe.copy(deep=True)

    validator = DeterministicValidator()

    validator.validate(
        dataframe,
        non_negative_fields={"Building Value"},
    )

    pd.testing.assert_frame_equal(dataframe, original)

def test_valid_sprinkler_categories_are_accepted():
    dataframe = pd.DataFrame(
        {
            "Fire Sprinklers (Y/N)": [
                "Y",
                "N",
                "Y13",
                "Y(13R)",
            ],
        }
    )

    validator = DeterministicValidator()

    issues = validator.validate(
        dataframe,
        allowed_categories={
            "Fire Sprinklers (Y/N)": {
                "Y",
                "N",
                "Y13",
                "Y(13R)",
            },
        },
    )

    assert issues == []


def test_invalid_sprinkler_category_is_detected():
    dataframe = pd.DataFrame(
        {
            "Fire Sprinklers (Y/N)": [
                "Y",
                "MAYBE",
                "N",
            ],
        }
    )

    validator = DeterministicValidator()

    issues = validator.validate(
        dataframe,
        allowed_categories={
            "Fire Sprinklers (Y/N)": {
                "Y",
                "N",
                "Y13",
                "Y(13R)",
            },
        },
    )

    assert len(issues) == 1

    issue = issues[0]

    assert issue.issue_type.value == "invalid_category"
    assert issue.source_field == "Fire Sprinklers (Y/N)"
    assert issue.row_index == 1
    assert issue.observed_value == "MAYBE"
    assert issue.severity.value == "high"
    assert issue.confidence == 1.0


def test_multiple_invalid_categories_are_detected():
    dataframe = pd.DataFrame(
        {
            "Fire Sprinklers (Y/N)": [
                "YES",
                "Y",
                "UNKNOWN",
                "N",
            ],
        }
    )

    validator = DeterministicValidator()

    issues = validator.validate(
        dataframe,
        allowed_categories={
            "Fire Sprinklers (Y/N)": {
                "Y",
                "N",
                "Y13",
                "Y(13R)",
            },
        },
    )

    assert len(issues) == 2
    assert {issue.row_index for issue in issues} == {0, 2}


def test_missing_category_value_is_skipped():
    dataframe = pd.DataFrame(
        {
            "Fire Sprinklers (Y/N)": [
                "Y",
                None,
                "N",
            ],
        }
    )

    validator = DeterministicValidator()

    issues = validator.validate(
        dataframe,
        allowed_categories={
            "Fire Sprinklers (Y/N)": {
                "Y",
                "N",
                "Y13",
                "Y(13R)",
            },
        },
    )

    assert issues == []


def test_missing_category_field_is_skipped():
    dataframe = pd.DataFrame(
        {
            "Reference": ["REF001"],
        }
    )

    validator = DeterministicValidator()

    issues = validator.validate(
        dataframe,
        allowed_categories={
            "Fire Sprinklers (Y/N)": {
                "Y",
                "N",
                "Y13",
                "Y(13R)",
            },
        },
    )

    assert issues == []


def test_category_matching_is_case_sensitive():
    dataframe = pd.DataFrame(
        {
            "Fire Sprinklers (Y/N)": [
                "Y",
                "y",
                "N",
            ],
        }
    )

    validator = DeterministicValidator()

    issues = validator.validate(
        dataframe,
        allowed_categories={
            "Fire Sprinklers (Y/N)": {
                "Y",
                "N",
                "Y13",
                "Y(13R)",
            },
        },
    )

    assert len(issues) == 1
    assert issues[0].row_index == 1
    assert issues[0].observed_value == "y"


def test_category_validation_does_not_modify_dataframe():
    dataframe = pd.DataFrame(
        {
            "Fire Sprinklers (Y/N)": [
                "Y",
                "MAYBE",
            ],
        }
    )

    original = dataframe.copy(deep=True)

    validator = DeterministicValidator()

    validator.validate(
        dataframe,
        allowed_categories={
            "Fire Sprinklers (Y/N)": {
                "Y",
                "N",
                "Y13",
                "Y(13R)",
            },
        },
    )

    pd.testing.assert_frame_equal(dataframe, original)

def test_storeys_below_minimum_is_detected():
    dataframe = pd.DataFrame(
        {
            "Storeys": [1, 0, 2],
        }
    )

    validator = DeterministicValidator()

    issues = validator.validate(
        dataframe,
        field_ranges={
            "Storeys": {
                "min": 1,
            },
        },
    )

    assert len(issues) == 1

    issue = issues[0]

    assert issue.issue_type.value == "invalid_range"
    assert issue.source_field == "Storeys"
    assert issue.row_index == 1
    assert issue.observed_value == 0
    assert issue.confidence == 1.0


def test_number_of_buildings_below_minimum_is_detected():
    dataframe = pd.DataFrame(
        {
            "Number of Buildings": [1, 0, 3],
        }
    )

    validator = DeterministicValidator()

    issues = validator.validate(
        dataframe,
        field_ranges={
            "Number of Buildings": {
                "min": 1,
            },
        },
    )

    assert len(issues) == 1

    issue = issues[0]

    assert issue.issue_type.value == "invalid_range"
    assert issue.source_field == "Number of Buildings"
    assert issue.row_index == 1
    assert issue.observed_value == 0


def test_value_inside_range_is_valid():
    dataframe = pd.DataFrame(
        {
            "Storeys": [1, 2, 10],
        }
    )

    validator = DeterministicValidator()

    issues = validator.validate(
        dataframe,
        field_ranges={
            "Storeys": {
                "min": 1,
                "max": 200,
            },
        },
    )

    assert issues == []


def test_value_above_maximum_is_detected():
    dataframe = pd.DataFrame(
        {
            "Storeys": [1, 10, 250],
        }
    )

    validator = DeterministicValidator()

    issues = validator.validate(
        dataframe,
        field_ranges={
            "Storeys": {
                "min": 1,
                "max": 200,
            },
        },
    )

    assert len(issues) == 1

    issue = issues[0]

    assert issue.issue_type.value == "invalid_range"
    assert issue.row_index == 2
    assert issue.observed_value == 250


def test_missing_range_value_is_skipped():
    dataframe = pd.DataFrame(
        {
            "Storeys": [1, None, 3],
        }
    )

    validator = DeterministicValidator()

    issues = validator.validate(
        dataframe,
        field_ranges={
            "Storeys": {
                "min": 1,
            },
        },
    )

    assert issues == []


def test_non_numeric_range_value_is_skipped():
    dataframe = pd.DataFrame(
        {
            "Storeys": [1, "ABC", 3],
        }
    )

    validator = DeterministicValidator()

    issues = validator.validate(
        dataframe,
        field_ranges={
            "Storeys": {
                "min": 1,
            },
        },
    )

    assert issues == []


def test_missing_range_field_is_skipped():
    dataframe = pd.DataFrame(
        {
            "Reference": ["REF001"],
        }
    )

    validator = DeterministicValidator()

    issues = validator.validate(
        dataframe,
        field_ranges={
            "Storeys": {
                "min": 1,
            },
        },
    )

    assert issues == []


def test_range_validation_does_not_modify_dataframe():
    dataframe = pd.DataFrame(
        {
            "Storeys": [0, 2],
        }
    )

    original = dataframe.copy(deep=True)

    validator = DeterministicValidator()

    validator.validate(
        dataframe,
        field_ranges={
            "Storeys": {
                "min": 1,
            },
        },
    )

    pd.testing.assert_frame_equal(dataframe, original)

def test_future_year_is_detected():
    dataframe = pd.DataFrame(
        {
            "Year Built": [1995, 2026, 2035],
        }
    )

    validator = DeterministicValidator()

    issues = validator.validate(
        dataframe,
        current_year=2026,
    )

    assert len(issues) == 1

    issue = issues[0]

    assert issue.issue_type.value == "future_year"
    assert issue.source_field == "Year Built"
    assert issue.target_field == "Year Built"
    assert issue.row_index == 2
    assert issue.observed_value == 2035
    assert issue.severity.value == "high"
    assert issue.confidence == 1.0


def test_current_year_is_valid():
    dataframe = pd.DataFrame(
        {
            "Year Built": [2024, 2025, 2026],
        }
    )

    validator = DeterministicValidator()

    issues = validator.validate(
        dataframe,
        current_year=2026,
    )

    assert issues == []


def test_multiple_future_years_are_detected():
    dataframe = pd.DataFrame(
        {
            "Year Built": [2030, 1990, 2040, 2000],
        }
    )

    validator = DeterministicValidator()

    issues = validator.validate(
        dataframe,
        current_year=2026,
    )

    assert len(issues) == 2
    assert {issue.row_index for issue in issues} == {0, 2}


def test_missing_year_built_is_skipped():
    dataframe = pd.DataFrame(
        {
            "Year Built": [1990, None, 2026],
        }
    )

    validator = DeterministicValidator()

    issues = validator.validate(
        dataframe,
        current_year=2026,
    )

    assert issues == []


def test_invalid_year_type_is_not_future_year():
    dataframe = pd.DataFrame(
        {
            "Year Built": [1990, "ABC", 2026],
        }
    )

    validator = DeterministicValidator()

    issues = validator.validate(
        dataframe,
        current_year=2026,
    )

    assert issues == []


def test_whole_number_float_year_is_supported():
    dataframe = pd.DataFrame(
        {
            "Year Built": [1990.0, 2030.0],
        }
    )

    validator = DeterministicValidator()

    issues = validator.validate(
        dataframe,
        current_year=2026,
    )

    assert len(issues) == 1
    assert issues[0].row_index == 1


def test_year_built_field_missing_is_skipped():
    dataframe = pd.DataFrame(
        {
            "Reference": ["REF001"],
        }
    )

    validator = DeterministicValidator()

    issues = validator.validate(
        dataframe,
        current_year=2026,
    )

    assert issues == []


def test_future_year_validation_does_not_modify_dataframe():
    dataframe = pd.DataFrame(
        {
            "Year Built": [1990, 2035],
        }
    )

    original = dataframe.copy(deep=True)

    validator = DeterministicValidator()

    validator.validate(
        dataframe,
        current_year=2026,
    )

    pd.testing.assert_frame_equal(dataframe, original)

def test_duplicate_reference_is_detected():
    dataframe = pd.DataFrame(
        {
            "Reference": [
                "REF001",
                "REF002",
                "REF001",
            ],
        }
    )

    validator = DeterministicValidator()

    issues = validator.validate(
        dataframe,
        unique_fields={"Reference"},
    )

    assert len(issues) == 2

    assert {issue.row_index for issue in issues} == {0, 2}

    for issue in issues:
        assert issue.issue_type.value == "duplicate"
        assert issue.source_field == "Reference"
        assert issue.observed_value == "REF001"
        assert issue.confidence == 1.0


def test_unique_reference_values_are_valid():
    dataframe = pd.DataFrame(
        {
            "Reference": [
                "REF001",
                "REF002",
                "REF003",
            ],
        }
    )

    validator = DeterministicValidator()

    issues = validator.validate(
        dataframe,
        unique_fields={"Reference"},
    )

    assert issues == []


def test_multiple_duplicate_reference_groups_are_detected():
    dataframe = pd.DataFrame(
        {
            "Reference": [
                "REF001",
                "REF002",
                "REF001",
                "REF002",
                "REF003",
            ],
        }
    )

    validator = DeterministicValidator()

    issues = validator.validate(
        dataframe,
        unique_fields={"Reference"},
    )

    assert len(issues) == 4

    assert {issue.row_index for issue in issues} == {
        0,
        1,
        2,
        3,
    }


def test_missing_references_are_not_duplicate_issues():
    dataframe = pd.DataFrame(
        {
            "Reference": [
                "REF001",
                None,
                None,
                "REF002",
            ],
        }
    )

    validator = DeterministicValidator()

    issues = validator.validate(
        dataframe,
        unique_fields={"Reference"},
    )

    assert issues == []


def test_missing_unique_field_is_skipped():
    dataframe = pd.DataFrame(
        {
            "Address": [
                "123 Main Street",
            ],
        }
    )

    validator = DeterministicValidator()

    issues = validator.validate(
        dataframe,
        unique_fields={"Reference"},
    )

    assert issues == []


def test_duplicate_reference_does_not_modify_dataframe():
    dataframe = pd.DataFrame(
        {
            "Reference": [
                "REF001",
                "REF001",
            ],
        }
    )

    original = dataframe.copy(deep=True)

    validator = DeterministicValidator()

    validator.validate(
        dataframe,
        unique_fields={"Reference"},
    )

    pd.testing.assert_frame_equal(
        dataframe,
        original,
    )


def test_duplicate_evidence_contains_count():
    dataframe = pd.DataFrame(
        {
            "Reference": [
                "REF001",
                "REF001",
                "REF001",
            ],
        }
    )

    validator = DeterministicValidator()

    issues = validator.validate(
        dataframe,
        unique_fields={"Reference"},
    )

    assert len(issues) == 3

    for issue in issues:
        assert issue.evidence["duplicate_count"] == 3
        assert issue.evidence["duplicated_value"] == "REF001"

def test_statistical_anomaly_validation_is_integrated():
    from app.agents.data_quality.validator import DeterministicValidator

    dataframe = pd.DataFrame(
        {
            "Building Value": [
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

    validator = DeterministicValidator()

    issues = validator.validate(dataframe)

    statistical_issues = [
        issue
        for issue in issues
        if issue.issue_type.value == "statistical_anomaly"
    ]

    assert len(statistical_issues) >= 1
    assert any(
        issue.row_index == 7
        for issue in statistical_issues
    )