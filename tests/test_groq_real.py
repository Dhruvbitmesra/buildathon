from app.agents.schema_mapping.groq_client import (
    GroqLLMClient,
)
from app.agents.schema_mapping.llm_decision import (
    LLMDecisionContext,
)


def main():

    context = LLMDecisionContext(
        source_header="Bldg Repl Cost",
        normalized_header="bldg repl cost",
        candidates=[
            {
                "target_field": "Building Value",
                "score": 0.739,
                "embedding_similarity": 0.82,
                "value_evidence_score": 0.95,
                "evidence_reasons": [
                    "Values appear to be monetary amounts."
                ],
            },
            {
                "target_field": "Contents",
                "score": 0.51,
                "embedding_similarity": 0.61,
                "value_evidence_score": 0.80,
                "evidence_reasons": [
                    "Values appear to be monetary amounts."
                ],
            },
        ],
        column_profile={
            "top_target_field": "Building Value",
            "top_embedding_similarity": 0.82,
            "top_value_evidence_score": 0.95,
        },
        sample_values=[
            "1250000",
            "850000",
            "2100000",
        ],
    )

    client = GroqLLMClient()

    decision = client.decide(context)

    print("\n===== GROQ LLM DECISION =====")
    print(f"Target field: {decision.target_field}")
    print(f"Confidence: {decision.confidence}")
    print(f"Reason: {decision.reason}")
    print(
        f"Human review required: "
        f"{decision.human_review_required}"
    )
    print("==============================\n")


if __name__ == "__main__":
    main()