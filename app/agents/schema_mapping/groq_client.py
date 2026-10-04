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
    SYSTEM_PROMPT,
    build_llm_user_prompt,
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

    MAX_RETRIES = 3
    MAX_WAIT_SECONDS = 15.0

    def _create_with_retry(self, **request):
        """
        Call the chat API, waiting and retrying on rate-limit (429)
        responses. Groq's free tier allows ~8k tokens/minute, which a
        single SOV file can exceed.
        """

        attempt = 0

        while True:
            try:
                return self.client.chat.completions.create(**request)
            except Exception as error:
                attempt += 1

                if attempt > self.MAX_RETRIES or not _is_rate_limit(error):
                    raise

                time.sleep(_retry_delay(error, attempt, self.MAX_WAIT_SECONDS))


def _is_rate_limit(error: Exception) -> bool:
    status = getattr(error, "status_code", None)
    return status == 429 or "rate limit" in str(error).lower()


def _retry_delay(error: Exception, attempt: int, cap: float) -> float:
    """Use the server's "try again in Xs" hint, else exponential backoff."""

    match = re.search(r"try again in ([\d.]+)\s*(ms|s)", str(error))

    if match:
        seconds = float(match.group(1))
        if match.group(2) == "ms":
            seconds /= 1000
        return min(seconds + 0.5, cap)

    return min(2.0 ** attempt, cap)
