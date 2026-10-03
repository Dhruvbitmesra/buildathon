from app.agents.schema_mapping.decision_engine import (
    resolve_mapping,
)
from app.agents.schema_mapping.semantic_pipeline import (
    run_semantic_pipeline,
)


def run_case(
    source_header: str,
    sample_values: list[str],
):
    pipeline = run_semantic_pipeline(
        source_header=source_header,
    )

    result = resolve_mapping(
        pipeline,
        sample_values=sample_values,
    )

    print("\n========================================")
    print(f"Source header: {source_header}")
    print(f"Semantic status: {pipeline.status}")

    if pipeline.evaluation:
        print(
            f"Semantic category: "
            f"{pipeline.evaluation.category}"
        )
        print(
            f"Semantic top candidate: "
            f"{pipeline.evaluation.top_candidate.target_field}"
        )
        print(
            f"Semantic score: "
            f"{pipeline.evaluation.top_score}"
        )
        print(
            f"Semantic margin: "
            f"{pipeline.evaluation.score_margin}"
        )

    print(f"Final target: {result.target_field}")
    print(f"Final method: {result.method}")
    print(f"Final confidence: {result.confidence}")
    print(
        f"Human review: "
        f"{result.human_review_required}"
    )
    print(f"Reason: {result.reason}")

    return pipeline, result

def main():

    # --------------------------------------------------
    # Case 1 — Clear semantic mapping
    # --------------------------------------------------

    run_case(
        source_header="Bldg Repl Cost",
        sample_values=[
            "$1,250,000",
            "$850,000",
            "$2,100,000",
        ],
    )

    # --------------------------------------------------
    # Case 2 — Intentionally ambiguous mapping
    # --------------------------------------------------

    run_case(
        source_header="Building",
        sample_values=[
            "Brick",
            "Concrete",
            "Steel",
            "Wood",
        ],
    )


if __name__ == "__main__":
    main()