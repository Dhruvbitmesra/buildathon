import os

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

        response = self.client.chat.completions.create(
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