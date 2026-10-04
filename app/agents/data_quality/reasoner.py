"""
Reasoning back-ends for Agent 3.

A reasoner is consulted only after deterministic rules have run:
- reconsider(): propose a new recommendation after a human rejection;
- explain(): optionally add a business-impact explanation.

Reasoners only *propose*. ReviewSession validates every proposal
(closed operation list, allowed values, re-validation of the result)
before it reaches a reviewer, and a reasoner can never change data.

RuleBasedReasoner is deterministic and needs no network. GroqReasoner
calls an LLM and is used when GROQ_API_KEY is configured; any failure
falls back to RuleBasedReasoner.
"""

import json
import os
import re
import time
from typing import Any, Optional, Protocol

from pydantic import BaseModel, Field

from app.agents.data_quality.normalizers import Operation
from app.agents.data_quality.recommendation_schema import (
    ActionType,
    Recommendation,
)


# Fields whose values may identify a person or property; never sent to
# an external model.
MASKED_FIELDS = {"Reference", "Address", "City"}


class ReasoningContext(BaseModel):
    recommendation: Recommendation

    rejection_reason: str = Field(min_length=1)

    # Number of the attempt being produced (2 = first re-reasoning).
    attempt: int = Field(ge=2)

    allowed_operations: list[Operation]

    # Canonical values for the field (sprinkler codes, state codes,
    # target field names for column mappings).
    allowed_values: list[str] = Field(default_factory=list)

    # (operation, value) pairs already rejected; must not be repeated.
    rejected_proposals: list[tuple[str, Any]] = Field(default_factory=list)


class ReasoningProposal(BaseModel):
    operation: Operation

    # Only for SET_VALUE (a cell value) or RENAME_COLUMN (a target field).
    value: Any = None

    rationale: str = Field(min_length=1)

    uncertainty: str = Field(min_length=1)

    confidence: float = Field(ge=0.0, le=1.0)


class Reasoner(Protocol):
    name: str

    def reconsider(
        self,
        context: ReasoningContext,
    ) -> Optional[ReasoningProposal]: ...

    def explain(self, recommendation: Recommendation) -> Optional[str]: ...


def find_value_in_note(note: str, allowed_values: list[str]) -> Optional[str]:
    """
    Return the single allowed value the reviewer's note names, if any.

    Longer values are matched first so "Y(13R)" wins over "Y".
    Ambiguous notes (two different values) return None.
    """

    found: list[str] = []
    remaining = note

    for value in sorted(allowed_values, key=len, reverse=True):
        pattern = rf"(?<![A-Za-z0-9]){re.escape(value)}(?![A-Za-z0-9])"
        flags = 0 if len(value) <= 2 else re.IGNORECASE

        if re.search(pattern, remaining, flags):
            found.append(value)
            remaining = re.sub(pattern, " ", remaining, flags=flags)

    return found[0] if len(found) == 1 else None


class RuleBasedReasoner:
    """
    Deterministic re-reasoning.

    1. If the reviewer's note names exactly one allowed value
       ("these are 13R systems"), propose that value.
    2. Otherwise, if the rejected recommendation changed data, propose
       keeping the source values unchanged and flagging them.
    3. Otherwise there is no safe alternative: return None (escalate).
    """

    name = "rule_based"

    def reconsider(
        self,
        context: ReasoningContext,
    ) -> Optional[ReasoningProposal]:
        previous = context.recommendation
        rejected = {(op, str(value)) for op, value in context.rejected_proposals}
        is_mapping = previous.action_type == ActionType.COLUMN_MAPPING or (
            previous.rule_id == "column_unmapped"
        )

        named = find_value_in_note(
            context.rejection_reason,
            context.allowed_values,
        )

        if named is not None:
            operation = (
                Operation.RENAME_COLUMN if is_mapping else Operation.SET_VALUE
            )

            if (operation.value, named) not in rejected:
                return ReasoningProposal(
                    operation=operation,
                    value=named,
                    rationale=(
                        f"The reviewer's note names '{named}', which is a "
                        "valid value for this field, so it replaces the "
                        "rejected proposal."
                    ),
                    uncertainty=(
                        "Taken from the reviewer's note; it applies to "
                        "every affected row."
                    ),
                    confidence=0.8,
                )

        if (
            previous.operation != Operation.KEEP
            and (Operation.KEEP.value, "None") not in rejected
        ):
            return ReasoningProposal(
                operation=Operation.KEEP,
                value=None,
                rationale=(
                    "The proposed change was rejected, so the safest "
                    "alternative is to keep the source values unchanged "
                    + (
                        "and leave the column unmapped."
                        if is_mapping
                        else "and flag them for manual correction."
                    )
                ),
                uncertainty=(
                    "The source values may still be wrong; they are kept "
                    "as received."
                ),
                confidence=0.9,
            )

        return None

    def explain(self, recommendation: Recommendation) -> Optional[str]:
        return None


_SYSTEM_PROMPT = """You are the reasoning component of an insurance
Statement-of-Values data-quality agent. A human reviewer rejected a
recommendation. Propose ONE alternative.

Rules:
- Choose "operation" only from allowed_operations.
- Never invent data. For set_value or rename_column, "value" must be one
  of allowed_values or appear verbatim in the reviewer's note.
- Never repeat a proposal listed in rejected_proposals.
- If no safe alternative exists, choose "keep".
- Respect the reviewer's note; it overrides your own preference.

Reply with JSON only:
{"operation": "...", "value": null or "...", "rationale": "...",
 "uncertainty": "...", "confidence": 0.0-1.0}"""


_EXPLAIN_PROMPT = """You explain data-quality findings in insurance
Statements of Values to non-technical underwriting staff. In at most two
sentences, explain the business impact of the finding if it is not
fixed. Do not propose new values. Reply with JSON only:
{"explanation": "..."}"""


_EXPLAIN_BATCH_PROMPT = """You explain data-quality findings in insurance
Statements of Values to non-technical underwriting staff. For each item,
write at most two sentences on the business impact (pricing, exposure,
modelling) if it is not fixed. Do not propose new values or operations.
Reply with JSON only: {"explanations": {"<id>": "...", ...}}"""


class GroqReasoner:
    """LLM reasoner using Groq (same provider/model as Agent 2)."""

    name = "groq"

    DEFAULT_MODEL = "openai/gpt-oss-120b"

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
        client: Any = None,
    ) -> None:
        self.model = model or os.getenv("AGENT3_LLM_MODEL", self.DEFAULT_MODEL)

        self._pool = None

        if client is not None:
            self.client = client
            return

        if api_key:
            from groq import Groq

            self.client = Groq(api_key=api_key)
            return

        from app.llm_pool import configured_keys, get_pool

        if not configured_keys():
            raise ValueError("GROQ_API_KEY is not configured.")

        self._pool = get_pool()
        self.client = None

    def reconsider(
        self,
        context: ReasoningContext,
    ) -> Optional[ReasoningProposal]:
        payload = {
            "recommendation": masked_summary(context.recommendation),
            "rejection_reason": context.rejection_reason,
            "attempt": context.attempt,
            "allowed_operations": [op.value for op in context.allowed_operations],
            "allowed_values": context.allowed_values,
            "rejected_proposals": context.rejected_proposals,
        }

        content = self._complete(_SYSTEM_PROMPT, payload)

        if content is None:
            return None

        try:
            return ReasoningProposal.model_validate_json(content)
        except ValueError:
            return None

    def explain(self, recommendation: Recommendation) -> Optional[str]:
        content = self._complete(
            _EXPLAIN_PROMPT,
            masked_summary(recommendation),
        )

        if content is None:
            return None

        try:
            explanation = json.loads(content).get("explanation")
        except (ValueError, AttributeError):
            return None

        return explanation.strip() if isinstance(explanation, str) else None

    def explain_batch(
        self,
        recommendations: list[Recommendation],
    ) -> dict[str, str]:
        """
        Business-impact explanations for several recommendations in one
        call (masked input). Returns {recommendation_id: explanation}.
        """

        if not recommendations:
            return {}

        payload = {
            "items": [
                {"id": rec.recommendation_id, **masked_summary(rec)}
                for rec in recommendations
            ]
        }
        content = self._complete(_EXPLAIN_BATCH_PROMPT, payload)

        if content is None:
            return {}

        try:
            explanations = json.loads(content).get("explanations", {})
        except (ValueError, AttributeError):
            return {}

        known = {rec.recommendation_id for rec in recommendations}

        return {
            str(rec_id): text.strip()
            for rec_id, text in (explanations or {}).items()
            if str(rec_id) in known and isinstance(text, str) and text.strip()
        }

    def _complete(self, system_prompt: str, payload: dict) -> Optional[str]:
        """
        One JSON completion through the key pool (or the explicit
        client). Any failure returns None: callers fall back to
        deterministic behaviour.
        """

        from app.agents.schema_mapping.groq_client import with_reasoning_effort
        from app.llm_pool import complete_with
        from app.llm_rate_limiter import RATE_LIMITER

        request = with_reasoning_effort(
            self.model,
            {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": json.dumps(payload, default=str)},
                ],
                "temperature": 0,
                "response_format": {"type": "json_object"},
            },
        )

        try:
            pool = getattr(self, "_pool", None)
            response = (
                pool.complete(request, 2000)
                if pool is not None
                else complete_with(self.client, RATE_LIMITER, request, 2000)
            )
        except Exception:
            return None

        return response.choices[0].message.content or None


def masked_summary(recommendation: Recommendation) -> dict[str, Any]:
    """
    The minimum context an LLM needs, with identifying values masked.
    No raw rows are included.
    """

    field = recommendation.target_field
    masked = field in MASKED_FIELDS

    def mask(value: Any) -> Any:
        return f"<masked {field}>" if masked and value is not None else value

    return {
        "field": field,
        "action_type": recommendation.action_type.value,
        "operation": recommendation.operation.value,
        "rule_id": recommendation.rule_id,
        "severity": recommendation.severity.value,
        "expected_condition": recommendation.evidence.expected_condition,
        "affected_row_count": recommendation.affected_row_count,
        "observed_values": [
            mask(value) for value in recommendation.evidence.observed_values[:5]
        ],
        "proposed_value": mask(recommendation.after_value),
        # Trimmed: the title and rule carry the meaning; long rationales
        # only cost tokens.
        "title": recommendation.title[:160],
    }


def default_reasoner() -> Reasoner:
    """GroqReasoner when an API key is configured, else rule-based."""

    try:
        return GroqReasoner()
    except Exception:
        return RuleBasedReasoner()
