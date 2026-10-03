
# SOVereign AI
## Step 1 — Project Foundation, State Management & SOV Ingestion

---

## 1. Objective

The objective of Step 1 is to establish the core backend foundation of the
SOVereign AI system.

At this stage, we are NOT implementing the agents.

We are creating the infrastructure that all future agents will use:

1. Project environment
2. Configuration management
3. SOVState
4. Pydantic schemas
5. Excel/CSV ingestion
6. Basic data representation
7. Initial column evidence generation
8. Validation of the ingestion pipeline

The output of this step will be a clean, structured representation of an
uploaded SOV file that can be passed to Agent 1 in the next step.


---

## 2. Why This Step Is Required

An SOV submission can contain:

- Multiple worksheets
- Different column names
- Header rows at different positions
- Empty rows
- Merged cells
- Notes and summary sheets
- Different data types
- Missing values
- Inconsistent formatting

Therefore, the downstream agents should not directly operate on the raw
uploaded file.

Instead, we first convert the uploaded file into a controlled internal
representation.

The architecture becomes:

    Raw SOV File
          |
          v
    Ingestion Layer
          |
          v
    Structured SOV Representation
          |
          v
       SOVState
          |
          v
    Agent 1 / Agent 2 / Agent 3 / Agent 4


---

## 3. Step 1 Architecture

                    USER UPLOAD
                         |
                         v
                +------------------+
                | File Validation  |
                +--------+---------+
                         |
                         v
                +------------------+
                | Excel / CSV      |
                | Reader           |
                +--------+---------+
                         |
                         v
                +------------------+
                | Raw Sheet Data   |
                +--------+---------+
                         |
                         v
                +------------------+
                | Initial Column   |
                | Evidence         |
                +--------+---------+
                         |
                         v
                +------------------+
                | SOVState         |
                +--------+---------+
                         |
                         v
                 Agent 1 Discovery


---

## 4. SOVState

SOVState is the shared state object used by the complete agentic workflow.

Every agent will read information from SOVState and add its own results
back to the state.

For example:

    Agent 1
       |
       v
    selected_sheet
       |
       v
    Agent 2
       |
       v
    mapping_candidates
       |
       v
    Agent 3
       |
       v
    quality_findings
       |
       v
    Agent 4
       |
       v
    transformation_results


This allows LangGraph to maintain a controlled state throughout the
workflow.


### Initial SOVState fields

The initial state should contain:

    file_name
    file_type
    sheets
    selected_sheet
    dataframe
    columns
    column_profiles
    metadata
    errors
    warnings

Later we will extend this state with:

    mapping_candidates
    mapping_confidence
    retrieved_examples
    validation_results
    anomalies
    proposed_actions
    human_approvals
    transformation_results
    audit_log


---

## 5. Pydantic Schemas

Pydantic will be used to define structured objects.

The purpose is to prevent different agents from passing arbitrary,
unstructured information to each other.

Example conceptual structure:

    ColumnProfile
        |
        +-- column_name
        +-- data_type
        +-- missing_ratio
        +-- unique_count
        +-- numeric_ratio
        +-- min
        +-- max
        +-- mean
        +-- median
        +-- patterns

    SOVState
        |
        +-- file information
        +-- sheets
        +-- dataframe
        +-- column profiles
        +-- workflow metadata


This gives the system a predictable internal contract.


---

## 6. SOV File Ingestion

The ingestion layer will support:

    .xlsx
    .xls
    .csv

For Excel files, each worksheet will initially be loaded separately.

Example:

    input.xlsx

        Sheet 1
        Sheet 2
        Sheet 3
        Sheet 4

will become:

    sheets = {
        "Sheet1": DataFrame,
        "Sheet2": DataFrame,
        "Sheet3": DataFrame,
        "Sheet4": DataFrame
    }


At this stage we do NOT decide which sheet is the primary SOV.

That decision belongs to Agent 1.


---

## 7. File Validation

Before processing the file, the ingestion layer should verify:

    - Supported file extension
    - File is readable
    - Workbook can be opened
    - At least one sheet exists
    - Sheet contains data
    - Data can be converted into a DataFrame

Invalid files should stop the workflow with a structured error rather
than causing an uncontrolled exception.


Example:

    Unsupported file
          |
          v
    FileValidationError
          |
          v
    SOVState.errors


---

## 8. Initial Column Evidence

Before the schema-mapping agent runs, we generate a basic fingerprint
for every column.

This includes information such as:

    Column name
    Data type
    Number of rows
    Missing values
    Unique values
    Numeric proportion
    String proportion
    Minimum
    Maximum
    Mean
    Median
    Standard deviation
    Quantiles
    String length
    Common values
    Basic value patterns


Example:

    Column:
        Construction Yr

    Evidence:

        dtype           → integer
        numeric_ratio   → 1.00
        missing_ratio   → 0.02
        unique_ratio    → 0.31
        min             → 1952
        max             → 2021
        median          → 1998
        year_pattern    → high


This information will later be used by the schema-mapping and data-quality
agents as supporting evidence.


---

## 9. Why Column Evidence Is Generated Early

The meaning of a column cannot always be determined from its name.

For example:

    "Yr Built"
    "Construction Yr"
    "Year Constructed"
    "Const. Year"

may all refer to the same target field.

The actual values provide additional evidence.

For example:

    Construction Yr

    1998
    2001
    2005
    2012
    2018

strongly indicates a year-like field.

Therefore the system preserves both:

    Header Information
            +
    Value Information

for later reasoning.


---

## 10. Handling Sensitive Data

SOV files may contain sensitive information such as:

    Names
    Addresses
    Property information
    Financial values

The ingestion layer should therefore avoid unnecessarily sending complete
row-level data to external LLM services.

The architecture will keep raw data locally and later provide agents with
only the minimum information required for reasoning.

The project specification also calls for masking names/addresses before
LLM use and sending only headers plus a small number of masked sample
values. 


---

## 11. Data Flow

The complete Step 1 flow is:

    Upload File
         |
         v
    Validate File
         |
         v
    Detect File Type
         |
         v
    Load Workbook / CSV
         |
         v
    Load Sheets
         |
         v
    Convert to DataFrames
         |
         v
    Generate Column Evidence
         |
         v
    Create SOVState
         |
         v
    Validate SOVState
         |
         v
    Pass State to Agent 1


---

## 12. Expected Output

At the end of Step 1, the system should be able to accept:

    SOV.xlsx

and produce an internal state similar to:

    SOVState

        file_name:
            "sample_sov.xlsx"

        file_type:
            "xlsx"

        sheets:
            ["Summary", "Property Data", "Notes"]

        selected_sheet:
            None

        columns:
            [...]

        column_profiles:
            {
                "Construction Yr": {...},
                "Bldg Repl Cost New": {...},
                "Sprk": {...}
            }

        warnings:
            [...]

        errors:
            []


The selected sheet remains None because Agent 1 has not yet been executed.


---

## 13. What Step 1 Does NOT Do

Step 1 does NOT:

    - Select the primary SOV sheet
    - Map columns to the 17 target fields
    - Use embeddings
    - Perform RAG retrieval
    - Call the LLM for mapping
    - Detect final data-quality issues
    - Modify source data
    - Transform the SOV
    - Generate the final cleaned file

Those capabilities will be implemented in later steps.


---

## 14. Definition of Done

Step 1 is complete when:

    [✓] Project environment works

    [✓] Configuration loads correctly

    [✓] Excel files can be read

    [✓] CSV files can be read

    [✓] Multiple Excel sheets are preserved

    [✓] Basic file validation works

    [✓] Column evidence is generated

    [✓] Pydantic schemas are defined

    [✓] SOVState is created successfully

    [✓] Errors are represented in the state

    [✓] A sample SOV can move through the complete ingestion pipeline

    [✓] The resulting state can be passed to Agent 1


---

## 15. Step 1 Output

The final output of Step 1 is:

        RAW SOV
           |
           v
      INGESTION
           |
           v
      COLUMN EVIDENCE
           |
           v
        SOVState
           |
           v
      READY FOR AGENT 1


This state becomes the foundation for the entire SOVereign AI agentic
workflow.

