from typing import Any


SOV_REQUIRED_FIELDS = [
    "Reference",
    "Address",
    "City",
    "State",
    "Zip",
    "County",
    "Country",
    "Building Value",
    "Contents",
    "BI",
    "Occupancy",
    "Construction",
    "Storeys",
    "Number of Buildings",
    "Year Built",
    "Fire Sprinklers (Y/N)",
    "Other",
]


SOV_FIELD_TYPES: dict[str, type] = {
    "Reference": str,
    "Address": str,
    "City": str,
    "State": str,
    "Zip": str,
    "County": str,
    "Country": str,
    "Building Value": float,
    "Contents": float,
    "BI": float,
    "Occupancy": str,
    "Construction": str,
    "Storeys": int,
    "Number of Buildings": int,
    "Year Built": int,
    "Fire Sprinklers (Y/N)": str,
    "Other": float,
}


SOV_NON_NEGATIVE_FIELDS = {
    "Building Value",
    "Contents",
    "BI",
    "Storeys",
    "Number of Buildings",
    "Other",
}


SOV_ALLOWED_CATEGORIES: dict[str, set[Any]] = {
    "Fire Sprinklers (Y/N)": {
        "Y",
        "N",
        "Y13",
        "Y(13R)",
    }
}


SOV_FIELD_RANGES: dict[str, tuple[float | None, float | None]] = {
    "Storeys": (1, None),
    "Number of Buildings": (1, None),
    "Year Built": (0, None),
}


SOV_FUTURE_YEAR_FIELDS = {
    "Year Built",
}


SOV_UNIQUE_FIELDS = {
    "Reference",
}


def get_sov_validation_config() -> dict[str, Any]:
    """
    Return the complete deterministic validation configuration
    for the canonical SOV schema.
    """

    return {
        "required_fields": list(SOV_REQUIRED_FIELDS),
        "field_types": dict(SOV_FIELD_TYPES),
        "non_negative_fields": set(SOV_NON_NEGATIVE_FIELDS),
        "allowed_categories": {
            field: set(values)
            for field, values in SOV_ALLOWED_CATEGORIES.items()
        },
        "field_ranges": dict(SOV_FIELD_RANGES),
        "future_year_fields": set(SOV_FUTURE_YEAR_FIELDS),
        "unique_fields": set(SOV_UNIQUE_FIELDS),
    }