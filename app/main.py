from app.ingestion.loader import load_sov_file


def print_state_summary(state):

    print("\n" + "=" * 60)
    print("SOV INGESTION SUMMARY")
    print("=" * 60)

    print(f"\nFile Name: {state.file_name}")
    print(f"File Type: {state.file_type}")

    print("\nSheets:")
    print("-" * 60)

    for sheet in state.sheets:

        print(
            f"{sheet.name:<20}"
            f"Rows: {sheet.rows:<8}"
            f"Columns: {sheet.columns:<8}"
            f"Empty: {sheet.is_empty}"
        )

    print("\nSelected Sheet:")
    print(state.selected_sheet)

    print("\nErrors:")
    print(state.errors)

    print("\nWarnings:")
    print(state.warnings)


def main():

    file_path = "data/input/sample_sov.csv"
    state = load_sov_file(file_path)

    print_state_summary(state)


if __name__ == "__main__":
    main()