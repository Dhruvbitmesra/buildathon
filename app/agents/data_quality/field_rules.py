from typing import Any


FIELD_RULES: dict[str, dict[str, Any]] = {
    "Reference": {
        "kind": "identifier",
        "required": True,
    },
    "Address": {
        "kind": "text",
        "required": True,
    },
    "City": {
        "kind": "text",
        "required": True,
        "reject_numeric_only": True,
    },
    "State": {
        "kind": "state",
        "required": True,
        "reject_numeric_only": True,
    },
    "Zip": {
        "kind": "zip",
        "required": True,
        "integer": True,
        "non_negative": True,
    },
    "County": {
        "kind": "text",
        "required": False,
        "reject_numeric_only": True,
    },
    "Country": {
        "kind": "text",
        "required": True,
    },
    "Building Value": {
        "kind": "monetary",
        "required": True,
        "non_negative": True,
    },
    "Contents": {
        "kind": "monetary",
        "required": True,
        "non_negative": True,
    },
    "BI": {
        "kind": "monetary",
        "required": True,
        "non_negative": True,
    },
    "Occupancy": {
        "kind": "text",
        "required": False,
        "reject_numeric_only": True,
    },
    "Construction": {
        "kind": "text",
        "required": False,
        "reject_numeric_only": True,
    },
    "Storeys": {
        "kind": "positive_integer",
        "required": True,
        "minimum": 1,
    },
    "Number of Buildings": {
        "kind": "positive_integer",
        "required": True,
        "minimum": 1,
    },
    "Year Built": {
        "kind": "year",
        "required": False,
        "minimum": 0,
        "not_future": True,
    },
    "Fire Sprinklers (Y/N)": {
        "kind": "categorical",
        "required": False,
        "allowed_values": {
            "Y",
            "N",
            "Y13",
            "Y(13R)",
        },
    },
    "Other": {
        "kind": "monetary",
        "required": False,
        "non_negative": True,
    },
}