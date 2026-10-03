import pandas as pd


def create_sample_sov(output_path: str):

    summary = pd.DataFrame([
        ["SOV Submission"],
        ["Client: ABC Insurance"],
        ["Prepared: 2026"],
    ])

    property_data = pd.DataFrame([
        [
            "Location ID",
            "Bldg Repl Cost New",
            "Construction Yr",
            "No. Floors",
            "Sprk",
            "Zip",
        ],
        [
            "LOC001",
            450000,
            1998,
            2,
            "Y",
            "82601",
        ],
        [
            "LOC002",
            720000,
            2005,
            3,
            "N",
            "80202",
        ],
        [
            "LOC003",
            1200000,
            2010,
            5,
            "Y",
            "94105",
        ],
        [
            "LOC004",
            300000,
            1985,
            1,
            "Y",
            "81301",
        ],
    ])

    notes = pd.DataFrame([
        ["Notes"],
        ["Values supplied by client"],
        ["Please review missing values"],
    ])

    with pd.ExcelWriter(
        output_path,
        engine="openpyxl",
    ) as writer:

        summary.to_excel(
            writer,
            sheet_name="Summary",
            index=False,
            header=False,
        )

        property_data.to_excel(
            writer,
            sheet_name="Property Data",
            index=False,
            header=False,
        )

        notes.to_excel(
            writer,
            sheet_name="Notes",
            index=False,
            header=False,
        )


if __name__ == "__main__":

    create_sample_sov(
        "data/input/sample_sov.xlsx"
    )

    print(
        "Sample SOV created successfully."
    )