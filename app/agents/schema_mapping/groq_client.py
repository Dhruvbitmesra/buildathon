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


DEFAULT_MODEL = "openai/gpt-oss-120b"


class GroqLLMClient:
    """Client responsible for schema-mapping reasoning through Groq."""

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        api_key: str | None = None,
    ):
        self.model = model

        key = api_key or os.getenv("GROQ_API_KEY")

        if not key:
            raise ValueError(
                "GROQ_API_KEY is not configured. "
                "Add it to the .env file."
            )

        self.client = Groq(api_key=key)

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
        Call the chat API inside the shared token budget, and wait and
        retry if the API still answers 429 (rate limited).
        """

        prompt_text = "".join(
            message.get("content", "") for message in request.get("messages", [])
        )
        request = with_reasoning_effort(self.model, request)
        attempt = 0

        while True:
            reservation = RATE_LIMITER.acquire(
                estimate_tokens(prompt_text, completion=_completion_tokens)
            )

            try:
                response = self.client.chat.completions.create(**request)
            except Exception as error:
                if _rejects_reasoning_effort(error) and "reasoning_effort" in request:
                    request = {k: v for k, v in request.items() if k != "reasoning_effort"}
                    continue

                if not _is_rate_limit(error):
                    raise

                stop_if_quota_exhausted(error, self.MAX_WAIT_SECONDS)
                attempt += 1

                if attempt > self.MAX_RETRIES:
                    raise

                delay = _retry_delay(error, attempt, self.MAX_WAIT_SECONDS)
                RATE_LIMITER.penalise(delay)
                time.sleep(delay)
                continue

            usage = getattr(response, "usage", None)
            RATE_LIMITER.record(reservation, getattr(usage, "total_tokens", None))
            return response


def _is_rate_limit(error: Exception) -> bool:
    status = getattr(error, "status_code", None)
    return status == 429 or "rate limit" in str(error).lower()


def _retry_delay(error: Exception, attempt: int, cap: float) -> float:
    """Use the server's "try again in ..." hint, else exponential backoff."""

    hint = parse_retry_after(str(error))

    if hint is not None:
        return min(hint + 0.5, cap)

    return min(2.0 ** attempt, cap)


def stop_if_quota_exhausted(error: Exception, max_wait: float) -> None:
    """
    A daily quota, or any limit that resets later than `max_wait`,
    cannot be waited out inside one run: stop calling the LLM until it
    resets and let the agents continue deterministically.
    """

    message = str(error)
    hint = parse_retry_after(message)
    daily = "per day" in message.lower() or "(tpd)" in message.lower() or "(rpd)" in message.lower()

    if not daily and (hint is None or hint <= max_wait):
        return

    seconds = hint if hint is not None else 3600.0
    kind = "daily token quota" if daily else "rate limit"
    minutes, secs = divmod(int(seconds), 60)
    reason = (
        f"The LLM provider's {kind} is used up (resets in about "
        f"{minutes}m {secs}s); continuing without the LLM."
    )
    RATE_LIMITER.block(seconds, reason)
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
    text = str(error).lower()
    return "reasoning_effort" in text and ("400" in text or "unsupported" in text or "invalid" in text)
