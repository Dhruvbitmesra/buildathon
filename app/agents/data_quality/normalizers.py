"""
Deterministic value normalizers shared by Agent 3 and Agent 4.

Agent 3 calls propose() to build the before/after preview of a
recommendation. Agent 4 calls apply_operation() with the approved
operation and parameters. Because both sides use the same functions,
the preview shown to the reviewer is exactly what gets applied.

Every function here is pure: it never mutates its input and never
invents a value. When a value cannot be converted safely, the
functions return None and the caller must fall back to human review.
"""

import numbers
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Any, Iterable

import numpy as np
import pandas as pd

from app.agents.data_quality.us_reference import (
    AP_STATE_ABBREVIATIONS,
    STATE_CODES,
    STATE_NAME_TO_CODE,
    US_COUNTRY_ALIASES,
)


class Operation(str, Enum):
    """Closed list of operations Agent 3 may recommend."""

    PARSE_MONETARY = "parse_monetary"
    PARSE_INTEGER = "parse_integer"
    EXTRACT_YEAR = "extract_year"
    PAD_ZIP = "pad_zip"
    STANDARDISE_STATE = "standardise_state"
    CANONICALIZE_SPRINKLER = "canonicalize_sprinkler"
    TRIM_WHITESPACE = "trim_whitespace"
    SET_BLANK = "set_blank"
    SET_VALUE = "set_value"
    RENAME_COLUMN = "rename_column"
    KEEP = "keep"


# Operations that change a cell value.
VALUE_CHANGING_OPERATIONS = {
    Operation.PARSE_MONETARY,
    Operation.PARSE_INTEGER,
    Operation.EXTRACT_YEAR,
    Operation.PAD_ZIP,
    Operation.STANDARDISE_STATE,
    Operation.CANONICALIZE_SPRINKLER,
    Operation.TRIM_WHITESPACE,
    Operation.SET_BLANK,
    Operation.SET_VALUE,
}


# Operations that only change representation, never meaning.
LOSSLESS_OPERATIONS = {
    Operation.PARSE_MONETARY,
    Operation.PARSE_INTEGER,
    Operation.EXTRACT_YEAR,
    Operation.STANDARDISE_STATE,
    Operation.TRIM_WHITESPACE,
    Operation.RENAME_COLUMN,
}


MONETARY_FIELDS = {"Building Value", "Contents", "BI", "Other"}
INTEGER_FIELDS = {"Storeys", "Number of Buildings"}
TEXT_FIELDS = {
    "Reference",
    "Address",
    "City",
    "County",
    "Country",
    "Occupancy",
    "Construction",
}
SPRINKLER_FIELD = "Fire Sprinklers (Y/N)"
CANONICAL_SPRINKLER_VALUES = ("Y", "N", "Y13", "Y(13R)")

SPRINKLER_ALIASES = {
    "YES": "Y",
    "NO": "N",
    "SPRINKLERED": "Y",
    "NOT SPRINKLERED": "N",
    "13R": "Y(13R)",
    "Y 13": "Y13",
    "Y (13R)": "Y(13R)",
}

# Values clients use to mean "year unknown".
YEAR_PLACEHOLDERS = {0, 9999, 9998, 99999}

# Amount after currency symbols/codes, sign and brackets are removed.
#   US / UK:        1,200,000.50   1200000   .5
#   European:       1.200.000,50   1.200,5   (dots group, comma decimal)
#   Space grouped:  1 200 000
# A bare "1.234" stays a decimal: one dot group is ambiguous.
_AMOUNT_RE = re.compile(
    r"^(?P<number>"
    r"\d{1,3}(?:,\d{3})+(?:\.\d+)?"
    r"|\d{1,3}(?:\.\d{3})+,\d+"
    r"|\d{1,3}(?:\.\d{3}){2,}"
    r"|\d{1,3}(?: \d{3})+(?:[.,]\d+)?"
    r"|\d+(?:\.\d+)?"
    r"|\d+,\d{1,2}"
    r"|\.\d+"
    r")\s*(?P<suffix>k|m|b|thousand|million|mil|billion|bn)?$",
    re.IGNORECASE,
)
_CURRENCY_RE = re.compile(r"^(usd|eur|gbp|us\$|[$€£])\s*|\s*(usd|eur|gbp|[$€£])$", re.IGNORECASE)
_SUFFIX_MULTIPLIER = {
    "K": 1_000,
    "THOUSAND": 1_000,
    "M": 1_000_000,
    "MIL": 1_000_000,
    "MILLION": 1_000_000,
    "B": 1_000_000_000,
    "BN": 1_000_000_000,
    "BILLION": 1_000_000_000,
}
_ISO_DATE_RE = re.compile(r"^\s*(\d{4})-\d{1,2}-\d{1,2}(?:[ T].*)?$")
_US_DATE_RE = re.compile(r"^\s*\d{1,2}[/-]\d{1,2}[/-](\d{4})\s*$")


@dataclass(frozen=True)
class Proposal:
    """A deterministic proposal for changing one cell."""

    operation: Operation
    after_value: Any
    confidence: float
    reason: str
    params: dict[str, Any] = field(default_factory=dict)

    # True when only the representation changes, never the meaning.
    # Defaults from the operation; sprinkler synonyms set it explicitly.
    lossless: bool | None = None

    def __post_init__(self) -> None:
        if self.lossless is None:
            object.__setattr__(
                self,
                "lossless",
                self.operation in LOSSLESS_OPERATIONS,
            )


@dataclass(frozen=True)
class ApplyResult:
    ok: bool
    value: Any = None
    error: str | None = None


# ---------------------------------------------------------------------
# Primitive parsers
# ---------------------------------------------------------------------


def is_missing(value: Any) -> bool:
    if value is None:
        return True

    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def is_number(value: Any) -> bool:
    """True for Python and numpy real numbers, excluding booleans."""

    return isinstance(value, numbers.Real) and not isinstance(
        value, (bool, np.bool_)
    )


def parse_monetary(value: Any) -> float | None:
    """
    Parse an insured amount written in a common spreadsheet form:
    1200000, "$1,200,000", "1.2M", "750K", "USD 1.2 million",
    "EUR 1.200.000,50", "1 200 000", "(500)" (accounting negative).
    Returns None when the text is not unambiguously an amount.
    """

    if is_number(value):
        return float(value)

    if not isinstance(value, str):
        return None

    text = value.strip()
    negative = False

    if text.startswith("(") and text.endswith(")"):
        negative, text = True, text[1:-1].strip()

    if text.startswith("-"):
        negative, text = True, text[1:].strip()

    # Currency may sit before or after the sign: "-$500", "$-500".
    for _ in range(2):
        text = _CURRENCY_RE.sub("", text).strip()

        if text.startswith("-"):
            negative, text = True, text[1:].strip()

    match = _AMOUNT_RE.fullmatch(text)

    if match is None:
        return None

    number_text = match.group("number")

    if "," in number_text and "." in number_text and number_text.rfind(",") > number_text.rfind("."):
        # European: dots group thousands, comma is the decimal mark.
        number_text = number_text.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(?:\.\d{3}){2,}", number_text):
        number_text = number_text.replace(".", "")
    elif re.fullmatch(r"\d+,\d{1,2}", number_text):
        number_text = number_text.replace(",", ".")
    else:
        number_text = number_text.replace(",", "")

    number = float(number_text.replace(" ", ""))
    suffix = (match.group("suffix") or "").upper()
    number *= _SUFFIX_MULTIPLIER.get(suffix, 1)

    return round(-number if negative else number, 2)


def parse_whole_int(value: Any) -> int | None:
    """Parse 3, 3.0, '3', '3.0', '1,200' into an int; reject 2.5."""

    if is_number(value):
        return int(value) if float(value).is_integer() else None

    if not isinstance(value, str):
        return None

    text = value.strip().replace(",", "")

    try:
        number = float(text)
    except ValueError:
        return None

    return int(number) if number.is_integer() else None


def extract_year(value: Any) -> int | None:
    """Extract the year from a date, timestamp or date-like string."""

    if isinstance(value, (datetime, date, pd.Timestamp)):
        return int(value.year)

    if not isinstance(value, str):
        return None

    for pattern in (_ISO_DATE_RE, _US_DATE_RE):
        match = pattern.match(value)

        if match:
            return int(match.group(1))

    return None


def is_us_country(country: Any) -> bool:
    """Blank country is treated as US because the target schema is US-centric."""

    if is_missing(country):
        return True

    return str(country).strip().lower() in US_COUNTRY_ALIASES


def zip_digits(value: Any) -> str | None:
    """
    Return the ZIP as a digit string without changing its meaning.

    Whole-number floats such as 75219.0 (how Excel stores ZIPs) become
    '75219'. ZIP+4 strings are returned unchanged.
    """

    if is_number(value):
        if not float(value).is_integer() or value < 0:
            return None

        return str(int(value))

    if isinstance(value, str):
        text = value.strip()

        if text.endswith(".0") and text[:-2].isdigit():
            text = text[:-2]

        return text

    return None


def pad_zip(value: Any) -> str | None:
    """Restore leading zeros lost by Excel: 802 -> '00802', '2108' -> '02108'."""

    digits = zip_digits(value)

    if digits is None or not digits.isdigit():
        return None

    if 3 <= len(digits) <= 4:
        return digits.zfill(5)

    if 7 <= len(digits) <= 8:
        return digits.zfill(9)

    return None


def standardise_state(value: Any) -> str | None:
    """Return the 2-letter code for a state code, name or AP abbreviation."""

    if not isinstance(value, str):
        return None

    text = " ".join(value.strip().split())

    if not text:
        return None

    if text.upper() in STATE_CODES:
        return text.upper()

    lowered = text.lower()

    if lowered in STATE_NAME_TO_CODE:
        return STATE_NAME_TO_CODE[lowered]

    compact = lowered.replace(".", "").replace(" ", "")

    if compact.upper() in STATE_CODES:
        return compact.upper()

    return AP_STATE_ABBREVIATIONS.get(compact)


def sprinkler_number(value: Any) -> float | None:
    if is_number(value):
        return float(value)

    if isinstance(value, str):
        text = value.strip().rstrip("%").strip()

        try:
            return float(text)
        except ValueError:
            return None

    return None


def infer_sprinkler_scale(values: Iterable[Any]) -> float | None:
    """
    Decide whether a numeric sprinkler column is a fraction (0-1) or a
    percentage (0-100). Returns None when the column has no numbers or
    the numbers do not look like a percentage.
    """

    numbers = [
        number
        for number in (sprinkler_number(value) for value in values)
        if number is not None
    ]

    if not numbers or min(numbers) < 0:
        return None

    if max(numbers) <= 1:
        return 1.0

    if max(numbers) <= 100:
        return 100.0

    return None


def canonical_sprinkler(value: Any, scale: float | None = None) -> str | None:
    """
    Map a sprinkler value to Y / N / Y13 / Y(13R).

    Numeric values are interpreted as a sprinklered percentage using the
    column-level scale: 0 -> N, full coverage -> Y. Partial coverage
    returns None because neither Y nor N is a safe answer.
    """

    number = sprinkler_number(value)

    if number is not None:
        if scale is None:
            return None

        if number == 0:
            return "N"

        if number == scale:
            return "Y"

        return None

    if not isinstance(value, str):
        return None

    text = " ".join(value.strip().upper().split())

    if text in CANONICAL_SPRINKLER_VALUES:
        return text

    return SPRINKLER_ALIASES.get(text)


def trim_whitespace(value: Any) -> str | None:
    if not isinstance(value, str):
        return None

    return " ".join(value.split())


# ---------------------------------------------------------------------
# Proposal (Agent 3) and application (Agent 4)
# ---------------------------------------------------------------------


def propose(
    field_name: str,
    value: Any,
    context: dict[str, Any] | None = None,
) -> Proposal | None:
    """
    Propose a deterministic change for one cell, or None when no safe
    change exists. Missing values never get a proposal.

    context keys:
        is_us            -- bool, whether the row's country is the US
        sprinkler_scale  -- float | None, from infer_sprinkler_scale()
    """

    context = context or {}

    if is_missing(value):
        return None

    if field_name in MONETARY_FIELDS:
        if isinstance(value, str):
            parsed = parse_monetary(value)

            if parsed is not None:
                return Proposal(
                    Operation.PARSE_MONETARY,
                    parsed,
                    0.97,
                    "Text with currency symbols, thousands separators or "
                    "K/M/B suffixes converts to an exact number.",
                )

        return None

    if field_name in INTEGER_FIELDS:
        if isinstance(value, str):
            parsed = parse_whole_int(value)

            if parsed is not None:
                return Proposal(
                    Operation.PARSE_INTEGER,
                    parsed,
                    0.97,
                    "Numeric text converts to a whole number without "
                    "changing its value.",
                )

        return None

    if field_name == "Year Built":
        number = parse_whole_int(value) if not isinstance(
            value, (datetime, date)
        ) else None

        if number is not None and number in YEAR_PLACEHOLDERS:
            return Proposal(
                Operation.SET_BLANK,
                None,
                0.80,
                f"{number} is a common placeholder for an unknown year; "
                "the cell would be left blank rather than guessed.",
            )

        year = extract_year(value)

        if year is not None:
            return Proposal(
                Operation.EXTRACT_YEAR,
                year,
                0.95,
                "The cell holds a full date; Year Built only needs its year.",
            )

        if isinstance(value, str) and number is not None:
            return Proposal(
                Operation.PARSE_INTEGER,
                number,
                0.97,
                "Numeric text converts to a whole-number year.",
            )

        return None

    if field_name == "Zip":
        if not context.get("is_us", True):
            return None

        padded = pad_zip(value)

        if padded is not None:
            return Proposal(
                Operation.PAD_ZIP,
                padded,
                0.85,
                "The ZIP has fewer digits than a US ZIP. Spreadsheets drop "
                "leading zeros from numeric ZIPs, so the zeros are restored.",
            )

        return None

    if field_name == "State":
        if not context.get("is_us", True):
            return None

        code = standardise_state(value)

        if code is not None and code != value:
            return Proposal(
                Operation.STANDARDISE_STATE,
                code,
                0.97,
                "The state is recognised but not written as the preferred "
                "2-letter abbreviation.",
            )

        return None

    if field_name == SPRINKLER_FIELD:
        scale = context.get("sprinkler_scale")
        canonical = canonical_sprinkler(value, scale)

        if canonical is None or canonical == value:
            return None

        number = sprinkler_number(value)

        if number is not None:
            return Proposal(
                Operation.CANONICALIZE_SPRINKLER,
                canonical,
                0.90 if canonical == "N" else 0.85,
                f"The column stores sprinklered coverage as a number "
                f"(scale 0-{scale:g}); {value} means "
                f"{'no' if canonical == 'N' else 'full'} sprinkler coverage.",
                params={"scale": scale},
            )

        upper = " ".join(str(value).strip().upper().split())
        case_only = upper == canonical

        return Proposal(
            Operation.CANONICALIZE_SPRINKLER,
            canonical,
            0.98 if case_only else 0.95,
            "The value differs from the canonical code only in letter case."
            if case_only
            else f"'{value}' is a recognised synonym of the canonical "
            f"sprinkler code '{canonical}'.",
            lossless=True,
        )

    if field_name in TEXT_FIELDS:
        trimmed = trim_whitespace(value)

        if trimmed is not None and trimmed and trimmed != value:
            return Proposal(
                Operation.TRIM_WHITESPACE,
                trimmed,
                0.99,
                "The text has leading, trailing or repeated spaces.",
            )

    return None


def apply_operation(
    operation: Operation,
    value: Any,
    params: dict[str, Any] | None = None,
) -> ApplyResult:
    """Apply an approved operation to one cell value."""

    params = params or {}
    operation = Operation(operation)

    if operation in {Operation.KEEP, Operation.RENAME_COLUMN}:
        return ApplyResult(True, value)

    if operation == Operation.SET_BLANK:
        return ApplyResult(True, None)

    if operation == Operation.SET_VALUE:
        if "value" not in params:
            return ApplyResult(False, error="set_value requires params['value']")

        return ApplyResult(True, params["value"])

    if is_missing(value):
        return ApplyResult(True, None)

    converters = {
        Operation.PARSE_MONETARY: parse_monetary,
        Operation.PARSE_INTEGER: parse_whole_int,
        Operation.EXTRACT_YEAR: lambda v: extract_year(v)
        if extract_year(v) is not None
        else parse_whole_int(v),
        Operation.PAD_ZIP: pad_zip,
        Operation.STANDARDISE_STATE: standardise_state,
        Operation.CANONICALIZE_SPRINKLER: lambda v: canonical_sprinkler(
            v, params.get("scale")
        ),
        Operation.TRIM_WHITESPACE: trim_whitespace,
    }

    result = converters[operation](value)

    if result is None:
        return ApplyResult(
            False,
            error=f"{operation.value} cannot convert {value!r} safely",
        )

    return ApplyResult(True, result)


def allowed_operations_for(field_name: str | None) -> set[Operation]:
    """Operations that make sense for a field (LLM guardrail)."""

    base = {Operation.KEEP, Operation.SET_BLANK, Operation.SET_VALUE}

    if field_name in MONETARY_FIELDS:
        return base | {Operation.PARSE_MONETARY}

    if field_name in INTEGER_FIELDS:
        return base | {Operation.PARSE_INTEGER}

    if field_name == "Year Built":
        return base | {Operation.PARSE_INTEGER, Operation.EXTRACT_YEAR}

    if field_name == "Zip":
        return base | {Operation.PAD_ZIP}

    if field_name == "State":
        return base | {Operation.STANDARDISE_STATE}

    if field_name == SPRINKLER_FIELD:
        return base | {Operation.CANONICALIZE_SPRINKLER}

    if field_name in TEXT_FIELDS:
        return base | {Operation.TRIM_WHITESPACE}

    return base
