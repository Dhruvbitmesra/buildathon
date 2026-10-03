# Step 1.3 — Agent 1: Sheet Discovery & Header Detection

## 1. Objective

The objective of Agent 1 is to automatically identify which sheets in an SOV workbook contain meaningful property/exposure data and determine where the actual table header begins.

The system must not assume that:

- the first sheet is the SOV sheet
- the first row contains headers
- every workbook contains only one useful sheet
- every sheet with location-related columns is a primary SOV
- headers always occupy a single row

Agent 1 prepares the workbook for downstream schema mapping and data-quality analysis.

---

## 2. Why Sheet Discovery Is Required

Real SOV workbooks can contain:

- multiple worksheets
- summary sheets
- notes and disclaimer sheets
- reference/glossary sheets
- historical data
- deleted locations
- insured-elsewhere records
- BI/value information
- blank rows before the actual table
- merged cells
- grouped headers
- multi-row headers

The actual SOV data received for the project demonstrates these cases.

Therefore, selecting a sheet manually or assuming that row 1 is the header would make the system unreliable.

The first agent must discover the structure before any schema mapping or transformation is performed.

---

## 3. Real Dataset Observations

The real SOV files will be used as the primary development and evaluation dataset.

### SOV_B4ID.xlsx

The workbook contains a single sheet with formatting and metadata before the actual table.

The actual data header does not begin at row 1.

The workbook contains fields such as:

- Loc #
- Bldg.
- Street
- City
- State
- Zip

This demonstrates that the system must search for the actual header row rather than assuming the first row is the header.

---

### SOV_H6D2.xlsx

The workbook contains a large SOV table.

The actual header begins below several preceding rows.

The dataset contains fields such as:

- Item #
- Facility Name
- Street Address
- City
- County
- State

This file is useful for testing header detection and large-sheet profiling.

---

### SOV_K4T9.xlsx

This workbook contains multiple sheets, including sheets representing:

- summary information
- year-over-year comparison
- locations
- glossary/reference information
- confidentiality/disclaimer information
- original client data

This provides a real test case for distinguishing the primary SOV data from supporting or non-data worksheets.

---

### SOV_Q8B3.xlsx

This workbook contains multiple sheets representing different types of information, including:

- property/value information
- BI values
- automobile data
- trailers
- equipment
- deleted locations
- insured-elsewhere information

This demonstrates that the presence of location-like or financial columns alone is not sufficient to classify a sheet as the primary SOV.

---

## 4. Agent 1 Responsibilities

Agent 1 performs two major tasks:

1. Sheet-level discovery
2. Header-row detection

The overall process is:

    Raw Workbook
          ↓
    Inspect Every Sheet
          ↓
    Profile Sheet Structure
          ↓
    Detect Candidate Header Rows
          ↓
    Score Sheets
          ↓
    Classify Sheets
          ↓
    Primary / Secondary / Reject
          ↓
    Prepare Selected Sheet for Agent 2

---

# 5. Sheet-Level Profiling

Every worksheet should be profiled before selecting a primary sheet.

For each sheet, we collect structural evidence such as:

- sheet name
- number of rows
- number of columns
- number of non-empty cells
- overall data density
- blank-row ratio
- blank-column ratio
- candidate header rows
- header-likeness
- type consistency
- null ratio
- row volume
- presence of location/property-related terms
- presence of numeric/value-heavy columns

The purpose of profiling is not to transform the data.

It is to gather evidence that allows the agent to make a reliable decision.

---

# 6. Header-Row Detection

The system must search for the actual header row instead of assuming:

```python
header=0