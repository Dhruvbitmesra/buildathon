"""
Human review gate and re-reasoning loop for Agent 3.

ReviewLedger  -- serialisable record of every recommendation version
                 and every human action (lives in SOVState).
ReviewSession -- applies review actions, runs re-reasoning on
                 rejection, and builds the approved change plan for
                 Agent 4.

Flow for one recommendation (max_reasoning_attempts = 2):

    attempt 1 --approve--> APPROVED
        |
      reject (with reason)
        v
    re-reason (LLM or rule-based, validated) -> attempt 2
        |                      (no safe alternative -> ESCALATED)
      reject
        v
    ESCALATED --approve/edit--> RESOLVED with the reviewer's choice
              --reject-------> RESOLVED, source values kept

Nothing here mutates the DataFrame.
"""

from typing import Any, Optional

import pandas as pd
from pydantic import BaseModel, Field

from app.agents.data_quality import normalizers
from app.agents.data_quality.config import (
    SOV_ALLOWED_CATEGORIES,
    SOV_REQUIRED_FIELDS,
)
from app.agents.data_quality.decision_policy import DecisionPolicy
from app.agents.data_quality.issue_schema import IssueStatus
from app.agents.data_quality.normalizers import (
    LOSSLESS_OPERATIONS,
    Operation,
)
from app.agents.data_quality.reasoner import (
    Reasoner,
    ReasoningContext,
    ReasoningProposal,
    RuleBasedReasoner,
)
from app.agents.data_quality.recommendation_engine import (
    CandidateChecker,
    plain,
)
from app.agents.data_quality.recommendation_schema import (
    ActionType,
    ApprovedChange,
    BeforeAfter,
    ReasoningSource,
    Recommendation,
    ReviewAction,
    ReviewDecision,
    ReviewPolicy,
)
from app.agents.data_quality.us_reference import STATE_CODES


OPEN_STATUSES = {IssueStatus.RECOMMENDED, IssueStatus.ESCALATED}
DONE_STATUSES = {IssueStatus.APPROVED, IssueStatus.RESOLVED}


class ReviewItem(BaseModel):
    recommendation_id: str

    current: Recommendation

    # Earlier versions, oldest first (rejected attempts, pre-edit versions).
    history: list[Recommendation] = Field(default_factory=list)

    actions: list[ReviewAction] = Field(default_factory=list)

    @property
    def rejection_reasons(self) -> list[str]:
        return [
            action.reason or ""
            for action in self.actions
            if action.decision == ReviewDecision.REJECT
        ]

    @property
    def reasoning_attempt(self) -> int:
        return self.current.attempt

    @property
    def is_open(self) -> bool:
        return self.current.status in OPEN_STATUSES


class ReviewLedger(BaseModel):
    items: dict[str, ReviewItem] = Field(default_factory=dict)

    max_reasoning_attempts: int = Field(default=2, ge=1)

    @classmethod
    def from_recommendations(
        cls,
        recommendations: list[Recommendation],
        max_reasoning_attempts: int = 2,
    ) -> "ReviewLedger":
        return cls(
            items={
                rec.recommendation_id: ReviewItem(
                    recommendation_id=rec.recommendation_id,
                    current=rec,
                )
                for rec in recommendations
            },
            max_reasoning_attempts=max_reasoning_attempts,
        )

    def carry_over(self, previous: "ReviewLedger") -> "ReviewLedger":
        """
        Keep decisions from an earlier run (e.g. after a mapping edit)
        for recommendations that are unchanged.
        """

        items = dict(self.items)

        for rec_id, item in self.items.items():
            old = previous.items.get(rec_id)

            if old is None or not old.history and not old.actions:
                continue

            original = old.history[0] if old.history else old.current
            new = item.current

            def same(version: Recommendation) -> bool:
                return (
                    version.operation == new.operation
                    and version.after_value == new.after_value
                    and version.target_field == new.target_field
                    and version.affected_rows == new.affected_rows
                )

            # Unchanged proposal, or the new proposal is exactly what the
            # reviewer already decided (e.g. their own mapping edit).
            if same(original) or (
                old.current.status in DONE_STATUSES and same(old.current)
            ):
                items[rec_id] = old

        return self.model_copy(update={"items": items})

    def get(self, recommendation_id: str) -> ReviewItem:
        if recommendation_id not in self.items:
            raise KeyError(f"Unknown recommendation: {recommendation_id}")

        return self.items[recommendation_id]

    def current_recommendations(self) -> list[Recommendation]:
        return [item.current for item in self.items.values()]

    def pending(self) -> list[Recommendation]:
        return [
            item.current for item in self.items.values() if item.is_open
        ]

    @property
    def export_ready(self) -> bool:
        """FR-5: export is blocked until every item has a decision."""

        return not self.pending()

    def summary(self) -> dict[str, Any]:
        statuses: dict[str, int] = {}

        for item in self.items.values():
            key = item.current.status.value
            statuses[key] = statuses.get(key, 0) + 1

        return {
            "total": len(self.items),
            "by_status": statuses,
            "pending": len(self.pending()),
            "bulk_approvable_pending": sum(
                1
                for rec in self.pending()
                if rec.policy == ReviewPolicy.BULK_APPROVABLE
                and rec.status == IssueStatus.RECOMMENDED
            ),
            "escalated": statuses.get(IssueStatus.ESCALATED.value, 0),
            "export_ready": self.export_ready,
        }

    def audit_trail(self) -> list[dict[str, Any]]:
        """One row per human action, with the recommendation it acted on."""

        rows: list[dict[str, Any]] = []

        for item in self.items.values():
            for position, action in enumerate(item.actions):
                acted_on = (
                    item.history[position]
                    if position < len(item.history)
                    else item.current
                )
                rows.append(
                    {
                        "recommendation_id": item.recommendation_id,
                        "target_field": acted_on.target_field,
                        "issue_type": (
                            acted_on.issue_type.value
                            if acted_on.issue_type
                            else None
                        ),
                        "decision": action.decision.value,
                        "reviewer": action.reviewer,
                        "reason": action.reason,
                        "edited_value": action.edited_value,
                        "timestamp": action.timestamp.isoformat(),
                        "reasoning_attempt": acted_on.attempt,
                        "operation": acted_on.operation.value,
                        "after_value": acted_on.after_value,
                    }
                )

        return sorted(rows, key=lambda row: row["timestamp"])


class ReviewError(ValueError):
    """A review action that cannot be applied, with a readable message."""


class ReviewSession:
    """
    Applies human review actions to a ReviewLedger.

    The session holds a read-only reference to the canonical DataFrame
    so re-reasoned proposals can be previewed and validated against the
    real values. The ledger itself stores no raw rows.
    """

    def __init__(
        self,
        ledger: ReviewLedger,
        dataframe: pd.DataFrame | None = None,
        reasoner: Reasoner | None = None,
        fallback_reasoner: Reasoner | None = None,
        policy: DecisionPolicy | None = None,
        checker: CandidateChecker | None = None,
        source_rows: dict[int, int] | None = None,
        current_year: int | None = None,
    ) -> None:
        self.ledger = ledger
        self.dataframe = dataframe
        self.reasoner = reasoner
        self.fallback_reasoner = fallback_reasoner or RuleBasedReasoner()
        self.policy = policy or DecisionPolicy()
        self.checker = checker or CandidateChecker(current_year)
        self.source_rows = source_rows or {}

    # -----------------------------------------------------------------
    # Review actions
    # -----------------------------------------------------------------

    def submit(self, action: ReviewAction) -> Recommendation:
        """Apply one review action and return the item's current version."""

        item = self.ledger.get(action.recommendation_id)
        current = item.current

        if not item.is_open:
            raise ReviewError(
                f"{action.recommendation_id} is already "
                f"{current.status.value}; it cannot be reviewed again."
            )

        escalated = current.status == IssueStatus.ESCALATED
        final_status = IssueStatus.RESOLVED if escalated else IssueStatus.APPROVED

        if action.decision == ReviewDecision.APPROVE:
            new = current.model_copy(update={"status": final_status})

        elif action.decision == ReviewDecision.EDIT:
            new = self._edited(current, action, final_status)

        elif action.decision == ReviewDecision.ESCALATE:
            new = current.model_copy(
                update={
                    "status": IssueStatus.ESCALATED,
                    "policy_reasons": current.policy_reasons
                    + [f"Escalated by {action.reviewer}: {action.reason or ''}"],
                }
            )

        elif escalated:
            # Rejecting an escalated item means "change nothing".
            new = self._keep_unchanged(current, action)

        else:
            new = self._rejected(item, action)

        # Each action archives exactly one version: action i acted on
        # history[i].
        if action.decision == ReviewDecision.REJECT:
            item.history.append(
                current.model_copy(update={"status": IssueStatus.REJECTED})
            )
        else:
            item.history.append(current)

        item.actions.append(action)
        item.current = new

        return new

    def approve_all_bulk(self, reviewer: str) -> list[Recommendation]:
        """FR-5 "Approve All": approve every pending bulk-approvable item."""

        approved: list[Recommendation] = []

        for rec in list(self.ledger.pending()):
            if (
                rec.policy == ReviewPolicy.BULK_APPROVABLE
                and rec.status == IssueStatus.RECOMMENDED
            ):
                approved.append(
                    self.submit(
                        ReviewAction(
                            recommendation_id=rec.recommendation_id,
                            decision=ReviewDecision.APPROVE,
                            reviewer=reviewer,
                            reason="Approve All (bulk-approvable item).",
                        )
                    )
                )

        return approved

    # -----------------------------------------------------------------
    # Change plan for Agent 4
    # -----------------------------------------------------------------

    def approved_changes(self) -> list[ApprovedChange]:
        """
        Every approved cell change and column mapping, with the audit
        fields FR-6 requires. Approved KEEP items produce no change.
        """

        changes: list[ApprovedChange] = []

        for item in self.ledger.items.values():
            rec = item.current

            if rec.status not in DONE_STATUSES:
                continue

            approval = next(
                (
                    action
                    for action in reversed(item.actions)
                    if action.decision
                    in {ReviewDecision.APPROVE, ReviewDecision.EDIT}
                ),
                item.actions[-1] if item.actions else None,
            )

            if approval is None:
                continue

            if rec.operation == Operation.RENAME_COLUMN:
                changes.append(
                    self._change(
                        rec,
                        approval,
                        row=None,
                        before=rec.source_column,
                        after=rec.target_field,
                    )
                )
                continue

            if not rec.changes_values:
                continue

            per_row = rec.operation_params.get("values")

            for row in rec.affected_rows:
                before = self._value(row, rec.target_field)
                params = (
                    {"value": per_row[str(row)]}
                    if per_row is not None
                    else rec.operation_params
                )
                result = normalizers.apply_operation(
                    rec.operation,
                    before,
                    params,
                )

                if not result.ok:
                    raise ReviewError(
                        f"{rec.recommendation_id}: {result.error} "
                        f"(row {row})."
                    )

                changes.append(
                    self._change(
                        rec,
                        approval,
                        row=row,
                        before=before,
                        after=result.value,
                    )
                )

        return changes

    # -----------------------------------------------------------------
    # Internals
    # -----------------------------------------------------------------

    def _rejected(self, item: ReviewItem, action: ReviewAction) -> Recommendation:
        current = item.current

        if current.attempt >= self.ledger.max_reasoning_attempts:
            return self._escalate(
                current,
                f"Rejected {current.attempt} time(s); maximum automatic "
                "re-reasoning reached.",
            )

        context = ReasoningContext(
            recommendation=current,
            rejection_reason=action.reason or "",
            attempt=current.attempt + 1,
            allowed_operations=sorted(
                self._allowed_operations(current),
                key=lambda op: op.value,
            ),
            allowed_values=self._allowed_values(current),
            rejected_proposals=[
                (version.operation.value, self._proposal_value(version))
                for version in item.history + [current]
            ],
        )

        for reasoner, source in (
            (self.reasoner, ReasoningSource.LLM),
            (self.fallback_reasoner, ReasoningSource.DETERMINISTIC),
        ):
            if reasoner is None:
                continue

            try:
                proposal = reasoner.reconsider(context)
            except Exception:
                proposal = None

            if proposal is None:
                continue

            problem = self._proposal_problem(proposal, context)

            if problem is None:
                return self._from_proposal(current, proposal, context, source)

        return self._escalate(
            current,
            "No safe alternative recommendation could be produced from "
            "the reviewer's feedback.",
        )

    def _from_proposal(
        self,
        current: Recommendation,
        proposal: ReasoningProposal,
        context: ReasoningContext,
        source: ReasoningSource,
    ) -> Recommendation:
        operation = proposal.operation
        params: dict[str, Any] = {}
        after: Any = current.before_value
        target_field = current.target_field
        action_type = ActionType.FLAG_FOR_REVIEW
        lossless = False

        if self._is_mapping(current):
            if operation == Operation.RENAME_COLUMN:
                target_field = proposal.value
                after = proposal.value
                action_type = ActionType.COLUMN_MAPPING
                params = {"source_column": current.source_column}
                lossless = True
            else:
                target_field = None
                after = None

        elif operation == Operation.SET_VALUE:
            params = {"value": proposal.value}
            after = proposal.value
            action_type = ActionType.DATA_CORRECTION

        elif operation != Operation.KEEP:
            params = (
                dict(current.operation_params)
                if operation == current.operation
                else {}
            )
            result = normalizers.apply_operation(
                operation,
                current.before_value,
                params,
            )
            after = result.value
            lossless = operation in LOSSLESS_OPERATIONS
            action_type = (
                ActionType.STANDARDISATION
                if lossless
                else ActionType.DATA_CORRECTION
            )

        samples = [
            BeforeAfter(
                row_index=sample.row_index,
                source_row=sample.source_row,
                before=sample.before,
                after=(
                    normalizers.apply_operation(
                        operation, sample.before, params
                    ).value
                    if operation
                    not in {Operation.KEEP, Operation.RENAME_COLUMN}
                    else sample.before
                ),
            )
            for sample in current.samples
        ]

        rows = f"{current.affected_row_count} row(s)"

        if self._is_mapping(current):
            title = (
                f"Map column '{current.source_column}' to {target_field}"
                if operation == Operation.RENAME_COLUMN
                else f"Leave column '{current.source_column}' unmapped"
            )
        elif operation == Operation.KEEP:
            title = f"{current.target_field}: keep source values ({rows})"
        elif operation == Operation.SET_VALUE:
            title = f"{current.target_field}: set {after!r} ({rows})"
        else:
            title = (
                f"{current.target_field}: {operation.value.replace('_', ' ')} "
                f"({rows})"
            )

        new = current.model_copy(
            update={
                "title": f"{title} - revised after rejection",
                "action_type": action_type,
                "operation": operation,
                "operation_params": params,
                "target_field": target_field,
                "after_value": after,
                "samples": samples,
                "lossless": lossless,
                "rationale": (
                    f"{proposal.rationale} (Re-assessed after rejection: "
                    f"\"{context.rejection_reason}\".)"
                ),
                "uncertainty": proposal.uncertainty,
                "fix_confidence": proposal.confidence,
                "attempt": context.attempt,
                "parent_recommendation_id": (
                    f"{current.recommendation_id}#attempt{current.attempt}"
                ),
                "reasoning_source": source,
                "status": IssueStatus.RECOMMENDED,
            }
        )

        return self.policy.apply(new)

    def _proposal_problem(
        self,
        proposal: ReasoningProposal,
        context: ReasoningContext,
    ) -> Optional[str]:
        """Guardrails for reasoner output. None means acceptable."""

        current = context.recommendation

        if proposal.operation not in context.allowed_operations:
            return f"{proposal.operation.value} is not allowed here"

        key = (proposal.operation.value, self._normalise_value(proposal.value))

        if key in {
            (op, self._normalise_value(value))
            for op, value in context.rejected_proposals
        }:
            return "repeats a rejected proposal"

        if proposal.operation in {Operation.SET_VALUE, Operation.RENAME_COLUMN}:
            value = proposal.value

            if value is None:
                return "a value is required"

            in_allowed = str(value) in context.allowed_values
            in_note = str(value).lower() in context.rejection_reason.lower()

            if not (in_allowed or in_note):
                return "value is neither an allowed value nor in the note"

            if proposal.operation == Operation.RENAME_COLUMN:
                return self._mapping_problem(current, value)

            if not self._single_source_value(current):
                return "one value cannot replace different source values"

            if self.checker.problems(current.target_field, value):
                return "value fails validation"

            return None

        if proposal.operation in {Operation.KEEP, Operation.SET_BLANK}:
            return None

        # A deterministic operation must convert every affected row and
        # each result must pass validation ("validation again").
        for row in current.affected_rows:
            before = self._value(row, current.target_field)
            result = normalizers.apply_operation(
                proposal.operation,
                before,
                current.operation_params
                if proposal.operation == current.operation
                else {},
            )

            if not result.ok:
                return result.error

            if self.checker.problems(current.target_field, result.value):
                return f"converted value {result.value!r} fails validation"

        return None

    def _edited(
        self,
        current: Recommendation,
        action: ReviewAction,
        final_status: IssueStatus,
    ) -> Recommendation:
        value = action.edited_value

        if self._is_mapping(current):
            if value is not None:
                problem = self._mapping_problem(current, value)

                if problem:
                    raise ReviewError(problem)

            return current.model_copy(
                update={
                    "action_type": (
                        ActionType.COLUMN_MAPPING
                        if value is not None
                        else ActionType.FLAG_FOR_REVIEW
                    ),
                    "operation": (
                        Operation.RENAME_COLUMN
                        if value is not None
                        else Operation.KEEP
                    ),
                    "operation_params": (
                        {"source_column": current.source_column}
                        if value is not None
                        else {}
                    ),
                    "target_field": value,
                    "after_value": value,
                    "title": (
                        f"Map column '{current.source_column}' to {value} "
                        "(set by reviewer)"
                        if value is not None
                        else f"Leave column '{current.source_column}' "
                        "unmapped (set by reviewer)"
                    ),
                    "fix_confidence": 1.0,
                    "reasoning_source": ReasoningSource.HUMAN,
                    "rationale": (
                        f"{action.reviewer} mapped '{current.source_column}' "
                        f"to {value}."
                        if value is not None
                        else f"{action.reviewer} left "
                        f"'{current.source_column}' unmapped."
                    ),
                    "status": final_status,
                }
            )

        if not current.affected_rows:
            raise ReviewError(
                "This item is not tied to specific cells; edit the column "
                "mapping instead."
            )

        # A dict edits rows individually: {row_index: value}. Rows not
        # listed keep their source value.
        if isinstance(value, dict):
            per_row = {int(row): plain(v) for row, v in value.items()}
            unknown = set(per_row) - set(current.affected_rows)

            if unknown:
                raise ReviewError(
                    f"Rows {sorted(unknown)} are not part of this item."
                )
        else:
            if not self._single_source_value(current):
                raise ReviewError(
                    f"This item covers {current.affected_row_count} rows "
                    "with different source values. Supply edited_value as "
                    "{row_index: value} so each row gets its own value."
                )

            per_row = {row: plain(value) for row in current.affected_rows}

        for row, row_value in per_row.items():
            problems = self.checker.problems(current.target_field, row_value)

            if problems:
                raise ReviewError(
                    f"The edited value {row_value!r} (row {row}) is not "
                    f"valid for {current.target_field}: {problems[0]}"
                )

        distinct = {repr(v) for v in per_row.values()}
        single = next(iter(per_row.values())) if len(distinct) == 1 else None
        uniform = len(distinct) == 1 and len(per_row) == len(
            current.affected_rows
        )

        if uniform and single is None:
            operation, params = Operation.SET_BLANK, {}
        else:
            operation = Operation.SET_VALUE
            params = (
                {"value": single}
                if uniform
                else {"values": {str(row): v for row, v in per_row.items()}}
            )

        return current.model_copy(
            update={
                "action_type": ActionType.DATA_CORRECTION,
                "operation": operation,
                "operation_params": params,
                "affected_rows": sorted(per_row),
                "affected_row_count": len(per_row),
                "after_value": single if uniform else None,
                "samples": [
                    sample.model_copy(
                        update={"after": per_row.get(sample.row_index)}
                    )
                    for sample in current.samples
                    if sample.row_index in per_row
                ],
                "title": (
                    f"{current.target_field}: reviewer-supplied value(s) "
                    f"({len(per_row)} row(s))"
                ),
                "fix_confidence": 1.0,
                "reasoning_source": ReasoningSource.HUMAN,
                "rationale": (
                    f"{action.reviewer} supplied the value(s) for "
                    f"{len(per_row)} row(s). " + (action.reason or "")
                ).strip(),
                "status": final_status,
            }
        )

    def _single_source_value(self, rec: Recommendation) -> bool:
        """True when every affected row has the same source value."""

        if self.dataframe is None or rec.target_field not in self.dataframe:
            return rec.affected_row_count <= 1

        values = {
            repr(self._value(row, rec.target_field))
            for row in rec.affected_rows
        }
        return len(values) <= 1

    def _keep_unchanged(
        self,
        current: Recommendation,
        action: ReviewAction,
    ) -> Recommendation:
        is_mapping = self._is_mapping(current)

        return current.model_copy(
            update={
                "action_type": ActionType.FLAG_FOR_REVIEW,
                "operation": Operation.KEEP,
                "operation_params": {},
                "target_field": None if is_mapping else current.target_field,
                "after_value": None if is_mapping else current.before_value,
                "rationale": (
                    f"{action.reviewer} rejected the escalated proposal; "
                    "the source values are kept unchanged. "
                    f"Reason: {action.reason}"
                ),
                "reasoning_source": ReasoningSource.HUMAN,
                "status": IssueStatus.RESOLVED,
            }
        )

    def _escalate(self, current: Recommendation, reason: str) -> Recommendation:
        return current.model_copy(
            update={
                "status": IssueStatus.ESCALATED,
                "policy": ReviewPolicy.HUMAN_REVIEW_REQUIRED,
                "policy_reasons": current.policy_reasons + [reason],
            }
        )

    def _mapping_problem(self, current: Recommendation, target: Any) -> Optional[str]:
        if target not in SOV_REQUIRED_FIELDS:
            return f"{target!r} is not one of the 17 target fields"

        for item in self.ledger.items.values():
            other = item.current

            if (
                other.recommendation_id != current.recommendation_id
                and self._is_mapping(other)
                and other.operation == Operation.RENAME_COLUMN
                and other.target_field == target
                and other.status != IssueStatus.REJECTED
            ):
                return (
                    f"{target} is already mapped from "
                    f"'{other.source_column}'"
                )

        return None

    @staticmethod
    def _is_mapping(rec: Recommendation) -> bool:
        return (
            rec.action_type == ActionType.COLUMN_MAPPING
            or rec.rule_id in {"schema_mapping", "column_unmapped"}
        )

    def _allowed_operations(self, rec: Recommendation) -> set[Operation]:
        if self._is_mapping(rec):
            return {Operation.RENAME_COLUMN, Operation.KEEP}

        if not rec.affected_rows:
            return {Operation.KEEP}

        return normalizers.allowed_operations_for(rec.target_field)

    def _allowed_values(self, rec: Recommendation) -> list[str]:
        if self._is_mapping(rec):
            return list(SOV_REQUIRED_FIELDS)

        field = rec.target_field

        if field in SOV_ALLOWED_CATEGORIES:
            return sorted(SOV_ALLOWED_CATEGORIES[field])

        if field == "State":
            return sorted(STATE_CODES)

        return []

    @staticmethod
    def _proposal_value(rec: Recommendation) -> Any:
        if rec.operation == Operation.SET_VALUE:
            return rec.operation_params.get("value")

        if rec.operation == Operation.RENAME_COLUMN:
            return rec.target_field

        return None

    @staticmethod
    def _normalise_value(value: Any) -> str:
        return str(value)

    def _value(self, row: int, field: str | None) -> Any:
        if (
            self.dataframe is None
            or field is None
            or field not in self.dataframe.columns
        ):
            raise ReviewError(
                "The canonical DataFrame is required to compute changes."
            )

        return plain(self.dataframe.at[row, field])

    def _change(
        self,
        rec: Recommendation,
        approval: ReviewAction,
        row: Optional[int],
        before: Any,
        after: Any,
    ) -> ApprovedChange:
        return ApprovedChange(
            recommendation_id=rec.recommendation_id,
            source_column=rec.source_column,
            target_column=rec.target_field,
            row_index=row,
            source_row=self.source_rows.get(row) if row is not None else None,
            transformation_applied=rec.operation,
            operation_params=rec.operation_params,
            before_value=before,
            after_value=after,
            confidence=rec.fix_confidence,
            rationale=rec.rationale,
            approved_by=approval.reviewer,
            timestamp=approval.timestamp,
            reasoning_attempt=rec.attempt,
        )
