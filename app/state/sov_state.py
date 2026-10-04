from typing import Any, Optional

from pydantic import BaseModel, Field


class ColumnProfile(BaseModel):
    """
    Structural and value-level profile of one SOV column.
    """

    column_name: str
    data_type: str

    total_count: int = 0
    missing_count: int = 0
    missing_ratio: float = 0.0

    unique_count: int = 0
    unique_ratio: float = 0.0

    numeric_ratio: float = 0.0
    string_ratio: float = 0.0

    min_value: Optional[float] = None
    max_value: Optional[float] = None
    mean: Optional[float] = None
    median: Optional[float] = None
    std: Optional[float] = None
    q1: Optional[float] = None
    q3: Optional[float] = None

    top_values: dict[str, int] = Field(
        default_factory=dict
    )

    patterns: dict[str, float] = Field(
        default_factory=dict
    )


class SheetInfo(BaseModel):
    """
    Metadata about one worksheet.
    """

    name: str
    rows: int = 0
    columns: int = 0
    is_empty: bool = False


class SOVState(BaseModel):
    """
    Shared state for the SOVereign AI workflow.
    """

    file_name: Optional[str] = None
    file_type: Optional[str] = None

    sheets: list[SheetInfo] = Field(
        default_factory=list
    )

    selected_sheet: Optional[str] = None

    # Raw sheet data.
    # Key = sheet name
    # Value = pandas DataFrame
    sheet_data: dict[str, Any] = Field(
        default_factory=dict
    )

    columns: list[str] = Field(
        default_factory=list
    )

    column_profiles: dict[str, ColumnProfile] = Field(
        default_factory=dict
    )

    metadata: dict[str, Any] = Field(
        default_factory=dict
    )

    warnings: list[str] = Field(
        default_factory=list
    )

    errors: list[str] = Field(
        default_factory=list
    )

    # ------------------------------------------------------------------
    # Agent 2 -> Agent 3
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Agent 1 -> Agent 2
    # ------------------------------------------------------------------

    # Ranked sheet manifest: sheet_name, classification, confidence,
    # rank_score, header_row, data_rows, reasoning.
    sheet_manifest: list[dict[str, Any]] = Field(
        default_factory=list
    )

    # Data table of the selected sheet with cleaned source headers.
    # Index = 1-based Excel row number.
    data_table: Any = None

    # 0-based worksheet row of the detected header.
    header_row: Optional[int] = None

    # Agent 2 mappings: source_header, target_field, score, method, reason.
    schema_mappings: list[Any] = Field(
        default_factory=list
    )

    # ------------------------------------------------------------------
    # Agent 3 -> human review -> Agent 4
    # ------------------------------------------------------------------

    # Mapped data under the 17 target field names (a copy; never mutated).
    canonical_data: Any = None

    # target field -> source header, for the audit log.
    source_columns: dict[str, str] = Field(
        default_factory=dict
    )

    # QualityReport (typed as Any to keep the state module free of
    # agent imports).
    quality_report: Any = None

    # ReviewLedger: recommendations, human decisions, reasoning history.
    review_ledger: Any = None

    agent3_fingerprint: Optional[str] = None

    # Agent hand-offs, for workflow visualisation.
    agent_trace: list[dict[str, Any]] = Field(
        default_factory=list
    )