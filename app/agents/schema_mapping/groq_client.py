import os
import re
import time

from dotenv import load_dotenv
from groq import Groq

from app.agents.schema_mapping.llm_decision import (
    LLMDecisionContext,
    LLMMappingDecision,
    validate_llm_decision,
)
from app.agents.schema_mapping.llm_prompt import (
    BATCH_INSTRUCTIONS,
    SYSTEM_PROMPT,
    build_batch_payload,
    build_llm_user_prompt,
)
from app.llm_rate_limiter import (
    RATE_LIMITER,
    LLMUnavailableError,
    estimate_tokens,
    parse_retry_after,
)


load_dotenv()


DEFAULT_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")


class GroqLLMClient:
    """Client responsible for schema-mapping reasoning through Groq."""

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        api_key: str | None = None,
    ):
        self.model = model

        if api_key:
            # One explicit key: no failover.
            self._pool = None
            self.client = Groq(api_key=api_key)
            return

        from app.llm_pool import configured_keys, get_pool

        if not configured_keys():
            raise ValueError(
                "GROQ_API_KEY is not configured. "
                "Add it to the .env file."
            )

        # All configured keys, with automatic failover between them.
        self._pool = get_pool()
        self.client = None

    def decide(
        self,
        context: LLMDecisionContext,
    ) -> LLMMappingDecision:
        """
        Ask the LLM to resolve an ambiguous schema mapping.

        The model response is validated through the Pydantic
        LLMMappingDecision contract before being returned.
        """

        user_prompt = build_llm_user_prompt(context)

        response = self._create_with_retry(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": user_prompt,
                },
            ],
            temperature=0,
            response_format={
                "type": "json_object",
            },
        )

        content = response.choices[0].message.content

        if not content:
            raise ValueError(
                "Groq returned an empty response."
            )

        decision = LLMMappingDecision.model_validate_json(
            content
        )

        return validate_llm_decision(decision)

    MAX_RETRIES = 4
    MAX_WAIT_SECONDS = 20.0
    BATCH_SIZE = 8

    def decide_batch(
        self,
        contexts: list[LLMDecisionContext],
    ) -> dict[str, LLMMappingDecision]:
        """
        Resolve several ambiguous columns in one request.

        One call per 8 columns instead of one per column keeps a whole
        workbook inside the free-tier token budget. Each returned
        decision is validated exactly like a single decision; columns
        the model omits or answers invalidly are simply not returned.
        """

        if not contexts:
            return {}

        payload = build_batch_payload(contexts)

        response = self._create_with_retry(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT + "\n\n" + BATCH_INSTRUCTIONS},
                {"role": "user", "content": payload},
            ],
            temperature=0,
            response_format={"type": "json_object"},
            _completion_tokens=250 * len(contexts) + 600,
        )

        content = response.choices[0].message.content

        if not content:
            raise ValueError("Groq returned an empty response.")

        import json

        raw = json.loads(content).get("decisions", {})
        decisions: dict[str, LLMMappingDecision] = {}

        for context in contexts:
            item = raw.get(context.source_header)

            if not isinstance(item, dict):
                continue

            try:
                decision = LLMMappingDecision.model_validate(
                    {
                        key: item.get(key)
                        for key in (
                            "target_field",
                            "confidence",
                            "reason",
                            "human_review_required",
                        )
                        if key in item
                    }
                )
            except ValueError:
                continue

            decisions[context.source_header] = validate_llm_decision(decision)

        return decisions

    def _create_with_retry(self, _completion_tokens: int = 400, **request):
        """
        Run a chat completion inside the token budget: through the key
        pool (failover between keys) or, when this client was given one
        explicit key/client, on that client alone.
        """

        from app.llm_pool import complete_with

        request = with_reasoning_effort(self.model, request)
        pool = getattr(self, "_pool", None)

        if pool is not None:
            return pool.complete(request, _completion_tokens)

        return complete_with(self.client, RATE_LIMITER, request, _completion_tokens)


def _is_rate_limit(error: Exception) -> bool:
    from app.llm_pool import is_rate_limit

    return is_rate_limit(error)


def _retry_delay(error: Exception, attempt: int, cap: float) -> float:
    from app.llm_pool import retry_delay

    return retry_delay(error, attempt, cap)


def stop_if_quota_exhausted(error: Exception, max_wait: float) -> None:
    """Block the shared single-key budget when its quota is used up."""

    from app.llm_pool import quota_exhausted

    reset = quota_exhausted(error, max_wait)

    if reset is None:
        return

    minutes, seconds = divmod(int(reset), 60)
    reason = (
        "The LLM provider's daily token quota is used up (resets in about "
        f"{minutes}m {seconds}s); continuing without the LLM."
    )
    RATE_LIMITER.block(reset, reason)
    raise LLMUnavailableError(reason) from error


def with_reasoning_effort(model: str, request: dict) -> dict:
    """
    gpt-oss models spend hidden reasoning tokens; "low" effort is enough
    for picking a column and costs far fewer tokens (GROQ_REASONING_EFFORT
    overrides; empty disables).
    """

    effort = os.getenv("GROQ_REASONING_EFFORT", "low")

    if not effort or "gpt-oss" not in model or "reasoning_effort" in request:
        return request

    return {**request, "reasoning_effort": effort}


def _rejects_reasoning_effort(error: Exception) -> bool:
    from app.llm_pool import rejects_reasoning_effort

    return rejects_reasoning_effort(error)
