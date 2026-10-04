from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, model_validator


class IssueType(str, Enum):
    MISSING_VALUE = "missing_value"
    INVALID_TYPE = "invalid_type"
    NEGATIVE_VALUE = "negative_value"
    INVALID_CATEGORY = "invalid_category"
    INVALID_RANGE = "invalid_range"
    FUTURE_YEAR = "future_year"
    DUPLICATE = "duplicate"
    STATISTICAL_ANOMALY = "statistical_anomaly"
    CROSS_FIELD_CONFLICT = "cross_field_conflict"
    FORMAT_INCONSISTENCY = "format_inconsistency"


class IssueSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


SEVERITY_RANK = {
    IssueSeverity.LOW: 1,
    IssueSeverity.MEDIUM: 2,
    IssueSeverity.HIGH: 3,
    IssueSeverity.CRITICAL: 4,
}


class IssueStatus(str, Enum):
    DETECTED = "detected"
    RECOMMENDED = "recommended"
    APPROVED = "approved"
    REJECTED = "rejected"
    ESCALATED = "escalated"
    RESOLVED = "resolved"


class QualityIssue(BaseModel):
    """
    Structured representation of a data-quality issue detected by Agent 3.

    row_index is None for dataset-level issues, such as a required
    column that is absent from the mapped data.
    """

    issue_id: str = Field(min_length=1)

    row_index: Optional[int] = None

    source_field: str = Field(min_length=1)

    target_field: Optional[str] = None

    issue_type: IssueType

    severity: IssueSeverity

    observed_value: Any = None

    expected_condition: str = Field(min_length=1)

    evidence: dict[str, Any] = Field(default_factory=dict)

    recommendation: Optional[str] = None

    confidence: float = Field(ge=0.0, le=1.0)

    uncertainty: str = Field(min_length=1)

    status: IssueStatus = IssueStatus.DETECTED

    # Stable machine-readable rule code, e.g. "zip.leading_zeros_lost".
    # Validators that do not set it get one derived from their evidence.
    rule_id: Optional[str] = None

    @model_validator(mode="after")
    def _derive_rule_id(self) -> "QualityIssue":
        if not self.rule_id:
            self.rule_id = (
                self.evidence.get("rule")
                or self.evidence.get("validation")
                or self.issue_type.value
            )

        return self
