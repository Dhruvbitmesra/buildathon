from pathlib import Path

import pandas as pd

from app.agents.schema_mapping.agent import (
    SchemaMappingAgent,
    SchemaMappingInput,
)
from app.agents.schema_mapping.groq_client import GroqLLMClient


# ============================================================================
# CONFIG
# ============================================================================

INPUT_FILE = Path("data/input/SOV_B4ID.xlsx")
SHEET_NAME = "SOV"
HEADER_ROW = 11

# Keep samples small to avoid unnecessary LLM/token usage.
MAX_SAMPLES = 5


# ============================================================================
# HEADER CLEANING
# ============================================================================

def clean_header(value, index: int) -> str:
    """
    Convert a pandas header into the same stable string representation
    used by the real Agent 2 runner.
    """

    if pd.isna(value):
        return f"Unnamed: {index}"

    value = str(value).strip()

    if not value:
        return f"Unnamed: {index}"

    return value


# ============================================================================
# MAIN
# ============================================================================

def main() -> None:

    print("=" * 80)
    print("STEP 2.23 — AGENT 2 EVIDENCE EVALUATION")
    print("=" * 80)

    # ----------------------------------------------------------------------
    # Load workbook
    # ----------------------------------------------------------------------

    print()
    print(f"Input file : {INPUT_FILE}")
    print(f"Sheet      : {SHEET_NAME}")
    print(f"Header row : {HEADER_ROW}")

    dataframe = pd.read_excel(
        INPUT_FILE,
        sheet_name=SHEET_NAME,
        header=HEADER_ROW,
    )

    print(
        f"Dataframe shape: {dataframe.shape}"
    )

    # ----------------------------------------------------------------------
    # Preserve actual pandas columns
    # ----------------------------------------------------------------------

    actual_columns = list(dataframe.columns)

    clean_columns = [
        clean_header(
            column,
            index,
        )
        for index, column in enumerate(actual_columns)
    ]

    sample_values: dict[str, list[str]] = {}

    for actual_column, clean_column in zip(
        actual_columns,
        clean_columns,
    ):

        values = (
            dataframe[actual_column]
            .dropna()
            .astype(str)
            .head(MAX_SAMPLES)
            .tolist()
        )

        sample_values[clean_column] = values

    # ----------------------------------------------------------------------
    # Initialize Agent 2
    # ----------------------------------------------------------------------

    print()
    print("=" * 80)
    print("INITIALIZING AGENT 2")
    print("=" * 80)

    llm_client = None

    try:
        llm_client = GroqLLMClient()
        print("Groq LLM client initialized.")
    except Exception as exc:
        print(
            f"Groq LLM client unavailable: {exc}"
        )
        print(
            "Continuing without LLM fallback."
        )

    agent = SchemaMappingAgent(
        llm_client=llm_client
    )

    # ----------------------------------------------------------------------
    # Inspect every column BEFORE global assignment
    # ----------------------------------------------------------------------

    print()
    print("=" * 80)
    print("RAW CANDIDATE EVIDENCE")
    print("=" * 80)

    all_evidence = []

    for source_header in clean_columns:

        samples = sample_values.get(
            source_header,
            [],
        )

        print()
        print("-" * 80)
        print(f"SOURCE: {source_header}")
        print("-" * 80)

        try:

            evidence = agent._build_column_evidence(
                source_header=source_header,
                samples=samples,
            )

            all_evidence.append(evidence)

            candidates = sorted(
                evidence.candidates,
                key=lambda candidate: float(
                    candidate.get(
                        "score",
                        0.0,
                    )
                    or 0.0
                ),
                reverse=True,
            )

            if not candidates:

                print("No candidates.")

                continue

            for rank, candidate in enumerate(
                candidates[:10],
                start=1,
            ):

                print(
                    f"{rank:02d}. "
                    f"Target={candidate.get('target_field')} | "
                    f"Score={float(candidate.get('score', 0.0) or 0.0):.4f} | "
                    f"Det={float(candidate.get('deterministic_score', 0.0) or 0.0):.4f} | "
                    f"Fuzzy={float(candidate.get('fuzzy_score', 0.0) or 0.0):.4f} | "
                    f"Semantic={float(candidate.get('semantic_score', 0.0) or 0.0):.4f} | "
                    f"Embedding={float(candidate.get('embedding_similarity', 0.0) or 0.0):.4f} | "
                    f"Value={float(candidate.get('value_evidence_score', 0.0) or 0.0):.4f} | "
                    f"LLM={float(candidate.get('llm_score', 0.0) or 0.0):.4f} | "
                    f"Method={candidate.get('method')}"
                )

                reasons = candidate.get(
                    "evidence_reasons",
                    [],
                )

                for reason in reasons[:5]:
                    print(
                        f"      Reason: {reason}"
                    )

        except Exception as exc:

            print(
                f"ERROR: {exc}"
            )

    # ----------------------------------------------------------------------
    # Specifically inspect Building
    # ----------------------------------------------------------------------

    print()
    print("=" * 80)
    print("BUILDING → BUILDING VALUE DIAGNOSTIC")
    print("=" * 80)

    building_evidence = None

    for evidence in all_evidence:

        if evidence.source_header.lower() == "building":
            building_evidence = evidence
            break

    if building_evidence is None:

        print(
            "Could not find the 'Building' source column."
        )

    else:

        candidates = sorted(
            building_evidence.candidates,
            key=lambda candidate: float(
                candidate.get(
                    "score",
                    0.0,
                )
                or 0.0
            ),
            reverse=True,
        )

        for candidate in candidates:

            if candidate.get(
                "target_field"
            ) == "Building Value":

                print()
                print(
                    "Building Value candidate:"
                )

                print(
                    f"Score                : "
                    f"{float(candidate.get('score', 0.0) or 0.0):.4f}"
                )

                print(
                    f"Deterministic score   : "
                    f"{float(candidate.get('deterministic_score', 0.0) or 0.0):.4f}"
                )

                print(
                    f"Fuzzy score           : "
                    f"{float(candidate.get('fuzzy_score', 0.0) or 0.0):.4f}"
                )

                print(
                    f"Semantic score        : "
                    f"{float(candidate.get('semantic_score', 0.0) or 0.0):.4f}"
                )

                print(
                    f"Embedding similarity  : "
                    f"{float(candidate.get('embedding_similarity', 0.0) or 0.0):.4f}"
                )

                print(
                    f"Value evidence        : "
                    f"{float(candidate.get('value_evidence_score', 0.0) or 0.0):.4f}"
                )

                print(
                    f"LLM score             : "
                    f"{float(candidate.get('llm_score', 0.0) or 0.0):.4f}"
                )

                print(
                    f"Method                : "
                    f"{candidate.get('method')}"
                )

                print()
                print("Reasons:")

                for reason in candidate.get(
                    "evidence_reasons",
                    [],
                ):

                    print(
                        f"  - {reason}"
                    )

                break

        else:

            print(
                "Building Value was NOT present "
                "in the candidate list."
            )

    # ----------------------------------------------------------------------
    # Run global assignment separately
    # ----------------------------------------------------------------------

    print()
    print("=" * 80)
    print("GLOBAL ASSIGNMENT RESULT")
    print("=" * 80)

    from app.agents.schema_mapping.batch_mapper import (
        assign_one_to_one,
    )

    assignment = assign_one_to_one(
        all_evidence
    )

    for mapping in assignment.mappings:

        print(
            f"{mapping.source_header:30s} → "
            f"{str(mapping.target_field):30s} | "
            f"{mapping.score:.4f} | "
            f"{mapping.method}"
        )

    # ----------------------------------------------------------------------
    # Summary
    # ----------------------------------------------------------------------

    print()
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)

    print(
        f"Source columns : {len(clean_columns)}"
    )

    print(
        f"Assigned       : "
        f"{len(assignment.assigned_targets)}"
    )

    print(
        f"Unresolved     : "
        f"{len(assignment.unresolved_columns)}"
    )

    print()
    print(
        "Step 2.23 diagnostic run completed."
    )


if __name__ == "__main__":
    main()