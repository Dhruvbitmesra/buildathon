from dataclasses import dataclass, field
from typing import Optional

import numpy as np
from scipy.optimize import linear_sum_assignment
from app.agents.schema_mapping.target_schema import TARGET_FIELDS

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MINIMUM_ASSIGNMENT_SCORE = 0.50


# ---------------------------------------------------------------------------
# Data contracts
# ---------------------------------------------------------------------------

@dataclass
class SourceColumnEvidence:
    source_header: str
    candidates: list[dict] = field(default_factory=list)


@dataclass
class BatchMapping:
    source_header: str
    target_field: Optional[str]
    score: float
    method: str
    human_review_required: bool = False
    reason: str = ""


@dataclass
class BatchMappingResult:
    mappings: list[BatchMapping] = field(default_factory=list)
    unresolved_columns: list[str] = field(default_factory=list)
    assigned_targets: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Candidate helpers
# ---------------------------------------------------------------------------

def _candidate_score(candidate: dict) -> float:
    """
    Return the final score supplied to the global assignment layer.

    Agent 2 performs evidence fusion before reaching this module.
    This function exists as a defensive boundary so malformed or
    out-of-range scores cannot enter the assignment matrix.
    """

    try:
        score = float(candidate.get("score", 0.0))
    except (TypeError, ValueError):
        return 0.0

    return max(0.0, min(score, 1.0))


def _candidate_method(candidate: dict) -> str:
    return str(candidate.get("method", "unknown"))


def _candidate_reason(candidate: dict) -> str:
    reasons = candidate.get("evidence_reasons", [])

    if isinstance(reasons, list) and reasons:
        return "; ".join(str(reason) for reason in reasons)

    return ""


# ---------------------------------------------------------------------------
# Global assignment
# ---------------------------------------------------------------------------

def assign_one_to_one(
    column_evidence: list[SourceColumnEvidence],
    minimum_score: float = MINIMUM_ASSIGNMENT_SCORE,
) -> BatchMappingResult:
    """
    Perform global one-to-one target assignment without forcing mappings.

    Important behavior:

    - A source column may remain unresolved.
    - A target field may remain unused.
    - Candidates below minimum_score are not eligible.
    - Hungarian assignment is used only among eligible candidates.
    - Strong evidence is therefore not displaced by weak evidence merely
      because a target is unused.
    """

    if not column_evidence:
        return BatchMappingResult()

    # ------------------------------------------------------------------
    # Collect all target fields appearing in candidate evidence.
    # ------------------------------------------------------------------

    target_fields: list[str] = []

    for evidence in column_evidence:
        for candidate in evidence.candidates:
            target = candidate.get("target_field")

            if not target:
                continue

            if target not in target_fields:
                target_fields.append(target)

    if not target_fields:
        return BatchMappingResult(
            mappings=[
                BatchMapping(
                    source_header=evidence.source_header,
                    target_field=None,
                    score=0.0,
                    method="unresolved",
                    human_review_required=True,
                    reason="No valid target candidates were available.",
                )
                for evidence in column_evidence
            ],
            unresolved_columns=[
                evidence.source_header
                for evidence in column_evidence
            ],
            assigned_targets=[],
        )

    # ------------------------------------------------------------------
    # Build score matrix.
    #
    # Important:
    # Ineligible candidates receive a large cost rather than zero cost.
    # This prevents Hungarian from treating missing candidates as valid
    # assignments.
    # ------------------------------------------------------------------

    source_count = len(column_evidence)
    target_count = len(target_fields)

    scores = np.zeros(
        (source_count, target_count),
        dtype=float,
    )

    eligible = np.zeros(
        (source_count, target_count),
        dtype=bool,
    )

    candidate_lookup: dict[
        tuple[int, int],
        dict,
    ] = {}

    for source_index, evidence in enumerate(column_evidence):

        for candidate in evidence.candidates:

            target = candidate.get("target_field")

            if target not in target_fields:
                continue

            target_index = target_fields.index(target)

            score = _candidate_score(candidate)

            if score < minimum_score:
                continue

            # If duplicate candidates for the same source/target exist,
            # retain the strongest one.
            existing = scores[
                source_index,
                target_index,
            ]

            if not eligible[
                source_index,
                target_index,
            ] or score > existing:

                scores[
                    source_index,
                    target_index,
                ] = score

                eligible[
                    source_index,
                    target_index,
                ] = True

                candidate_lookup[
                    source_index,
                    target_index,
                ] = candidate

    # ------------------------------------------------------------------
    # If no eligible candidate exists anywhere, everything is unresolved.
    # ------------------------------------------------------------------

    if not eligible.any():

        mappings = []

        for evidence in column_evidence:
            mappings.append(
                BatchMapping(
                    source_header=evidence.source_header,
                    target_field=None,
                    score=0.0,
                    method="unresolved",
                    human_review_required=True,
                    reason = (
                        f"Best candidate score is below the "
                        f"minimum assignment score of {minimum_score:.2f}."
                    )
                )
            )

        return BatchMappingResult(
            mappings=mappings,
            unresolved_columns=[
                evidence.source_header
                for evidence in column_evidence
            ],
            assigned_targets=[],
        )

    # ------------------------------------------------------------------
    # Hungarian optimization.
    #
    # We minimize cost = 1 - score.
    #
    # Ineligible pairs receive a very large cost and are therefore never
    # selected unless the optimizer has no alternative. We explicitly
    # validate the resulting pair afterward, so even that case becomes
    # unresolved rather than a forced mapping.
    # ------------------------------------------------------------------

    cost_matrix = np.ones_like(scores)

    cost_matrix[eligible] = (
        1.0 - scores[eligible]
    )

    # Make ineligible assignments prohibitively expensive.
    cost_matrix[~eligible] = 10.0

    row_indices, col_indices = linear_sum_assignment(
        cost_matrix
    )

    selected_pairs: dict[int, int] = {}

    for row_index, col_index in zip(
        row_indices,
        col_indices,
    ):

        if not eligible[
            row_index,
            col_index,
        ]:
            continue

        selected_pairs[row_index] = col_index

    # ------------------------------------------------------------------
    # Build final result.
    # ------------------------------------------------------------------

    mappings: list[BatchMapping] = []
    unresolved_columns: list[str] = []
    assigned_targets: list[str] = []

    for source_index, evidence in enumerate(column_evidence):

        target_index = selected_pairs.get(
            source_index
        )

        # --------------------------------------------------------------
        # No eligible global assignment.
        # --------------------------------------------------------------

        if target_index is None:

            best_score = 0.0

            for candidate in evidence.candidates:
                best_score = max(
                    best_score,
                    _candidate_score(candidate),
                )

            mappings.append(
                BatchMapping(
                    source_header=evidence.source_header,
                    target_field=None,
                    score=best_score,
                    method="unresolved",
                    human_review_required=True,
                    reason=(
                        "No one-to-one target assignment "
                        "was available above the minimum "
                        f"score of {minimum_score:.2f}."
                    ),
                )
            )

            unresolved_columns.append(
                evidence.source_header
            )

            continue

        # --------------------------------------------------------------
        # Validate selected pair.
        # --------------------------------------------------------------

        if not eligible[
            source_index,
            target_index,
        ]:

            mappings.append(
                BatchMapping(
                    source_header=evidence.source_header,
                    target_field=None,
                    score=0.0,
                    method="unresolved",
                    human_review_required=True,
                    reason=(
                        "Global optimization did not produce "
                        "an eligible target assignment."
                    ),
                )
            )

            unresolved_columns.append(
                evidence.source_header
            )

            continue

        target_field = target_fields[
            target_index
        ]

        score = scores[
            source_index,
            target_index,
        ]

        candidate = candidate_lookup[
            source_index,
            target_index,
        ]

        method = _candidate_method(
            candidate
        )

        reason = _candidate_reason(
            candidate
        )

        if not reason:
            reason = (
                "Assigned using evidence-aware "
                "global one-to-one optimization."
            )

        mappings.append(
            BatchMapping(
                source_header=evidence.source_header,
                target_field=target_field,
                score=float(score),
                method="global_assignment",
                human_review_required=False,
                reason=reason,
            )
        )

        assigned_targets.append(
            target_field
        )

    return BatchMappingResult(
        mappings=mappings,
        unresolved_columns=unresolved_columns,
        assigned_targets=assigned_targets,
    )


def build_score_matrix(
    column_evidence: list[SourceColumnEvidence],
    target_fields: list[str] | None = None,
) -> np.ndarray:
    """
    Build a source-column × target-field score matrix.

    The function preserves the original public API used by the tests:
    - target_fields is optional
    - return value is a NumPy array
    - unknown target fields are ignored

    If target_fields is not provided, the canonical target fields are
    obtained from TARGET_FIELDS.
    """

    if target_fields is None:
        target_fields = [
            field.name
            for field in TARGET_FIELDS
        ]

    matrix: list[list[float]] = []

    for column in column_evidence:

        candidate_scores: dict[str, float] = {}

        for candidate in column.candidates:

            target = candidate.get(
                "target_field"
            )

            if target not in target_fields:
                continue

            score = float(
                candidate.get(
                    "score",
                    0.0,
                )
                or 0.0
            )

            candidate_scores[target] = max(
                candidate_scores.get(
                    target,
                    0.0,
                ),
                score,
            )

        row = [
            candidate_scores.get(
                target,
                0.0,
            )
            for target in target_fields
        ]

        matrix.append(row)

    return np.asarray(
        matrix,
        dtype=float,
    )
