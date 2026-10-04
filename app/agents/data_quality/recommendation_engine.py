"""
Deterministic recommendation engine for Agent 3.

Turns consolidated QualityIssue objects (and Agent 2 column mappings)
into grouped, explainable Recommendation objects.

Grouping: one recommendation per pattern, not per cell. "YES -> Y" in
412 rows is one review item. A reviewer can act on a few dozen items
instead of thousands of cells.

Safety:
- Candidate values come only from the shared normalizers.
- Every candidate is re-validated with the deterministic validator;
  if it would still fail, the item is downgraded to flag_for_review.
- Missing, negative, duplicate, out-of-range and anomalous values are
  never given a replacement value; they are flagged and kept.
"""

import hashlib
from dataclasses import dataclass, field
from typing import Any, Iterable, Optional

import pandas as pd

from app.agents.data_quality import normalizers
from app.agents.data_quality.config import get_sov_validation_config
from app.agents.data_quality.decision_policy import DecisionPolicy
from app.agents.data_quality.issue_schema import (
    SEVERITY_RANK,
    IssueSeverity,
    IssueType,
    QualityIssue,
)
from app.agents.data_quality.normalizers import Operation
from app.agents.data_quality.recommendation_schema import (
    ActionType,
    BeforeAfter,
    Evidence,
    Recommendation,
)


HIGH_IMPACT_FIELDS = {
    "Building Value",
    "Contents",
    "BI",
    "Occupancy",
    "Construction",
    "Storeys",
    "Number of Buildings",
    "Year Built",
    "Fire Sprinklers (Y/N)",
}

# Issue types whose value can be replaced by a normalizer proposal.
_FIXABLE_TYPES = {
    IssueType.FORMAT_INCONSISTENCY,
    IssueType.INVALID_TYPE,
    IssueType.INVALID_CATEGORY,
}

# Range/future-year issues only accept the placeholder -> blank proposal.
_PLACEHOLDER_TYPES = {
    IssueType.FUTURE_YEAR,
    IssueType.INVALID_RANGE,
}

OPERATION_PHRASES = {
    Operation.PARSE_MONETARY: "convert text amounts to numbers",
    Operation.PARSE_INTEGER: "convert numeric text to whole numbers",
    Operation.EXTRACT_YEAR: "keep only the year from full dates",
    Operation.PAD_ZIP: "restore leading zeros",
    Operation.TRIM_WHITESPACE: "remove extra spaces",
    Operation.SET_VALUE: "set the reviewer-supplied value",
}

# Operations whose result depends only on the before value: group by it.
_GROUP_BY_VALUE_OPERATIONS = {
    Operation.CANONICALIZE_SPRINKLER,
    Operation.STANDARDISE_STATE,
}


def plain(value: Any) -> Any:
    """Convert numpy/pandas scalars and NaN into plain Python values."""

    if normalizers.is_missing(value):
        return None

    if hasattr(value, "item") and not isinstance(value, (str, bytes)):
        try:
            return value.item()
        except (TypeError, ValueError):
            return value

    return value


def stable_id(prefix: str, *parts: Any) -> str:
    digest = hashlib.sha1(repr(parts).encode("utf-8")).hexdigest()[:10]
    return f"{prefix}-{digest}"


class CandidateChecker:
    """
    "Validation again": a proposed value must pass the same
    deterministic validator that detected the original issue.
    """

    def __init__(self, current_year: int | None = None) -> None:
        # Imported here to avoid a circular import with validator.py.
        from app.agents.data_quality.validator import DeterministicValidator

        self.validator = DeterministicValidator()
        self.config = get_sov_validation_config()
        self.current_year = current_year
        # Large files repeat the same candidate values thousands of
        # times; validating each distinct value once is enough.
        self._cache: dict[tuple, list[str]] = {}

    def problems(
        self,
        field_name: str,
        value: Any,
        country: Any = None,
    ) -> list[str]:
        """Return the problems the value would still have (empty = OK)."""

        # A blank result is always allowed: it preserves missing data
        # instead of inventing it (C-02).
        if value is None:
            return []

        key = (
            field_name,
            type(value).__name__,
            repr(value),
            normalizers.is_us_country(country),
        )

        if key in self._cache:
            return list(self._cache[key])

        result = self._problems(field_name, value, country)
        self._cache[key] = result
        return list(result)

    def _problems(
        self,
        field_name: str,
        value: Any,
        country: Any,
    ) -> list[str]:
        data: dict[str, list[Any]] = {field_name: [value]}

        if field_name != "Country" and not normalizers.is_missing(country):
            data["Country"] = [country]

        frame = pd.DataFrame(data, dtype=object)

        issues = self.validator.validate(
            dataframe=frame,
            field_types={
                key: value_type
                for key, value_type in self.config["field_types"].items()
                if key == field_name
            },
            non_negative_fields=self.config["non_negative_fields"],
            allowed_categories=self.config["allowed_categories"],
            field_ranges=self.config["field_ranges"],
            current_year=self.current_year,
        )

        return [
            f"{issue.issue_type.value}: {issue.expected_condition}"
            for issue in issues
            if issue.source_field == field_name
        ]


@dataclass
class _Plan:
    action: ActionType
    operation: Operation
    after: Any
    fix_confidence: float
    reason: str
    lossless: bool = False
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class _Group:
    key: tuple
    plans: list[tuple[QualityIssue, _Plan]] = field(default_factory=list)


class RecommendationEngine:
    def __init__(
        self,
        policy: DecisionPolicy | None = None,
        checker: CandidateChecker | None = None,
        max_samples: int = 5,
    ) -> None:
        self.policy = policy or DecisionPolicy()
        self.checker = checker
        self.max_samples = max_samples

    # -----------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------

    def build(
        self,
        issues: list[QualityIssue],
        dataframe: pd.DataFrame | None = None,
        mappings: Iterable[Any] | None = None,
        source_rows: dict[int, int] | None = None,
        source_columns: dict[str, str] | None = None,
        current_year: int | None = None,
    ) -> list[Recommendation]:
        """
        Build the review queue.

        Parameters
        ----------
        issues:
            Consolidated issues from DeterministicValidator.validate_sov().
        dataframe:
            The canonical DataFrame the issues were detected on. Used
            for row context (Country) and column context (sprinkler
            scale). Never modified.
        mappings:
            Agent 2 mappings (objects or dicts with source_header,
            target_field, score/confidence, method, reason).
        source_rows:
            row_index -> 1-based workbook row, for reviewer display.
        source_columns:
            target field -> source header, for the audit trail.
        """

        checker = self.checker or CandidateChecker(current_year)
        source_rows = source_rows or {}
        source_columns = source_columns or {}

        sprinkler_scale = None

        if (
            dataframe is not None
            and normalizers.SPRINKLER_FIELD in dataframe.columns
        ):
            sprinkler_scale = normalizers.infer_sprinkler_scale(
                dataframe[normalizers.SPRINKLER_FIELD].dropna().tolist()
            )

        groups: dict[tuple, _Group] = {}

        for issue in issues:
            country = self._row_value(dataframe, issue.row_index, "Country")
            context = {
                "is_us": normalizers.is_us_country(country),
                "sprinkler_scale": sprinkler_scale,
            }

            plan = self._plan(issue, context, checker, country)
            key = self._group_key(issue, plan)

            groups.setdefault(key, _Group(key=key)).plans.append(
                (issue, plan)
            )

        recommendations = [
            self._to_recommendation(group, source_rows, source_columns)
            for group in groups.values()
        ]

        recommendations.extend(
            self._mapping_recommendations(mappings or [])
        )

        recommendations = [
            self.policy.apply(recommendation)
            for recommendation in recommendations
        ]

        return sorted(recommendations, key=self._priority)

    # -----------------------------------------------------------------
    # Planning
    # -----------------------------------------------------------------

    def _plan(
        self,
        issue: QualityIssue,
        context: dict[str, Any],
        checker: CandidateChecker,
        country: Any,
    ) -> _Plan:
        keep = _Plan(
            action=ActionType.FLAG_FOR_REVIEW,
            operation=Operation.KEEP,
            after=plain(issue.observed_value),
            fix_confidence=issue.confidence,
            reason="",
        )

        if issue.row_index is None:
            return keep

        proposal = normalizers.propose(
            issue.source_field,
            issue.observed_value,
            context,
        )

        if proposal is None:
            return keep

        if issue.issue_type in _PLACEHOLDER_TYPES:
            if proposal.operation != Operation.SET_BLANK:
                return keep

        elif issue.issue_type not in _FIXABLE_TYPES:
            return keep

        problems = checker.problems(
            issue.source_field,
            proposal.after_value,
            country,
        )

        if problems:
            keep.reason = (
                f"Converting to {proposal.after_value!r} would still "
                f"fail validation ({problems[0]}), so the value is "
                "flagged instead."
            )
            return keep

        return _Plan(
            action=(
                ActionType.STANDARDISATION
                if proposal.lossless
                else ActionType.DATA_CORRECTION
            ),
            operation=proposal.operation,
            after=proposal.after_value,
            fix_confidence=proposal.confidence,
            reason=proposal.reason,
            lossless=bool(proposal.lossless),
            params=dict(proposal.params),
        )

    @staticmethod
    def _group_key(issue: QualityIssue, plan: _Plan) -> tuple:
        if issue.row_index is None:
            return ("dataset", issue.issue_id)

        group_value = None

        # Text categories ("MAYBE", "Manual Pull") are reviewed per value;
        # numeric ones (partial coverage 0.02, 0.57, ...) per rule.
        if plan.operation in _GROUP_BY_VALUE_OPERATIONS or (
            plan.operation == Operation.KEEP
            and issue.issue_type == IssueType.INVALID_CATEGORY
            and isinstance(issue.observed_value, str)
        ):
            group_value = " ".join(
                str(issue.observed_value).strip().upper().split()
            )

        return (
            issue.source_field,
            issue.issue_type.value,
            issue.rule_id,
            plan.action.value,
            plan.operation.value,
            tuple(sorted(plan.params.items())),
            group_value,
        )

    # -----------------------------------------------------------------
    # Recommendation construction
    # -----------------------------------------------------------------

    def _to_recommendation(
        self,
        group: _Group,
        source_rows: dict[int, int],
        source_columns: dict[str, str],
    ) -> Recommendation:
        first_issue, first_plan = group.plans[0]
        issues = [issue for issue, _ in group.plans]
        field_name = first_issue.source_field

        severity = max(
            (issue.severity for issue in issues),
            key=lambda s: SEVERITY_RANK[s],
        )

        rows = [
            issue.row_index for issue in issues if issue.row_index is not None
        ]

        if first_issue.row_index is None:
            row_count = int(first_issue.evidence.get("row_count", 0))
        else:
            row_count = len(rows)

        samples = [
            BeforeAfter(
                row_index=issue.row_index,
                source_row=source_rows.get(issue.row_index),
                before=plain(issue.observed_value),
                after=plain(plan.after),
            )
            for issue, plan in group.plans[: self.max_samples]
        ]

        related_rules = sorted(
            {
                related["rule_id"]
                for issue in issues
                for related in issue.evidence.get("related_issues", [])
                if related.get("rule_id")
            }
        )

        statistical_context = next(
            (
                issue.evidence.get("statistical_context")
                or (
                    issue.evidence
                    if issue.issue_type == IssueType.STATISTICAL_ANOMALY
                    else None
                )
                for issue in issues
                if issue.evidence.get("statistical_context")
                or issue.issue_type == IssueType.STATISTICAL_ANOMALY
            ),
            None,
        ) or {}

        field_context = {
            key: plain(value) if not isinstance(value, (list, dict)) else value
            for key, value in first_issue.evidence.items()
            if key not in {"related_issues", "statistical_context"}
        }

        distinct_before = []

        for issue in issues:
            value = plain(issue.observed_value)

            if value not in distinct_before:
                distinct_before.append(value)

            if len(distinct_before) >= 10:
                break

        evidence = Evidence(
            rule_id=first_issue.rule_id,
            expected_condition=first_issue.expected_condition,
            observed_values=distinct_before,
            statistical_context=statistical_context,
            field_context=field_context,
            related_rules=related_rules,
        )

        title, rationale = self._explain(
            field_name=field_name,
            issue=first_issue,
            plan=first_plan,
            row_count=row_count,
            examples=distinct_before[:3],
        )

        uncertainty = first_issue.uncertainty

        if first_plan.reason and first_plan.operation == Operation.KEEP:
            uncertainty = f"{uncertainty} {first_plan.reason}"

        return Recommendation(
            recommendation_id=stable_id("REC", group.key),
            action_type=first_plan.action,
            operation=first_plan.operation,
            operation_params=first_plan.params,
            target_field=first_issue.target_field,
            source_column=source_columns.get(field_name),
            issue_type=first_issue.issue_type,
            rule_id=first_issue.rule_id,
            severity=severity,
            issue_ids=[issue.issue_id for issue in issues],
            affected_rows=rows,
            affected_row_count=max(row_count, len(rows)),
            before_value=plain(first_issue.observed_value),
            after_value=plain(first_plan.after),
            samples=samples,
            title=title,
            rationale=rationale,
            uncertainty=uncertainty,
            evidence=evidence,
            detection_confidence=min(issue.confidence for issue in issues),
            fix_confidence=min(plan.fix_confidence for _, plan in group.plans),
            lossless=first_plan.lossless,
        )

    @staticmethod
    def _explain(
        field_name: str,
        issue: QualityIssue,
        plan: _Plan,
        row_count: int,
        examples: list[Any],
    ) -> tuple[str, str]:
        """Plain-English title and rationale (NFR-6)."""

        rows = f"{row_count} row{'s' if row_count != 1 else ''}"
        sample = ", ".join(repr(value) for value in examples)
        rule = issue.rule_id

        if plan.operation != Operation.KEEP:
            before = repr(plain(issue.observed_value))
            after = "blank" if plan.after is None else repr(plan.after)

            if plan.operation in _GROUP_BY_VALUE_OPERATIONS:
                title = f"{field_name}: change {before} to {after} ({rows})"
            elif plan.operation == Operation.SET_BLANK:
                title = f"{field_name}: blank placeholder values ({rows})"
            else:
                title = (
                    f"{field_name}: "
                    f"{OPERATION_PHRASES.get(plan.operation, plan.operation.value)}"
                    f" ({rows})"
                )

            rationale = (
                f"{rows} in {field_name} do not meet the rule: "
                f"{issue.expected_condition} {plan.reason} "
                f"For example {before} becomes {after}. "
                "If approved, Agent 4 applies exactly this conversion; "
                "if rejected, the source values are kept and the item "
                "is re-assessed using your note."
            )
            return title, rationale

        if issue.row_index is None:
            if rule == "column_not_mapped":
                return (
                    f"{field_name}: no source column mapped",
                    f"No column in the source file was mapped to "
                    f"{field_name}. It will be exported as an empty "
                    "column; no values will be invented. Edit the "
                    "column mapping if the source does contain this "
                    "information, or approve to confirm it is absent.",
                )

            return (
                f"{field_name}: column is empty",
                f"The source column mapped to {field_name} has no values "
                f"in any of its {rows}. It will be exported blank. "
                "Approve to confirm, or check whether the wrong source "
                "column was mapped.",
            )

        explanations = {
            IssueType.MISSING_VALUE: (
                f"{field_name}: {rows} missing a value",
                f"{rows} have no {field_name}. The cells stay blank in "
                "the cleaned output; the system will not invent a value. "
                "Approve to acknowledge, or edit to supply the value "
                "from the client.",
            ),
            IssueType.NEGATIVE_VALUE: (
                f"{field_name}: {rows} with negative values",
                f"{rows} have a negative {field_name} (e.g. {sample}). "
                "Insured values cannot be negative; this is usually a "
                "sign error or a credit entry. The values are not "
                "changed automatically - converting to zero or flipping "
                "the sign would alter the insured exposure.",
            ),
            IssueType.FUTURE_YEAR: (
                f"{field_name}: {rows} built in the future",
                f"{rows} have a {field_name} after the current year "
                f"(e.g. {sample}). The correct year cannot be inferred, "
                "so the values are left for you to correct.",
            ),
            IssueType.INVALID_RANGE: (
                f"{field_name}: {rows} outside the valid range",
                f"{rows} break the rule: {issue.expected_condition} "
                f"(e.g. {sample}). The correct value cannot be inferred "
                "and is left for you to correct.",
            ),
            IssueType.DUPLICATE: (
                f"{field_name}: {rows} duplicated",
                f"{rows} repeat a value that should be unique "
                f"(e.g. {sample}). Duplicates can double-count "
                "exposure. Nothing is removed automatically; confirm "
                "whether these are separate locations.",
            ),
            IssueType.STATISTICAL_ANOMALY: (
                f"{field_name}: {rows} unusually large or small",
                f"{rows} are statistical outliers for {field_name} "
                f"(e.g. {sample}) compared with the rest of the file. "
                "An outlier is not necessarily wrong - large sites "
                "exist - so the values are only flagged for a check.",
            ),
            IssueType.CROSS_FIELD_CONFLICT: (
                f"{field_name}: {rows} with conflicting fields",
                f"{rows} are individually valid but inconsistent with "
                f"related fields: {issue.expected_condition} The "
                "system cannot tell which field is wrong, so nothing "
                "is changed.",
            ),
        }

        if issue.issue_type in explanations:
            title, rationale = explanations[issue.issue_type]
        else:
            title = f"{field_name}: {rows} need review (e.g. {sample})"
            rationale = (
                f"{rows} break the rule: {issue.expected_condition} "
                f"(e.g. {sample}). No safe automatic conversion exists, "
                "so the values are kept and flagged for your decision. "
                "Edit to provide the correct value."
            )

        if plan.reason:
            rationale = f"{rationale} {plan.reason}"

        return title, rationale

    # -----------------------------------------------------------------
    # Column mappings (Agent 2 -> FR-4 column_mapping)
    # -----------------------------------------------------------------

    def _mapping_recommendations(
        self,
        mappings: Iterable[Any],
    ) -> list[Recommendation]:
        recommendations: list[Recommendation] = []

        for mapping in mappings:
            source = _get(mapping, "source_header", "source_column")
            target = _get(mapping, "target_field", "target")
            score = float(_get(mapping, "score", "confidence") or 0.0)
            method = _get(mapping, "method", "mapping_method") or "unknown"
            reason = _get(mapping, "reason") or ""

            if source is None:
                continue

            score = min(max(score, 0.0), 1.0)

            evidence = Evidence(
                rule_id="schema_mapping",
                expected_condition=(
                    "Each source column should map to at most one of the "
                    "17 target fields."
                ),
                observed_values=[source],
                field_context={
                    "method": method,
                    "score": score,
                    "agent2_reason": reason,
                },
            )

            if target is None:
                recommendations.append(
                    Recommendation(
                        recommendation_id=stable_id("REC-MAP", source),
                        action_type=ActionType.FLAG_FOR_REVIEW,
                        operation=Operation.KEEP,
                        target_field=None,
                        source_column=source,
                        rule_id="column_unmapped",
                        # Near-misses (e.g. lost a one-to-one conflict)
                        # matter more than clearly unrelated columns.
                        severity=(
                            IssueSeverity.MEDIUM
                            if score >= 0.5
                            else IssueSeverity.LOW
                        ),
                        affected_row_count=0,
                        before_value=source,
                        after_value=None,
                        title=f"Column '{source}' is not mapped",
                        rationale=(
                            f"No target field matched '{source}' with "
                            f"enough confidence (best score {score:.2f}). "
                            "It will not appear in the cleaned output. "
                            "Edit this item to map it to a target field, "
                            "or approve to leave it out."
                        ),
                        uncertainty=(
                            "The column may hold information the target "
                            "schema does not cover."
                        ),
                        evidence=evidence,
                        detection_confidence=1.0,
                        fix_confidence=score,
                    )
                )
                continue

            if score < 0.5:
                severity = IssueSeverity.HIGH
                uncertainty = (
                    "Low confidence: the header gives little evidence for "
                    "this target; please confirm."
                )
            elif score < 0.75:
                severity = IssueSeverity.MEDIUM
                uncertainty = (
                    "Moderate confidence: the match relies on partial "
                    "header or value similarity."
                )
            else:
                severity = IssueSeverity.LOW
                uncertainty = f"High-confidence {method} match."

            recommendations.append(
                Recommendation(
                    recommendation_id=stable_id("REC-MAP", source),
                    action_type=ActionType.COLUMN_MAPPING,
                    operation=Operation.RENAME_COLUMN,
                    operation_params={"source_column": source},
                    target_field=target,
                    source_column=source,
                    rule_id="schema_mapping",
                    severity=severity,
                    affected_row_count=0,
                    before_value=source,
                    after_value=target,
                    title=f"Map column '{source}' to {target}",
                    rationale=(
                        f"Source column '{source}' was matched to the "
                        f"target field {target} by {method} matching with "
                        f"confidence {score:.2f}."
                        + (f" Reason: {reason}" if reason else "")
                    ),
                    uncertainty=uncertainty,
                    evidence=evidence,
                    detection_confidence=1.0,
                    fix_confidence=score,
                    lossless=True,
                )
            )

        return recommendations

    # -----------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------

    @staticmethod
    def _row_value(
        dataframe: pd.DataFrame | None,
        row_index: Optional[int],
        column: str,
    ) -> Any:
        if (
            dataframe is None
            or row_index is None
            or column not in dataframe.columns
            or row_index not in dataframe.index
        ):
            return None

        return plain(dataframe.at[row_index, column])

    @staticmethod
    def _priority(recommendation: Recommendation) -> tuple:
        """
        Review-queue order: column mappings, then severity, then
        low fix confidence, high-impact fields, cross-field conflicts,
        statistical anomalies.
        """

        return (
            0 if recommendation.action_type == ActionType.COLUMN_MAPPING else 1,
            -SEVERITY_RANK[recommendation.severity],
            0 if recommendation.target_field in HIGH_IMPACT_FIELDS else 1,
            recommendation.fix_confidence,
            0
            if recommendation.issue_type == IssueType.CROSS_FIELD_CONFLICT
            else 1,
            0
            if recommendation.issue_type == IssueType.STATISTICAL_ANOMALY
            else 1,
            recommendation.title,
        )


def _get(mapping: Any, *names: str) -> Any:
    for name in names:
        if isinstance(mapping, dict) and name in mapping:
            return mapping[name]

        if hasattr(mapping, name):
            return getattr(mapping, name)

    return None
