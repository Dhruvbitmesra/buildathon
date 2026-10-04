"""
Agent 4: Controlled Transformation and Output.

Activates only after every review item has a human decision. It:
1. builds the 17 target columns from approved column mappings;
2. applies approved cell changes (ApprovedChange from Agent 3), using
   the same normalizers that produced the reviewer's preview;
3. casts each column to its data-dictionary type, leaving missing
   values blank (never zero or "N/A");
4. writes Cleaned_SOV.xlsx (sheet "Cleaned_SOV", headers in row 1, no
   merged cells) with an Audit_Log sheet, plus Audit_Log.json;
5. validates the written file against the schema (NFR-5).

The source data table is never modified.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import pandas as pd
from openpyxl import Workbook, load_workbook
from pydantic import BaseModel, Field

from app.agents.data_quality import normalizers
from app.agents.data_quality.config import SOV_REQUIRED_FIELDS
from app.agents.data_quality.normalizers import Operation
from app.agents.data_quality.recommendation_schema import ApprovedChange


OUTPUT_FILE = "Cleaned_SOV.xlsx"
OUTPUT_SHEET = "Cleaned_SOV"
AUDIT_SHEET = "Audit_Log"
AUDIT_JSON = "Audit_Log.json"
AUDIT_XLSX = "Audit_Log.xlsx"
SUMMARY_JSON = "Processing_Summary.json"
SUMMARY_MD = "Processing_Summary.md"

# Data dictionary (problem statement, section 08).
FIELD_TYPES = {
    "Reference": "string",
    "Address": "string",
    "City": "string",
    "State": "string",
    "Zip": "integer",
    "County": "string",
    "Country": "string",
    "Building Value": "float",
    "Contents": "float",
    "BI": "float",
    "Occupancy": "string",
    "Construction": "string",
    "Storeys": "integer",
    "Number of Buildings": "integer",
    "Year Built": "integer",
    "Fire Sprinklers (Y/N)": "string",
    "Other": "float",
}


ALLOWED_VALUES = {
    "Fire Sprinklers (Y/N)": {"Y", "N", "Y13", "Y(13R)"},
}


class ExportBlockedError(RuntimeError):
    """Raised when export is attempted before every item is reviewed."""


class AuditEntry(BaseModel):
    source_column: Optional[str] = None
    target_column: Optional[str] = None
    source_row: Optional[int] = None
    transformation_applied: str
    before_value: Any = None
    after_value: Any = None
    confidence: Optional[float] = None
    approved_by: str
    timestamp: str
    rationale: str
    recommendation_id: Optional[str] = None


class TransformationResult(BaseModel):
    output_path: str
    audit_json_path: str
    audit_xlsx_path: str = ""
    summary_path: str = ""
    rows: int
    applied_changes: int
    audit_entries: int
    blanked_uncastable_cells: int
    schema_valid: bool
    schema_problems: list[str] = Field(default_factory=list)


class TransformationAgent:
    def transform(
        self,
        data_table: pd.DataFrame,
        mappings: list[dict],
        changes: list[ApprovedChange],
        ledger: Any,
        require_complete: bool = True,
    ) -> tuple[pd.DataFrame, list[AuditEntry], int]:
        """
        Build the cleaned DataFrame and its audit entries.

        data_table: Agent 1's table (index = Excel row numbers).
        mappings:   Agent 2 mappings (used only through approved
                    column-mapping changes).
        changes:    ReviewSession.approved_changes().
        ledger:     ReviewLedger; export requires ledger.export_ready.
        """

        # require_complete=False builds a preview with the decisions made
        # so far; it is never written as Cleaned_SOV.xlsx.
        if require_complete and not ledger.export_ready:
            pending = ledger.pending()
            raise ExportBlockedError(
                f"{len(pending)} recommendation(s) still need a review "
                "decision; export is blocked (FR-5)."
            )

        now = datetime.now(timezone.utc).isoformat()
        audit: list[AuditEntry] = []

        # 1. Approved column mappings -----------------------------------
        target_to_source: dict[str, str] = {}

        for change in changes:
            if change.transformation_applied != Operation.RENAME_COLUMN:
                continue

            target_to_source[change.target_column] = change.source_column
            audit.append(
                AuditEntry(
                    source_column=change.source_column,
                    target_column=change.target_column,
                    transformation_applied="rename_column",
                    before_value=change.source_column,
                    after_value=change.target_column,
                    confidence=change.confidence,
                    approved_by=change.approved_by,
                    timestamp=change.timestamp.isoformat(),
                    rationale=change.rationale,
                    recommendation_id=change.recommendation_id,
                )
            )

        rows = list(data_table.index)
        output = pd.DataFrame(
            {
                field: (
                    data_table[target_to_source[field]].astype(object).tolist()
                    if field in target_to_source
                    else [None] * len(rows)
                )
                for field in SOV_REQUIRED_FIELDS
            },
            dtype=object,
        )

        # Agent 3 positions -> output positions are identical (same row
        # order); keep the Excel row for the audit log.
        excel_rows = {position: int(row) for position, row in enumerate(rows)}

        # 2. Approved cell changes --------------------------------------
        applied = 0

        for change in changes:
            if change.transformation_applied == Operation.RENAME_COLUMN:
                continue

            field = change.target_column

            if field not in target_to_source:
                raise ValueError(
                    f"{change.recommendation_id}: '{field}' has no approved "
                    "column mapping; re-run the analysis after changing "
                    "mappings."
                )

            if change.source_column and target_to_source[field] != change.source_column:
                raise ValueError(
                    f"{change.recommendation_id}: approved for source column "
                    f"'{change.source_column}' but {field} is now mapped from "
                    f"'{target_to_source[field]}'; re-run the analysis."
                )

            position = change.row_index
            current = output.at[position, field]

            if repr(_plain(current)) != repr(_plain(change.before_value)):
                raise ValueError(
                    f"{change.recommendation_id}: row {position} {field} is "
                    f"{current!r}, expected {change.before_value!r}."
                )

            output.at[position, field] = change.after_value
            applied += 1
            audit.append(
                AuditEntry(
                    source_column=change.source_column,
                    target_column=field,
                    source_row=change.source_row or excel_rows.get(position),
                    transformation_applied=change.transformation_applied.value,
                    before_value=_plain(change.before_value),
                    after_value=_plain(change.after_value),
                    confidence=change.confidence,
                    approved_by=change.approved_by,
                    timestamp=change.timestamp.isoformat(),
                    rationale=change.rationale,
                    recommendation_id=change.recommendation_id,
                )
            )

        # 3. Type casting -----------------------------------------------
        blanked = 0

        for field in SOV_REQUIRED_FIELDS:
            casted, failures, converted = _cast_column(
                output[field],
                FIELD_TYPES[field],
                ALLOWED_VALUES.get(field),
            )
            output[field] = casted

            # NFR-3: every cell whose stored value changes is logged.
            for position, before, after in converted:
                audit.append(
                    AuditEntry(
                        source_column=target_to_source.get(field),
                        target_column=field,
                        source_row=excel_rows.get(position),
                        transformation_applied=f"cast_to_{FIELD_TYPES[field]}",
                        before_value=_plain(before),
                        after_value=after,
                        confidence=1.0,
                        approved_by="data_dictionary",
                        timestamp=now,
                        rationale=(
                            "Lossless type cast required by the target data "
                            f"dictionary ({field} is {FIELD_TYPES[field]})."
                        ),
                    )
                )

            for position, value in failures:
                blanked += 1
                audit.append(
                    AuditEntry(
                        source_column=target_to_source.get(field),
                        target_column=field,
                        source_row=excel_rows.get(position),
                        transformation_applied="uncastable_value_left_blank",
                        before_value=_plain(value),
                        after_value=None,
                        confidence=1.0,
                        approved_by="data_dictionary",
                        timestamp=now,
                        rationale=(
                            f"The reviewed value is not a valid "
                            f"{FIELD_TYPES[field]} for {field}; the cell is left blank "
                            "(no placeholder) and the original value is "
                            "kept here."
                        ),
                    )
                )

        return output, audit, applied

    def export(
        self,
        data_table: pd.DataFrame,
        mappings: list[dict],
        changes: list[ApprovedChange],
        ledger: Any,
        output_dir: str | Path,
        context: Optional[dict[str, Any]] = None,
    ) -> TransformationResult:
        output, audit, applied = self.transform(
            data_table, mappings, changes, ledger
        )

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        workbook_path = output_dir / OUTPUT_FILE
        audit_path = output_dir / AUDIT_JSON
        audit_xlsx_path = output_dir / AUDIT_XLSX

        # FR-6: Cleaned_SOV.xlsx is single-sheet; the audit log is a
        # separate Audit_Log.xlsx / Audit_Log.json (C-07).
        _write_workbook(output, workbook_path)

        # Serialise the audit once; reuse for the workbook and the JSON.
        records = [entry.model_dump() for entry in audit]
        _write_audit_workbook(records, audit_xlsx_path)

        audit_path.write_text(
            json.dumps(records, indent=1, default=str),
            encoding="utf-8",
        )

        problems = validate_output(workbook_path)
        blanked = sum(
            1
            for entry in audit
            if entry.transformation_applied == "uncastable_value_left_blank"
        )

        result = TransformationResult(
            output_path=str(workbook_path),
            audit_json_path=str(audit_path),
            audit_xlsx_path=str(audit_xlsx_path),
            rows=int(len(output)),
            applied_changes=applied,
            audit_entries=len(audit),
            blanked_uncastable_cells=blanked,
            schema_valid=not problems,
            schema_problems=problems,
        )

        summary_path = write_processing_summary(
            output_dir, result, audit, ledger, context or {}
        )

        return result.model_copy(update={"summary_path": str(summary_path)})


def _plain(value: Any) -> Any:
    if normalizers.is_missing(value):
        return None

    if hasattr(value, "item") and not isinstance(value, str):
        try:
            return value.item()
        except (TypeError, ValueError):
            return value

    if isinstance(value, pd.Timestamp):
        return value.isoformat()

    return value


def _cast_column(
    series: pd.Series,
    field_type: str,
    allowed: set[str] | None = None,
) -> tuple[list[Any], list[tuple[int, Any]], list[tuple[int, Any, Any]]]:
    """
    Return (cast values, uncastable (position, value),
    converted (position, before, after)).
    """

    values: list[Any] = []
    failures: list[tuple[int, Any]] = []
    converted: list[tuple[int, Any, Any]] = []

    for position, value in enumerate(series.tolist()):
        if normalizers.is_missing(value):
            values.append(None)
            continue

        cast = _cast_value(value, field_type)

        if allowed is not None and cast not in allowed:
            cast = None

        if cast is None:
            failures.append((position, value))
            values.append(None)
            continue

        if type(cast) is not type(value) or cast != value:
            converted.append((position, value, cast))

        values.append(cast)

    return values, failures, converted


def _cast_value(value: Any, field_type: str) -> Any:
    if field_type == "string":
        if normalizers.is_number(value):
            number = float(value)
            return str(int(number)) if number.is_integer() else str(value)

        return str(value)

    if field_type == "float":
        return (
            float(value)
            if normalizers.is_number(value)
            else None
        )

    if field_type == "integer":
        if isinstance(value, str):
            digits = value.strip()
            # ZIP+4 is kept as its 5-digit ZIP; the dictionary types Zip
            # as an integer.
            if len(digits) == 10 and digits[5] == "-" and digits[:5].isdigit():
                digits = digits[:5]
            return int(digits) if digits.isdigit() else None

        if normalizers.is_number(value) and float(value).is_integer():
            return int(value)

        return None

    return None


def _write_workbook(output: pd.DataFrame, path: Path) -> None:
    """Single sheet "Cleaned_SOV": headers in row 1, data from row 2."""

    from openpyxl.cell import WriteOnlyCell

    workbook = Workbook(write_only=True)
    sheet = workbook.create_sheet(OUTPUT_SHEET)
    sheet.append(list(SOV_REQUIRED_FIELDS))
    zip_index = SOV_REQUIRED_FIELDS.index("Zip")

    for row in output.itertuples(index=False):
        values = [None if normalizers.is_missing(v) else v for v in row]
        zip_value = values[zip_index]

        # Zip is an integer (data dictionary) displayed with 5 digits so
        # leading zeros stay visible (00802). No colour formatting.
        if isinstance(zip_value, int):
            cell = WriteOnlyCell(sheet, value=zip_value)
            cell.number_format = "00000"
            values[zip_index] = cell

        sheet.append(values)

    workbook.save(path)


def _write_audit_workbook(records: list[dict], path: Path) -> None:
    workbook = Workbook(write_only=True)
    sheet = workbook.create_sheet(AUDIT_SHEET)
    columns = list(AuditEntry.model_fields)
    sheet.append(columns)
    primitive = (int, float, str)

    for record in records:
        sheet.append(
            [
                value
                if value is None or isinstance(value, primitive)
                else json.dumps(value, default=str)
                for value in (record[column] for column in columns)
            ]
        )

    workbook.save(path)


def write_processing_summary(
    output_dir: Path,
    result: "TransformationResult",
    audit: list[AuditEntry],
    ledger: Any,
    context: dict[str, Any],
) -> Path:
    """Agent 4's processing summary report (JSON + readable Markdown)."""

    from collections import Counter

    transformations = Counter(entry.transformation_applied for entry in audit)
    review = ledger.summary()
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        **context,
        "review": review,
        "output": {
            "file": OUTPUT_FILE,
            "rows": result.rows,
            "schema_valid": result.schema_valid,
            "schema_problems": result.schema_problems,
        },
        "transformations": dict(transformations),
        "approved_changes_applied": result.applied_changes,
        "uncastable_cells_left_blank": result.blanked_uncastable_cells,
        "audit_entries": result.audit_entries,
    }

    (output_dir / SUMMARY_JSON).write_text(
        json.dumps(summary, indent=2, default=str), encoding="utf-8"
    )

    lines = [
        "# SOV Processing Summary",
        "",
        f"- Generated: {summary['generated_at']}",
    ]

    for key in ("source_file", "selected_sheet", "header_row", "llm_enabled"):
        if key in context:
            lines.append(f"- {key.replace('_', ' ').title()}: {context[key]}")

    if "mapping" in context:
        mapping = context["mapping"]
        lines += [
            "",
            "## Schema mapping",
            f"- Mapped columns: {mapping.get('mapped')}",
            f"- Unresolved columns: {mapping.get('unresolved')}",
            f"- Overall confidence: {mapping.get('overall_confidence')}",
        ]

    if "quality" in context:
        quality = context["quality"]
        lines += [
            "",
            "## Data quality at intake",
            f"- Intake quality score: {quality.get('intake_quality_score')}",
            f"- Issues: {quality.get('total_issues')}",
            f"- By severity: {quality.get('issues_by_severity')}",
        ]

    lines += [
        "",
        "## Human review",
        f"- Recommendations: {review['total']}",
        f"- Decisions: {review['by_status']}",
        "",
        "## Output",
        f"- {OUTPUT_FILE}: {result.rows} rows, schema valid: {result.schema_valid}",
        f"- Approved changes applied: {result.applied_changes}",
        f"- Values not representable in the schema type, left blank: "
        f"{result.blanked_uncastable_cells}",
        f"- Audit entries: {result.audit_entries} ({AUDIT_XLSX}, {AUDIT_JSON})",
        "",
        "| Transformation | Cells |",
        "|---|---|",
    ]
    lines += [f"| {name} | {count} |" for name, count in transformations.most_common()]

    if "timings" in context:
        lines += ["", "## Timings (s)"]
        lines += [f"- {k}: {v:.1f}" for k, v in context["timings"].items()]

    path = output_dir / SUMMARY_MD
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def validate_output(path: str | Path) -> list[str]:
    """
    Check the written workbook against the target schema (NFR-5, FR-6):
    single sheet "Cleaned_SOV", the 17 headers in order, no merged cells,
    cell types per the data dictionary, allowed sprinkler values.
    """

    import zipfile

    problems: list[str] = []
    workbook = load_workbook(path, read_only=True)

    try:
        if OUTPUT_SHEET not in workbook.sheetnames:
            return [f"sheet '{OUTPUT_SHEET}' is missing"]

        if workbook.sheetnames != [OUTPUT_SHEET]:
            problems.append(
                f"workbook must have a single sheet; found {workbook.sheetnames}"
            )

        sheet = workbook[OUTPUT_SHEET]
        rows = sheet.iter_rows(values_only=True)
        header = list(next(rows, []))

        if header != list(SOV_REQUIRED_FIELDS):
            problems.append(f"headers are {header}")
            return problems

        expected = {
            "string": (str,),
            "float": (float, int),
            "integer": (int,),
        }
        reported: set[str] = set()

        for row_number, row in enumerate(rows, start=2):
            for field, value in zip(SOV_REQUIRED_FIELDS, row):
                if value is None or field in reported:
                    continue

                allowed = expected[FIELD_TYPES[field]]

                if isinstance(value, bool) or not isinstance(value, allowed):
                    problems.append(
                        f"{field} row {row_number}: {value!r} is not "
                        f"{FIELD_TYPES[field]}"
                    )
                    reported.add(field)

                elif field in ALLOWED_VALUES and value not in ALLOWED_VALUES[field]:
                    problems.append(
                        f"{field} row {row_number}: {value!r} is not an allowed value"
                    )
                    reported.add(field)
    finally:
        workbook.close()

    with zipfile.ZipFile(path) as archive:
        for name in archive.namelist():
            if name.startswith("xl/worksheets/") and b"<mergeCell" in archive.read(name):
                problems.append("sheet contains merged cells")
                break

    return problems
