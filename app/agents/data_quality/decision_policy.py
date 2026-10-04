from app.agents.data_quality.issue_schema import IssueSeverity
from app.agents.data_quality.recommendation_schema import (
    ActionType,
    ReasoningSource,
    Recommendation,
    ReviewPolicy,
)


class DecisionPolicy:
    """
    Deterministic, auditable review policy.

    The policy is applied to a recommendation, not to the raw issue:
    detection confidence ("this cell is certainly blank") says nothing
    about whether a proposed fix is safe. The policy uses the fix
    confidence, the operation, the severity and who produced it.

    A recommendation is BULK_APPROVABLE only when all hold:
    - it is a standardisation or a column mapping;
    - its operation is lossless (representation only);
    - its fix confidence is at least BULK_CONFIDENCE (FR-5: 0.90);
    - its severity is LOW or MEDIUM;
    - it was produced deterministically on the first attempt.

    Everything else needs an individual human decision. Either way,
    nothing is applied until a human approves it (C-01).
    """

    BULK_CONFIDENCE = 0.90

    def evaluate(
        self,
        recommendation: Recommendation,
    ) -> tuple[ReviewPolicy, list[str]]:
        reasons: list[str] = []

        if recommendation.action_type not in {
            ActionType.STANDARDISATION,
            ActionType.COLUMN_MAPPING,
        }:
            reasons.append(
                f"{recommendation.action_type.value} needs an individual "
                "decision."
            )

        if not recommendation.lossless:
            reasons.append(
                f"{recommendation.operation.value} may change meaning, "
                "not only format."
            )

        if recommendation.fix_confidence < self.BULK_CONFIDENCE:
            reasons.append(
                f"Fix confidence {recommendation.fix_confidence:.2f} is "
                f"below {self.BULK_CONFIDENCE:.2f}."
            )

        if recommendation.severity in {
            IssueSeverity.HIGH,
            IssueSeverity.CRITICAL,
        }:
            reasons.append(
                f"{recommendation.severity.value.upper()} severity always "
                "needs human review."
            )

        if recommendation.reasoning_source != ReasoningSource.DETERMINISTIC:
            reasons.append(
                f"Produced by {recommendation.reasoning_source.value} "
                "reasoning, not a deterministic rule."
            )

        if recommendation.attempt > 1:
            reasons.append("Re-reasoned after a rejection.")

        if reasons:
            return ReviewPolicy.HUMAN_REVIEW_REQUIRED, reasons

        return ReviewPolicy.BULK_APPROVABLE, [
            "Lossless, high-confidence standardisation; eligible for "
            "Approve All."
        ]

    def apply(self, recommendation: Recommendation) -> Recommendation:
        policy, reasons = self.evaluate(recommendation)

        return recommendation.model_copy(
            update={
                "policy": policy,
                "policy_reasons": reasons,
            }
        )
