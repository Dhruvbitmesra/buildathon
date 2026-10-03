from pathlib import Path

import pandas as pd

from app.agents.schema_mapping.agent import (
    SchemaMappingAgent,
    SchemaMappingInput,
)


INPUT_FILE = Path("data/input/SOV_B4ID.xlsx")
SHEET_NAME = "SOV"


def find_header_row(dataframe: pd.DataFrame) -> int:
    """
    Smoke-test heuristic for locating the header row.

    This is only used by the real Agent 2 runner.
    Agent 1 remains unchanged.
    """

    keywords = {
        "loc",
        "location",
        "address",
        "street",
        "city",
        "state",
        "zip",
        "building",
        "occupancy",
        "construction",
        "year built",
        "stories",
        "sprinkler",
    }

    best_row = 0
    best_score = -1

    max_rows_to_check = min(30, len(dataframe))

    for row_index in range(max_rows_to_check):

        row = dataframe.iloc[row_index]

        values = [
            str(value).strip().lower()
            for value in row.tolist()
            if pd.notna(value) and str(value).strip()
        ]

        if not values:
            continue

        score = 0

        for value in values:
            for keyword in keywords:

                if keyword in value:
                    score += 1
                    break

        text_count = sum(
            1
            for value in row.tolist()
            if pd.notna(value)
            and isinstance(value, str)
            and value.strip()
        )

        score += min(
            text_count * 0.1,
            2.0,
        )

        if score > best_score:
            best_score = score
            best_row = row_index

    return best_row


def clean_header(value) -> str:
    """
    Convert a pandas column label into clean header text.
    """

    return str(value).strip()


def main() -> None:

    print("=" * 80)
    print("REAL AGENT 2 RUN")
    print("=" * 80)

    # ==================================================================
    # 1. Validate input file
    # ==================================================================

    if not INPUT_FILE.exists():

        raise FileNotFoundError(
            f"Input file not found: "
            f"{INPUT_FILE.resolve()}"
        )

    print(f"\nInput file : {INPUT_FILE}")
    print(f"Sheet      : {SHEET_NAME}")

    # ==================================================================
    # 2. Read workbook without assuming header
    # ==================================================================

    dataframe = pd.read_excel(
        INPUT_FILE,
        sheet_name=SHEET_NAME,
        header=None,
    )

    print(
        f"\nRaw dataframe shape: "
        f"{dataframe.shape}"
    )

    # ==================================================================
    # 3. Detect header row
    # ==================================================================

    header_row = find_header_row(
        dataframe
    )

    print(
        f"Detected header row: "
        f"{header_row}"
    )

    # ==================================================================
    # 4. Read workbook again using detected header
    # ==================================================================

    dataframe = pd.read_excel(
        INPUT_FILE,
        sheet_name=SHEET_NAME,
        header=header_row,
    )

    print(
        "Dataframe shape after header detection: "
        f"{dataframe.shape}"
    )

    # ==================================================================
    # 5. Preserve actual pandas column labels
    # ==================================================================

    column_pairs = [
        (
            actual_column,
            clean_header(actual_column),
        )
        for actual_column in dataframe.columns
        if clean_header(actual_column)
    ]

    headers = [
        clean_header
        for _, clean_header in column_pairs
    ]

    print(
        f"\nDetected source columns: "
        f"{len(headers)}"
    )

    for index, header in enumerate(
        headers,
        1,
    ):

        print(
            f"{index:02d}. {header}"
        )

    # ==================================================================
    # 6. Build sample values
    # ==================================================================

    sample_values: dict[str, list[str]] = {}

    for (
        actual_column,
        clean_header_value,
    ) in column_pairs:

        values = (
            dataframe[actual_column]
            .dropna()
            .astype(str)
            .str.strip()
        )

        values = [
            value
            for value in values.tolist()
            if value
        ]

        sample_values[
            clean_header_value
        ] = values[:5]

    # ==================================================================
    # 7. Display sample values
    # ==================================================================

    print("\nSample values:")
    print("-" * 80)

    for header in headers:

        print(f"\n{header}")

        values = sample_values.get(
            header,
            [],
        )

        if not values:

            print(
                "  - <no non-empty values>"
            )

            continue

        for value in values:

            print(
                f"  - {value}"
            )

    # ==================================================================
    # 8. Initialize Agent 2
    # ==================================================================

    print("\n" + "=" * 80)
    print("INITIALIZING AGENT 2")
    print("=" * 80)

    agent = SchemaMappingAgent()

    # ==================================================================
    # 9. Create Agent 2 input
    # ==================================================================

    mapping_input = SchemaMappingInput(
        source_headers=headers,
        sample_values=sample_values,
    )

    # ==================================================================
    # 10. Run Agent 2
    # ==================================================================

    print("\nRunning schema mapping...\n")

    result = agent.map(
        mapping_input
    )

    # ==================================================================
    # 11. Display mappings
    #
    # IMPORTANT:
    # BatchMapping uses `source_header`, NOT `source_column`.
    # ==================================================================

    print("=" * 80)
    print("AGENT 2 MAPPING RESULT")
    print("=" * 80)

    print("\nMappings:")
    print("-" * 80)

    if not result.mappings:

        print(
            "No mappings produced."
        )

    else:

        for mapping in result.mappings:

            source = mapping.source_header
            target = mapping.target_field
            score = mapping.score
            method = mapping.method
            human_review = (
                mapping.human_review_required
            )
            reason = mapping.reason

            print(
                f"\nSource       : {source}"
            )

            print(
                f"Target       : {target}"
            )

            print(
                f"Score        : {score:.4f}"
            )

            print(
                f"Method       : {method}"
            )

            print(
                f"Human review : {human_review}"
            )

            print(
                f"Reason       : {reason}"
            )

    # ==================================================================
    # 12. Display unresolved columns
    # ==================================================================

    print("\n" + "=" * 80)
    print("UNRESOLVED COLUMNS")
    print("=" * 80)

    if result.unresolved_columns:

        for column in (
            result.unresolved_columns
        ):

            print(
                f"- {column}"
            )

    else:

        print("None")

    # ==================================================================
    # 13. Display assigned targets
    # ==================================================================

    print("\n" + "=" * 80)
    print("ASSIGNED TARGET FIELDS")
    print("=" * 80)

    if result.assigned_targets:

        for target in (
            result.assigned_targets
        ):

            print(
                f"- {target}"
            )

    else:

        print("None")

    # ==================================================================
    # 14. Display warnings
    # ==================================================================

    print("\n" + "=" * 80)
    print("WARNINGS")
    print("=" * 80)

    if result.warnings:

        for warning in result.warnings:

            print(
                f"- {warning}"
            )

    else:

        print("None")

    # ==================================================================
    # 15. Final summary
    # ==================================================================

    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    print(
        f"Source columns : "
        f"{len(headers)}"
    )

    print(
        f"Mappings       : "
        f"{len(result.mappings)}"
    )

    print(
        f"Unresolved     : "
        f"{len(result.unresolved_columns)}"
    )

    print(
        f"Targets used   : "
        f"{len(result.assigned_targets)}"
    )

    print(
        f"Warnings       : "
        f"{len(result.warnings)}"
    )

    print(
        "\nAgent 2 real run completed."
    )


if __name__ == "__main__":
    main()