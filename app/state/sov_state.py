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