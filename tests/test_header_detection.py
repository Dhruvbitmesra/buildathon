from app.ingestion.loader import load_sov_file
from app.agents.sheet_discovery.header_detector import detect_header


files = [
    "data/input/SOV_B4ID.xlsx",
    "data/input/SOV_H6D2.xlsx",
    "data/input/SOV_K4T9.xlsx",
    "data/input/SOV_Q8B3.xlsx",
]


for file_path in files:
    print("\n" + "=" * 80)
    print(file_path)
    print("=" * 80)

    state = load_sov_file(file_path)

    for sheet_name, df in state.sheet_data.items():

        result = detect_header(df)

        print(f"\nSheet: {sheet_name}")
        print(f"Rows: {len(df)} | Columns: {len(df.columns)}")

        print(
            f"Detected header row: "
            f"{result['header_row']}"
        )

        print(
            f"Score: "
            f"{result['header_score']}"
        )

        print(
            f"Confidence: "
            f"{result['header_confidence']}"
        )

        print(
            f"Possible multi-row header: "
            f"{result['possible_multirow_header']}"
        )

        if result["header_row"] is not None:
            row = df.iloc[result["header_row"]]

            print("Detected values:")

            print(
                [
                    str(value)
                    for value in row.tolist()
                    if str(value).strip() != "nan"
                ]
            )

        print("\nTop candidates:")

        for candidate in result["candidate_rows"][:3]:
            print(
                f"  Row {candidate['row']} "
                f"→ score={candidate['score']} "
                f"text={candidate['text_ratio']} "
                f"SOV={candidate['sov_term_ratio']} "
                f"data_below={candidate['data_below_score']}"
            )