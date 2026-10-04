import pandas as pd
import pytest

from app.agents.data_quality.issue_schema import (
    IssueSeverity,
    IssueStatus,
    IssueType,
    QualityIssue,
)

from app.agents.data_quality.quality_aggregator import (
    QualityAggregator,
    QualityReport,
)


def make_issue(
    issue_id: str,
    field: str = "Building Value",
    severity: IssueSeverity = IssueSeverity.MEDIUM,
    issue_type: IssueType = IssueType.INVALID_TYPE,
    row_index: int = 0,
) -> QualityIssue:

    return QualityIssue(
        issue_id=issue_id,
        row_index=row_index,
        source_field=field,
        target_field=field,
        issue_type=issue_type,
        severity=severity,
        observed_value="bad-value",
        expected_condition="Value should be valid.",
        evidence={
            "test": True,
        },
        recommendation="Review source value.",
        confidence=1.0,
        uncertainty="Test uncertainty.",
        status=IssueStatus.DETECTED,
    )


@pytest.fixture
def aggregator():
    return QualityAggregator()


def test_empty_issue_list_returns_clean_report(
    aggregator,
):
    report = aggregator.aggregate([])

    assert isinstance(report, QualityReport)
    assert report.total_issues == 0
    assert report.issues_by_severity == {}
    assert report.issues_by_type == {}
    assert report.issues_by_field == {}
    assert report.critical_issue_count == 0
    assert report.high_issue_count == 0
    assert report.medium_issue_count == 0
    assert report.low_issue_count == 0
    assert report.human_review_required is False
    assert report.quality_score == 100.0
    assert report.issues == []


def test_total_issue_count_is_correct(
    aggregator,
):
    issues = [
        make_issue("1"),
        make_issue("2"),
        make_issue("3"),
    ]

    report = aggregator.aggregate(issues)

    assert report.total_issues == 3


def test_issues_are_grouped_by_severity(
    aggregator,
):
    issues = [
        make_issue(
            "1",
            severity=IssueSeverity.CRITICAL,
        ),
        make_issue(
            "2",
            severity=IssueSeverity.HIGH,
        ),
        make_issue(
            "3",
            severity=IssueSeverity.HIGH,
        ),
        make_issue(
            "4",
            severity=IssueSeverity.MEDIUM,
        ),
        make_issue(
            "5",
            severity=IssueSeverity.LOW,
        ),
    ]

    report = aggregator.aggregate(issues)

    assert report.issues_by_severity == {
        "critical": 1,
        "high": 2,
        "medium": 1,
        "low": 1,
    }


def test_issues_are_grouped_by_type(
    aggregator,
):
    issues = [
        make_issue(
            "1",
            issue_type=IssueType.INVALID_TYPE,
        ),
        make_issue(
            "2",
            issue_type=IssueType.INVALID_TYPE,
        ),
        make_issue(
            "3",
            issue_type=IssueType.MISSING_VALUE,
        ),
    ]

    report = aggregator.aggregate(issues)

    assert report.issues_by_type == {
        "invalid_type": 2,
        "missing_value": 1,
    }


def test_issues_are_grouped_by_field(
    aggregator,
):
    issues = [
        make_issue(
            "1",
            field="Building Value",
        ),
        make_issue(
            "2",
            field="Building Value",
        ),
        make_issue(
            "3",
            field="Year Built",
        ),
    ]

    report = aggregator.aggregate(issues)

    assert report.issues_by_field == {
        "Building Value": 2,
        "Year Built": 1,
    }


def test_severity_counts_are_exposed(
    aggregator,
):
    issues = [
        make_issue(
            "1",
            severity=IssueSeverity.CRITICAL,
        ),
        make_issue(
            "2",
            severity=IssueSeverity.HIGH,
        ),
        make_issue(
            "3",
            severity=IssueSeverity.HIGH,
        ),
        make_issue(
            "4",
            severity=IssueSeverity.MEDIUM,
        ),
        make_issue(
            "5",
            severity=IssueSeverity.LOW,
        ),
    ]

    report = aggregator.aggregate(issues)

    assert report.critical_issue_count == 1
    assert report.high_issue_count == 2
    assert report.medium_issue_count == 1
    assert report.low_issue_count == 1


def test_critical_issue_requires_human_review(
    aggregator,
):
    issues = [
        make_issue(
            "1",
            severity=IssueSeverity.CRITICAL,
        ),
    ]

    report = aggregator.aggregate(issues)

    assert report.human_review_required is True


def test_high_issue_requires_human_review(
    aggregator,
):
    issues = [
        make_issue(
            "1",
            severity=IssueSeverity.HIGH,
        ),
    ]

    report = aggregator.aggregate(issues)

    assert report.human_review_required is True


def test_medium_issue_does_not_require_human_review(
    aggregator,
):
    issues = [
        make_issue(
            "1",
            severity=IssueSeverity.MEDIUM,
        ),
    ]

    report = aggregator.aggregate(issues)

    assert report.human_review_required is False


def test_low_issue_does_not_require_human_review(
    aggregator,
):
    issues = [
        make_issue(
            "1",
            severity=IssueSeverity.LOW,
        ),
    ]

    report = aggregator.aggregate(issues)

    assert report.human_review_required is False


def test_quality_score_for_empty_input_is_100(
    aggregator,
):
    report = aggregator.aggregate([])

    assert report.quality_score == 100.0


def test_quality_score_applies_severity_penalties(
    aggregator,
):
    issues = [
        make_issue(
            "1",
            severity=IssueSeverity.CRITICAL,
        ),
        make_issue(
            "2",
            severity=IssueSeverity.HIGH,
        ),
        make_issue(
            "3",
            severity=IssueSeverity.MEDIUM,
        ),
        make_issue(
            "4",
            severity=IssueSeverity.LOW,
        ),
    ]

    report = aggregator.aggregate(issues)

    expected_score = (
        100
        - 25
        - 15
        - 5
        - 1
    )

    assert report.quality_score == expected_score


def test_quality_score_cannot_go_below_zero(
    aggregator,
):
    issues = [
        make_issue(
            str(index),
            severity=IssueSeverity.CRITICAL,
        )
        for index in range(10)
    ]

    report = aggregator.aggregate(issues)

    assert report.quality_score == 0.0


def test_quality_score_cannot_exceed_100(
    aggregator,
):
    report = aggregator.aggregate([])

    assert report.quality_score <= 100.0


def test_original_issues_are_preserved(
    aggregator,
):
    issue = make_issue("1")

    report = aggregator.aggregate([issue])

    assert report.issues[0] is issue


def test_aggregation_does_not_modify_issue_objects(
    aggregator,
):
    issue = make_issue(
        "1",
        severity=IssueSeverity.HIGH,
    )

    original_status = issue.status
    original_confidence = issue.confidence

    aggregator.aggregate([issue])

    assert issue.status == original_status
    assert issue.confidence == original_confidence


def test_invalid_input_type_is_rejected(
    aggregator,
):
    with pytest.raises(TypeError):
        aggregator.aggregate("not-a-list")


def test_invalid_issue_object_is_rejected(
    aggregator,
):
    with pytest.raises(TypeError):
        aggregator.aggregate(
            [
                "not-a-quality-issue",
            ]
        )


def test_aggregation_does_not_require_dataframe(
    aggregator,
):
    issues = [
        make_issue(
            "1",
            field="State",
            issue_type=IssueType.INVALID_CATEGORY,
        ),
    ]

    report = aggregator.aggregate(issues)

    assert report.total_issues == 1
    assert report.issues_by_field == {
        "State": 1,
    }