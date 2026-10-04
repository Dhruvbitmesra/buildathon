import pytest
from pydantic import ValidationError

from app.agents.data_quality.issue_schema import (
    IssueSeverity,
    IssueStatus,
    IssueType,
    QualityIssue,
)


def test_valid_quality_issue():
    issue = QualityIssue(
        issue_id="DQ-000001",
        row_index=12,
        source_field="Year Built",
        target_field="Year Built",
        issue_type=IssueType.FUTURE_YEAR,
        severity=IssueSeverity.HIGH,
        observed_value=2035,
        expected_condition="Year Built must not exceed the current year.",
        evidence={
            "current_year": 2026,
            "observed_year": 2035,
        },
        recommendation="Review source value",
        confidence=0.99,
        uncertainty="No reliable replacement value is available.",
    )

    assert issue.issue_id == "DQ-000001"
    assert issue.issue_type == IssueType.FUTURE_YEAR
    assert issue.status == IssueStatus.DETECTED


def test_confidence_must_be_between_zero_and_one():
    with pytest.raises(ValidationError):
        QualityIssue(
            issue_id="DQ-000002",
            source_field="Year Built",
            issue_type=IssueType.FUTURE_YEAR,
            severity=IssueSeverity.HIGH,
            expected_condition="Year must not be in the future.",
            confidence=1.5,
            uncertainty="Unknown",
        )


def test_empty_issue_id_is_rejected():
    with pytest.raises(ValidationError):
        QualityIssue(
            issue_id="",
            source_field="Year Built",
            issue_type=IssueType.FUTURE_YEAR,
            severity=IssueSeverity.HIGH,
            expected_condition="Year must not be in the future.",
            confidence=0.9,
            uncertainty="Unknown",
        )


def test_status_can_be_updated():
    issue = QualityIssue(
        issue_id="DQ-000003",
        source_field="Building Value",
        issue_type=IssueType.NEGATIVE_VALUE,
        severity=IssueSeverity.HIGH,
        observed_value=-1000,
        expected_condition="Building Value must be non-negative.",
        confidence=0.98,
        uncertainty="Replacement value is unknown.",
    )

    updated = issue.model_copy(
        update={"status": IssueStatus.APPROVED}
    )

    assert updated.status == IssueStatus.APPROVED


def test_issue_serializes_to_json():
    issue = QualityIssue(
        issue_id="DQ-000004",
        source_field="Fire Sprinklers (Y/N)",
        target_field="Fire Sprinklers (Y/N)",
        issue_type=IssueType.INVALID_CATEGORY,
        severity=IssueSeverity.MEDIUM,
        observed_value="MAYBE",
        expected_condition="Value must be Y, N, Y13, or Y(13R).",
        confidence=1.0,
        uncertainty="No valid interpretation found.",
    )

    data = issue.model_dump()

    assert data["issue_id"] == "DQ-000004"
    assert data["issue_type"] == "invalid_category"
    assert data["severity"] == "medium"
    assert data["status"] == "detected"