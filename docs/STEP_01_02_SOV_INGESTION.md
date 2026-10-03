# SOVereign AI
## Step 1.2 — SOV File Ingestion

---

## 1. Objective

The objective of Step 1.2 is to build a reliable ingestion layer that can
accept SOV files and convert them into a standardized internal
representation.

The ingestion layer supports:

    - Excel workbooks (.xlsx / .xls)
    - CSV files (.csv)

The output of this layer is a structured SOVState containing:

    - File information
    - Worksheet information
    - Raw sheet data
    - Basic structural metadata
    - Initial warnings/errors

This state will later be passed to Agent 1 for sheet discovery.


---

## 2. Why an Ingestion Layer Is Required

SOV submissions can have different structures.

A workbook may contain:

    Summary
    Property Data
    Notes
    Instructions
    Additional worksheets

The system cannot assume that:

    - The first sheet is the SOV
    - The first row contains headers
    - Every sheet contains tabular data
    - Excel and CSV files have the same structure

Therefore, ingestion should preserve the original structure instead of
making decisions about the data too early.


---

## 3. Position in the Overall System

The ingestion layer is the first processing stage after file upload.

    USER UPLOAD
         |
         v
    File Validation
         |
         v
    File Type Detection
         |
         v
    Excel / CSV Reader
         |
         v
    Sheet Data
         |
         v
    SOVState
         |
         v
    Agent 1 — Sheet Discovery


The ingestion layer does NOT decide which sheet is the primary SOV.

That responsibility belongs to Agent 1.


---

## 4. Architecture

                         SOV FILE
                            |
                            v
                  +--------------------+
                  | File Validator     |
                  +---------+----------+
                            |
                            v
                    File Type Detection
                            |
                 +----------+----------+
                 |                     |
              Excel                    CSV
                 |                     |
                 v                     v
          Excel Reader            CSV Reader
                 |                     |
                 +----------+----------+
                            |
                            v
                     DataFrames
                            |
                            v
                        SOVState
                            |
                            v
                   Agent 1 Discovery


---

## 5. File Validation

Before reading a file, the system validates the input.

The validator checks:

    1. File exists
    2. Path points to a file
    3. File extension is supported

Supported extensions:

    .xlsx
    .xls
    .csv

Invalid files should produce a controlled error rather than an
unhandled exception.

Example:

    Invalid File
         |
         v
    FileValidationError
         |
         v
    SOVState.errors


---

## 6. File Type Detection

The file extension determines which reader should be used.

    .xlsx / .xls
         |
         v
    Excel Reader

    .csv
         |
         v
    CSV Reader


The rest of the application should not need to know how the original file
was read.

Both readers produce the same conceptual output:

    sheet_data
    sheet_info


This allows the downstream agents to work with a common representation.


---

## 7. Excel Ingestion

An Excel workbook may contain multiple worksheets.

For example:

    sample_sov.xlsx

        Summary
        Property Data
        Notes


The Excel reader loads every worksheet independently.

Conceptually:

    Workbook
       |
       +── Sheet 1 → DataFrame
       |
       +── Sheet 2 → DataFrame
       |
       +── Sheet 3 → DataFrame


Each worksheet is stored using its original sheet name.

Example:

    sheet_data = {

        "Summary": DataFrame,

        "Property Data": DataFrame,

        "Notes": DataFrame
    }


---

## 8. Why We Do Not Detect Headers During Ingestion

The ingestion layer deliberately reads Excel sheets without assuming a
header row.

For example:

    pd.read_excel(
        file,
        header=None
    )


This is important because the project identifies situations where:

    - Header rows can occur at different positions
    - Headers can span multiple rows
    - Cells can be merged
    - Sheets can contain notes or summaries before the actual table


Therefore, the raw structure must be preserved.

Agent 1 will later identify the actual header row and determine whether a
sheet is:

    Primary
    Secondary
    Reject


---

## 9. CSV Ingestion

CSV files do not contain worksheets.

To maintain a common internal representation, a CSV is treated as one
logical sheet:

    CSV file
       |
       v
    "CSV_Data"
       |
       v
    DataFrame


This allows the downstream workflow to treat Excel and CSV consistently.


---

## 10. SheetInfo

For every sheet, the ingestion layer creates a SheetInfo object.

Example:

    SheetInfo

        name:
            "Property Data"

        rows:
            1050

        columns:
            24

        is_empty:
            False


This information is intentionally basic.

Agent 1 will later use richer evidence to score the sheets.


---

## 11. Raw Sheet Data

The actual DataFrame is preserved inside SOVState.

Example:

    state.sheet_data

        {
            "Summary": <DataFrame>,

            "Property Data": <DataFrame>,

            "Notes": <DataFrame>
        }


This is important because later agents need access to the original data.

The ingestion layer should not:

    - Rename columns
    - Remove rows
    - Select the primary sheet
    - Transform values
    - Fill missing values
    - Modify the source data


At this stage, the goal is preservation rather than transformation.


---

## 12. SOVState After Ingestion

After successful ingestion, SOVState will contain information similar to:

    SOVState

        file_name:
            "sample_sov.xlsx"

        file_type:
            "xlsx"

        sheets:
            [
                {
                    name: "Summary",
                    rows: 3,
                    columns: 1
                },
                {
                    name: "Property Data",
                    rows: 100,
                    columns: 6
                },
                {
                    name: "Notes",
                    rows: 4,
                    columns: 1
                }
            ]

        selected_sheet:
            None

        sheet_data:
            {
                "Summary": DataFrame,
                "Property Data": DataFrame,
                "Notes": DataFrame
            }

        errors:
            []

        warnings:
            []


The selected_sheet remains None because Agent 1 has not yet made a
decision.


---

## 13. Initial Data Evidence

The ingestion pipeline also prepares the system for later analysis by
preserving column-level evidence.

Examples of useful evidence include:

    - Data type
    - Number of records
    - Missing values
    - Unique values
    - Numeric proportion
    - String proportion
    - Minimum
    - Maximum
    - Mean
    - Median
    - Quantiles
    - Common values
    - Value patterns


Example:

    Construction Yr

        numeric_ratio:
            1.00

        missing_ratio:
            0.02

        min:
            1950

        max:
            2021

        median:
            1998

        year_pattern:
            high


This evidence will later support schema mapping and data-quality
reasoning.

The ingestion stage does not use this evidence to make the final field
mapping decision.


---

## 14. Data Preservation Principle

A central principle of this stage is:

    READ → REPRESENT → PRESERVE

not:

    READ → MODIFY


The original SOV should remain untouched until an approved transformation
is explicitly executed later in the workflow.

This supports the project's human-in-control and controlled-transformation
requirements.


---

## 15. Error Handling

Possible ingestion errors include:

    File does not exist
    Unsupported file extension
    Corrupted workbook
    Workbook cannot be opened
    CSV cannot be parsed
    Empty workbook
    Empty sheet


Errors should be captured in a structured way.

Example:

    state.errors = [
        "Unable to read workbook"
    ]


Warnings should be used for non-fatal conditions.

Example:

    state.warnings = [
        "Sheet 'Notes' contains very few rows"
    ]


The distinction is:

    ERROR
        Processing cannot safely continue.

    WARNING
        Processing can continue, but the condition should be recorded.


---

## 16. Components

Step 1.2 introduces the following components:

    app/
    └── ingestion/
        ├── file_validator.py
        ├── excel_reader.py
        ├── csv_reader.py
        ├── loader.py
        └── create_sample.py


### file_validator.py

Responsible for:

    - File existence
    - File type validation
    - Supported extension checking


### excel_reader.py

Responsible for:

    - Opening Excel workbooks
    - Reading all worksheets
    - Creating DataFrames
    - Creating SheetInfo


### csv_reader.py

Responsible for:

    - Reading CSV files
    - Creating one logical sheet
    - Creating SheetInfo


### loader.py

Acts as the main ingestion interface.

Instead of other parts of the application calling individual readers,
they call:

    load_sov_file()


The loader determines which reader should be used.


### create_sample.py

Creates a synthetic SOV workbook for development and testing when an
official SOV file is not yet available.


---

## 17. Synthetic SOV for Development

Until a real SOV file is available, we use a synthetic workbook.

Example:

    sample_sov.xlsx

    ├── Summary
    ├── Property Data
    └── Notes


Property Data may contain:

    Location ID
    Bldg Repl Cost New
    Construction Yr
    No. Floors
    Sprk
    Zip


This synthetic file allows development of the complete pipeline without
waiting for the official hackathon dataset.


---

## 18. Example Development Flow

    create_sample.py
          |
          v
    sample_sov.xlsx
          |
          v
    load_sov_file()
          |
          v
    validate_file()
          |
          v
    detect extension
          |
          v
    Excel Reader
          |
          v
    read all sheets
          |
          v
    create SheetInfo
          |
          v
    create SOVState
          |
          v
    Agent 1


---

## 19. What Step 1.2 Does NOT Do

This stage does NOT:

    - Identify the primary SOV sheet
    - Detect the final header row
    - Join multi-row headers
    - Map source columns to target fields
    - Use embeddings
    - Perform RAG retrieval
    - Call an LLM
    - Correct invalid values
    - Fill missing values
    - Transform the source data
    - Export the final SOV


These operations belong to later stages of the workflow.


---

## 20. Definition of Done

Step 1.2 is complete when:

    [✓] Supported file types are defined

    [✓] File validation works

    [✓] Excel files can be loaded

    [✓] Multiple worksheets are preserved

    [✓] CSV files can be loaded

    [✓] SheetInfo is generated

    [✓] Raw DataFrames are stored in SOVState

    [✓] File errors are handled

    [✓] Synthetic SOV can be generated

    [✓] Synthetic SOV can pass through the ingestion pipeline

    [✓] SOVState is ready for Agent 1


---

## 21. Output of Step 1.2

The final output is:

                         SOV FILE
                            |
                            v
                       VALIDATION
                            |
                            v
                         READER
                            |
                            v
                     SHEET DATA
                            |
                            v
                        SOVState
                            |
                            v
                  READY FOR AGENT 1


The ingestion layer therefore acts as the controlled boundary between
the uploaded SOV file and the agentic workflow.