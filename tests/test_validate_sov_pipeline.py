"""
Detection-pipeline tests for DeterministicValidator.validate_sov() and
the format / cross-field / consolidation steps, including the
regressions listed in the Agent 3 handoff.
"""

from collections import Counter

import pandas as pd

from app.agents.data_quality.cross_field_validator import CrossFieldValidator
from app.agents.data_quality.format_validator import FormatConsistencyValidator
from app.agents.data_quality.issue_consolidator import (
    collapse_empty_columns,
    consolidate_cell_issues,
)
from app.agents.data_quality.issue_schema import (
    IssueSeverity,
    IssueType,
    QualityIssue,
)
from app.agents.data_quality.validator import DeterministicValidator


YEAR = 2026


def run(frame: pd.DataFrame) -> list[QualityIssue]:
    return DeterministicValidator().validate_sov(frame, current_year=YEAR)


def by_cell(issues):
    return {(issue.row_index, issue.source_field): issue for issue in issues}


def test_every_issue_has_a_rule_id():
    issues = run(pd.DataFrame({"Building Value": [-1, "abc"], "Zip": ["1", "02108"]}))

    assert issues
    assert all(issue.rule_id for issue in issues)


def test_excel_float_zips_do_not_flood():
    frame = pd.DataFrame({"Zip": [75219.0] * 50, "State": ["TX"] * 50})

    zip_issues = [i for i in run(frame) if i.source_field == "Zip"]

    assert zip_issues == []


def test_zip_with_lost_leading_zeros_is_flagged_with_candidate():
    issues = run(pd.DataFrame({"Zip": [802.0], "State": ["VI"]}))
    issue = by_cell(issues)[(0, "Zip")]

    assert issue.rule_id == "zip_leading_zeros_lost"
    assert issue.evidence["candidate_value"] == "00802"


def test_zip_string_with_leading_zero_is_preserved():
    frame = pd.DataFrame({"Zip": ["02108"], "State": ["MA"]}, dtype=object)
    original = frame.copy(deep=True)

    issues = run(frame)

    assert not [i for i in issues if i.source_field == "Zip"]
    assert frame.at[0, "Zip"] == "02108"
    pd.testing.assert_frame_equal(frame, original)


def test_foreign_rows_skip_us_state_and_zip_rules():
    frame = pd.DataFrame(
        {"Country": ["Spain", "Portugal"], "State": ["Galicia", "Porto"], "Zip": [36001.0, 4000.0]}
    )

    fields = {i.source_field for i in run(frame) if i.row_index is not None}

    assert "State" not in fields
    assert "Zip" not in fields


def test_currency_text_is_a_low_format_issue_not_a_type_error():
    issue = by_cell(run(pd.DataFrame({"Building Value": ["$1,200,000"]})))[
        (0, "Building Value")
    ]

    assert issue.issue_type == IssueType.FORMAT_INCONSISTENCY
    assert issue.severity == IssueSeverity.LOW
    assert issue.evidence["candidate_value"] == 1200000.0


def test_unparseable_money_is_still_a_high_type_error():
    issue = by_cell(run(pd.DataFrame({"Building Value": ["TBD"]})))[(0, "Building Value")]

    assert issue.issue_type == IssueType.INVALID_TYPE
    assert issue.severity == IssueSeverity.HIGH


def test_state_names_and_abbreviations_are_standardisations():
    issues = by_cell(run(pd.DataFrame({"State": ["Texas", "ny", "Calif.", "XX"]})))

    assert issues[(0, "State")].issue_type == IssueType.FORMAT_INCONSISTENCY
    assert issues[(1, "State")].issue_type == IssueType.FORMAT_INCONSISTENCY
    assert issues[(2, "State")].issue_type == IssueType.FORMAT_INCONSISTENCY
    assert issues[(3, "State")].issue_type == IssueType.INVALID_CATEGORY


def test_numeric_sprinkler_coverage_is_interpreted_per_column():
    frame = pd.DataFrame({"Fire Sprinklers (Y/N)": [0.0, 1.0, 0.57]})
    issues = by_cell(run(frame))

    assert issues[(0, "Fire Sprinklers (Y/N)")].evidence[
        "candidate_canonical_value"
    ] == "N"
    assert issues[(1, "Fire Sprinklers (Y/N)")].evidence[
        "candidate_canonical_value"
    ] == "Y"
    partial = issues[(2, "Fire Sprinklers (Y/N)")]
    assert partial.severity == IssueSeverity.HIGH
    assert partial.rule_id == "sprinkler_partial_coverage"


def test_each_cell_gets_one_issue():
    frame = pd.DataFrame(
        {
            "Year Built": [1990, 1991, 1992, 1993, 1994, 1995, 2099],
            "Fire Sprinklers (Y/N)": [0.0, 1.0, 0.57, "Y", "N", "MAYBE", "YES"],
        }
    )

    counts = Counter((i.row_index, i.source_field) for i in run(frame) if i.row_index is not None)

    assert max(counts.values()) == 1


def test_future_year_keeps_statistical_anomaly_as_evidence():
    frame = pd.DataFrame({"Year Built": [1990, 1991, 1992, 1993, 1994, 1995, 2099]})
    issue = by_cell(run(frame))[(6, "Year Built")]

    assert issue.issue_type == IssueType.FUTURE_YEAR
    related = {r["issue_type"] for r in issue.evidence["related_issues"]}
    assert "statistical_anomaly" in related
    assert "statistical_context" in issue.evidence


def test_year_placeholder_is_detected():
    issue = by_cell(run(pd.DataFrame({"Year Built": [0, 1990]})))[(0, "Year Built")]

    assert issue.rule_id == "year_placeholder"


def test_missing_required_column_is_reported_once():
    issues = run(pd.DataFrame({"Reference": ["A", "B"]}))
    column_issues = [
        i for i in issues if i.row_index is None and i.source_field == "Building Value"
    ]

    assert len(column_issues) == 1
    assert column_issues[0].rule_id == "column_not_mapped"
    assert column_issues[0].severity == IssueSeverity.HIGH


def test_fully_empty_column_collapses_to_one_issue():
    frame = pd.DataFrame({"BI": [None] * 100, "Reference": [f"R{i}" for i in range(100)]})
    bi = [i for i in run(frame) if i.source_field == "BI"]

    assert len(bi) == 1
    assert bi[0].rule_id == "column_empty"


def test_numeric_reference_is_not_a_type_error():
    issues = run(pd.DataFrame({"Reference": [1.0, 2.0, 3.0]}))

    assert not [i for i in issues if i.source_field == "Reference" and i.row_index is not None]


def test_statistical_anomalies_are_advisory():
    frame = pd.DataFrame({"Building Value": [100, 105, 110, 115, 120, 125, 130, 10_000_000]})
    anomalies = [i for i in run(frame) if i.issue_type == IssueType.STATISTICAL_ANOMALY]

    assert anomalies
    assert all(i.severity in {IssueSeverity.LOW, IssueSeverity.MEDIUM} for i in anomalies)


def test_constant_storeys_column_has_no_outliers():
    frame = pd.DataFrame({"Storeys": [1] * 40 + [2, 3]})

    assert not [i for i in run(frame) if i.issue_type == IssueType.STATISTICAL_ANOMALY]


def test_validate_sov_does_not_modify_dataframe():
    frame = pd.DataFrame(
        {"Zip": ["2108", 802.0], "Building Value": ["$1M", -5], "State": ["Texas", "XX"]},
        dtype=object,
    )
    original = frame.copy(deep=True)

    run(frame)

    pd.testing.assert_frame_equal(frame, original)


# ---------------------------------------------------------------------
# Cross-field
# ---------------------------------------------------------------------


def test_zip_state_mismatch():
    frame = pd.DataFrame({"Zip": ["02108", "75219"], "State": ["CA", "TX"]})
    issues = CrossFieldValidator().validate(frame)

    assert [i.row_index for i in issues] == [0]
    assert issues[0].issue_type == IssueType.CROSS_FIELD_CONFLICT


def test_zero_total_insured_value():
    frame = pd.DataFrame(
        {"Building Value": [0, 0, 100], "Contents": [0, 500000, 0], "BI": [None, 0, 0]}
    )
    issues = CrossFieldValidator().validate(frame)

    assert [i.row_index for i in issues] == [0]


def test_building_zero_with_contents_is_legitimate():
    frame = pd.DataFrame({"Building Value": [0], "Contents": [500000]})

    assert CrossFieldValidator().validate(frame) == []


def test_us_state_on_foreign_row():
    frame = pd.DataFrame({"Country": ["Spain", "USA"], "State": ["TX", "TX"]})
    issues = CrossFieldValidator().validate(frame)

    assert [i.row_index for i in issues] == [0]


def test_duplicate_rows():
    frame = pd.DataFrame({"Reference": ["A", "A", "B"], "City": ["X", "X", "Y"]})
    issues = [i for i in CrossFieldValidator().validate(frame) if i.rule_id == "duplicate_row"]

    assert sorted(i.row_index for i in issues) == [0, 1]


# ---------------------------------------------------------------------
# Format validator and consolidator in isolation
# ---------------------------------------------------------------------


def test_format_validator_trims_whitespace():
    issues = FormatConsistencyValidator().validate(pd.DataFrame({"Address": ["1 Main  St "]}))

    assert issues[0].evidence["candidate_value"] == "1 Main St"


def _issue(issue_id, issue_type, severity, row=0, field="Year Built"):
    return QualityIssue(
        issue_id=issue_id,
        row_index=row,
        source_field=field,
        issue_type=issue_type,
        severity=severity,
        expected_condition="x",
        confidence=1.0,
        uncertainty="x",
    )


def test_consolidator_keeps_most_severe_and_does_not_mutate():
    stat = _issue("s", IssueType.STATISTICAL_ANOMALY, IssueSeverity.MEDIUM)
    hard = _issue("h", IssueType.FUTURE_YEAR, IssueSeverity.HIGH)

    result = consolidate_cell_issues([stat, hard])

    assert [i.issue_id for i in result] == ["h"]
    assert hard.evidence == {}


def test_consolidator_keeps_cross_field_separate():
    cross = _issue("c", IssueType.CROSS_FIELD_CONFLICT, IssueSeverity.MEDIUM, field="Zip")
    cell = _issue("z", IssueType.INVALID_TYPE, IssueSeverity.MEDIUM, field="Zip")

    assert len(consolidate_cell_issues([cross, cell])) == 2


def test_collapse_empty_columns_leaves_other_issues():
    frame = pd.DataFrame({"BI": [None, None], "City": ["a", None]})
    issues = [
        _issue("b0", IssueType.MISSING_VALUE, IssueSeverity.MEDIUM, 0, "BI"),
        _issue("b1", IssueType.MISSING_VALUE, IssueSeverity.MEDIUM, 1, "BI"),
        _issue("c1", IssueType.MISSING_VALUE, IssueSeverity.MEDIUM, 1, "City"),
    ]

    ids = [i.issue_id for i in collapse_empty_columns(issues, frame)]

    assert ids == ["c1", "DQ-COLUMN-EMPTY-BI"]
