"""
Typed contract for Agent 3's output.

Recommendation  -- one grouped, explainable proposal (e.g. "YES -> Y in
                   412 rows"), queued for human review.
ReviewAction    -- one human decision on a recommendation.
ApprovedChange  -- one approved cell change, handed to Agent 4.

Agent 3 never mutates the DataFrame. Agent 4 applies ApprovedChange
objects using the same normalizers that produced the preview.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, model_validator

from app.agents.data_quality.issue_schema import (
    IssueSeverity,
    IssueStatus,
    IssueType,
)
from app.agents.data_quality.normalizers import (
    VALUE_CHANGING_OPERATIONS,
    Operation,
)


class ActionType(str, Enum):
    """Action types required by FR-4."""

    COLUMN_MAPPING = "column_mapping"
    DATA_CORRECTION = "data_correction"
    STANDARDISATION = "standardisation"
    FLAG_FOR_REVIEW = "flag_for_review"


class ReviewPolicy(str, Enum):
    """
    How a recommendation may be reviewed.

    Nothing is ever applied without a human decision (C-01).
    BULK_APPROVABLE only means the item may be cleared by the
    reviewer's "Approve All" action (FR-5).
    """

    BULK_APPROVABLE = "bulk_approvable"
    HUMAN_REVIEW_REQUIRED = "human_review_required"


class ReasoningSource(str, Enum):
    DETERMINISTIC = "deterministic"
    LLM = "llm"
    HUMAN = "human"


class Evidence(BaseModel):
    """Why the recommendation was made."""

    rule_id: str = Field(min_length=1)

    expected_condition: str = Field(min_length=1)

    observed_values: list[Any] = Field(default_factory=list)

    statistical_context: dict[str, Any] = Field(default_factory=dict)

    field_context: dict[str, Any] = Field(default_factory=dict)

    related_rules: list[str] = Field(default_factory=list)

    reasoning_source: ReasoningSource = ReasoningSource.DETERMINISTIC


class BeforeAfter(BaseModel):
    """One previewed cell. after is None when the cell stays/becomes blank."""

    row_index: Optional[int] = None

    # 1-based row number in the source workbook, when known.
    source_row: Optional[int] = None

    before: Any = None

    after: Any = None


class Recommendation(BaseModel):
    recommendation_id: str = Field(min_length=1)

    action_type: ActionType

    operation: Operation

    operation_params: dict[str, Any] = Field(default_factory=dict)

    target_field: Optional[str] = None

    source_column: Optional[str] = None

    issue_type: Optional[IssueType] = None

    rule_id: str = Field(min_length=1)

    severity: IssueSeverity

    issue_ids: list[str] = Field(default_factory=list)

    affected_rows: list[int] = Field(default_factory=list)

    affected_row_count: int = Field(ge=0)

    # Representative values; full per-row values live in samples and,
    # for approved items, in ApprovedChange.
    before_value: Any = None

    after_value: Any = None

    samples: list[BeforeAfter] = Field(default_factory=list)

    title: str = Field(min_length=1)

    rationale: str = Field(min_length=1)

    uncertainty: str = Field(min_length=1)

    evidence: Evidence

    # True when the operation only changes representation, not meaning.
    lossless: bool = False

    # Confidence that the issue exists.
    detection_confidence: float = Field(ge=0.0, le=1.0)

    # Confidence that the proposed operation is the right fix.
    fix_confidence: float = Field(ge=0.0, le=1.0)

    policy: ReviewPolicy = ReviewPolicy.HUMAN_REVIEW_REQUIRED

    policy_reasons: list[str] = Field(default_factory=list)

    attempt: int = Field(default=1, ge=1)

    parent_recommendation_id: Optional[str] = None

    reasoning_source: ReasoningSource = ReasoningSource.DETERMINISTIC

    # Optional LLM explanation of business impact; never changes the
    # operation or values.
    llm_explanation: Optional[str] = None

    status: IssueStatus = IssueStatus.RECOMMENDED

    @property
    def requires_human_approval(self) -> bool:
        # Every recommendation needs a human decision before Agent 4
        # applies it; this property exists to make that explicit.
        return True

    @property
    def changes_values(self) -> bool:
        return self.operation in VALUE_CHANGING_OPERATIONS

    @model_validator(mode="after")
    def _check_consistency(self) -> "Recommendation":
        if (
            self.action_type == ActionType.FLAG_FOR_REVIEW
            and self.operation != Operation.KEEP
        ):
            raise ValueError("flag_for_review must use the KEEP operation")

        if (
            self.action_type == ActionType.COLUMN_MAPPING
            and self.operation not in {Operation.RENAME_COLUMN, Operation.KEEP}
        ):
            raise ValueError(
                "column_mapping must use RENAME_COLUMN or KEEP"
            )

        if self.operation == Operation.SET_BLANK and self.after_value is not None:
            raise ValueError("set_blank must have after_value None")

        if self.operation == Operation.SET_VALUE and not (
            {"value", "values"} & set(self.operation_params)
        ):
            raise ValueError(
                "set_value requires operation_params['value'] or "
                "operation_params['values'] (per row)"
            )

        if self.affected_row_count < len(self.affected_rows):
            raise ValueError(
                "affected_row_count cannot be less than affected_rows"
            )

        return self


class ReviewDecision(str, Enum):
    APPROVE = "approve"
    REJECT = "reject"
    EDIT = "edit"
    ESCALATE = "escalate"


class ReviewAction(BaseModel):
    """One human decision. A rejection must say why."""

    recommendation_id: str = Field(min_length=1)

    decision: ReviewDecision

    reviewer: str = Field(min_length=1)

    reason: Optional[str] = None

    # EDIT only: the value (or, for column mappings, target field) the
    # reviewer wants instead.
    edited_value: Any = None

    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    @model_validator(mode="after")
    def _check_reason(self) -> "ReviewAction":
        if self.decision == ReviewDecision.REJECT and not (
            self.reason and self.reason.strip()
        ):
            raise ValueError("a rejection must include a reason")

        if (
            self.decision == ReviewDecision.EDIT
            and "edited_value" not in self.model_fields_set
        ):
            raise ValueError("an edit must include edited_value")

        return self


class ApprovedChange(BaseModel):
    """
    One approved cell change for Agent 4, carrying every audit field
    FR-6 requires.
    """

    recommendation_id: str

    source_column: Optional[str] = None

    target_column: Optional[str] = None

    row_index: Optional[int] = None

    source_row: Optional[int] = None

    transformation_applied: Operation

    operation_params: dict[str, Any] = Field(default_factory=dict)

    before_value: Any = None

    after_value: Any = None

    confidence: float = Field(ge=0.0, le=1.0)

    rationale: str

    approved_by: str

    timestamp: datetime

    reasoning_attempt: int = Field(ge=1)
