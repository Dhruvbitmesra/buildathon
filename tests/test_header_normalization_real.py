from app.ingestion.loader import load_sov_file
from app.agents.sheet_discovery.header_detector import detect_header
from app.agents.sheet_discovery.header_normalizer import (
    normalize_header_row,
)


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

        detection = detect_header(df)

        header_row = detection["header_row"]

        print(f"\nSheet: {sheet_name}")
        print(f"Detected header: {header_row}")
        print(
            f"Confidence: "
            f"{detection['header_confidence']}"
        )

        if header_row is None:
            print("No header detected.")
            continue

        headers = normalize_header_row(
            df,
            header_row,
        )

        print("\nOriginal → Normalized")

        for header in headers:
            print(
                f"{header['original']!r}"
                f"  →  "
                f"{header['normalized']!r}"
            )