"""
Domain-specific aliases for SOV schema mapping.

This module contains generic insurance/SOV terminology aliases for the
canonical target schema.

Important:
- Aliases must be domain-based, not dataset-specific.
- Every normalized alias must map to only one target field.
- Conflicts are detected during lookup construction.
"""

from __future__ import annotations

from app.agents.schema_mapping.target_schema import TARGET_FIELDS


# ============================================================================
# DOMAIN ALIASES
# ============================================================================

DOMAIN_ALIASES: dict[str, list[str]] = {

    # ------------------------------------------------------------------------
    # 1. Reference
    # ------------------------------------------------------------------------
    "Reference": [
        "ref",
        "ref no",
        "ref number",
        "reference no",
        "reference number",
        "reference id",
        "location reference",
        "location id",
        "location number",
        "loc number",
        "loc no",
        "loc id",
    ],

    # ------------------------------------------------------------------------
    # 2. Address
    # ------------------------------------------------------------------------
    "Address": [
        "address",
        "street address",
        "property address",
        "site address",
        "location address",
        "street",
        "street name",
        "address line",
        "address line 1",
        "address line 2",
        "addr",
    ],

    # ------------------------------------------------------------------------
    # 3. City
    # ------------------------------------------------------------------------
    "City": [
        "city",
        "city name",
        "town",
        "town name",
        "city town",
        "city / town",
        "municipality",
        "municipality name",
    ],

    # ------------------------------------------------------------------------
    # 4. State
    # ------------------------------------------------------------------------
    "State": [
        "state",
        "state name",
        "state code",
        "state abbreviation",
        "province",
        "province name",
        "state prov",
        "st",
    ],

    # ------------------------------------------------------------------------
    # 5. Zip
    # ------------------------------------------------------------------------
    "Zip": [
        "zip",
        "zip code",
        "zipcode",
        "postal code",
        "postal",
        "postcode",
        "post code",
        "zip number",
    ],

    # ------------------------------------------------------------------------
    # 6. County
    # ------------------------------------------------------------------------
    "County": [
        "county",
        "county name",
        "county code",
    ],

    # ------------------------------------------------------------------------
    # 7. Country
    # ------------------------------------------------------------------------
    "Country": [
        "country",
        "country name",
        "country code",
        "nation",
    ],

    # ------------------------------------------------------------------------
    # 8. Building Value
    # ------------------------------------------------------------------------
    #
    # NOTE:
    # Do NOT put building-count terminology here.
    #
    # "building count", "number of buildings", etc. belong exclusively to
    # Number of Buildings.
    # ------------------------------------------------------------------------
    "Building Value": [
        "bldg value",
        "building val",
        "bldg val",
        "building replacement value",
        "building replacement cost",
        "building repl cost",
        "bldg repl cost",
        "replacement cost",
        "replacement cost new",
        "repl cost",
        "repl cost new",
        "building cost",
        "bldg cost",
        "replacement value",
        "repl value",
        "property value",
        "property valuation",
        "building valuation",
        "building amount",
        "building limit",
        "building limit value",
    ],

    # ------------------------------------------------------------------------
    # 9. Contents
    # ------------------------------------------------------------------------
    "Contents": [
        "contents value",
        "contents val",
        "content value",
        "contents cost",
        "contents replacement value",
        "contents replacement cost",
        "machinery value",
        "equipment value",
        "machinery equipment",
        "machinery and equipment",
        "contents machinery equipment",
        "contents amount",
        "contents limit",
        "bpp",
        "business personal property",
        "business personal property value",
        "bpp value",
    ],

    # ------------------------------------------------------------------------
    # 10. BI
    # ------------------------------------------------------------------------
    "BI": [
        "business interruption",
        "business interruption value",
        "business income",
        "business income value",
        "bi value",
        "bi amount",
        "business income amount",
        "business interruption amount",
        "business interruption limit",
        "business income limit",
        "bi limit",
        "bi amount value",
    ],

    # ------------------------------------------------------------------------
    # 11. Occupancy
    # ------------------------------------------------------------------------
    "Occupancy": [
        "occupancy type",
        "property occupancy",
        "building occupancy",
        "occupancy class",
        "property use",
        "building use",
        "use type",
        "use",
        "occupancy description",
        "occupancy code",
        "occupancy classification",
    ],

    # ------------------------------------------------------------------------
    # 12. Construction
    # ------------------------------------------------------------------------
    "Construction": [
        "construction type",
        "construction class",
        "construction code",
        "building construction",
        "construction classification",
        "bldg construction",
        "construction description",
        "construction category",
        "construction material",
        "building construction type",
    ],

    # ------------------------------------------------------------------------
    # 13. Storeys
    # ------------------------------------------------------------------------
    "Storeys": [
        "stories",
        "story",
        "storey",
        "number of stories",
        "number of storeys",
        "number of floors",
        "floor count",
        "story count",
        "storey count",
        "of stories",
        "no of stories",
        "no of storeys",
        "floors",
        "floor number",
        "building floors",
    ],

    # ------------------------------------------------------------------------
    # 14. Number of Buildings
    # ------------------------------------------------------------------------
    #
    # These aliases are intentionally kept separate from Building Value.
    # ------------------------------------------------------------------------
    "Number of Buildings": [
        "building count",
        "number buildings",
        "number of building",
        "number of buildings",
        "no of buildings",
        "no buildings",
        "no of bldgs",
        "number of bldgs",
        "building number",
        "bldg count",
        "number buildings at location",
        "of buildings",
        "no of building",
        "bldgs count",
        "building quantity",
        "number of structures",
        "structure count",
    ],

    # ------------------------------------------------------------------------
    # 15. Year Built
    # ------------------------------------------------------------------------
    "Year Built": [
        "year of construction",
        "construction year",
        "year constructed",
        "built year",
        "year built",
        "built",
        "construction yr",
        "year constructed",
        "yr built",
        "built yr",
        "year",
    ],

    # ------------------------------------------------------------------------
    # 16. Fire Sprinklers (Y/N)
    # ------------------------------------------------------------------------
    "Fire Sprinklers (Y/N)": [
        "fire sprinklers",
        "fire sprinkler",
        "sprinklers",
        "sprinkler",
        "sprinklered",
        "sprinkler",
        "sprinkler system",
        "fire sprinkler system",
        "sprinkler protection",
        "sprinkler protection system",
        "sprinklered percentage",
        "sprinkler percentage",
        "sprinkler %",
        "percent sprinklered",
        "% sprinklered",
        "fire protection sprinkler",
    ],

    # ------------------------------------------------------------------------
    # 17. Other
    # ------------------------------------------------------------------------
    "Other": [
        "other",
        "other value",
        "other amount",
        "other property",
        "other property value",
        "other exposure",
        "other exposure value",
        "other limit",
        "other assets",
        "other asset value",
    ],
}


# ============================================================================
# NORMALIZATION
# ============================================================================

def _normalize_alias(value: str) -> str:
    """
    Normalize an alias using the same basic conventions used by the
    schema-mapping header normalization layer.

    Examples
    --------
    "No. of Buildings" -> "no of buildings"
    "Bldg. Count"      -> "bldg count"
    "Fire Sprinklers"  -> "fire sprinklers"
    """

    value = str(value).strip().lower()

    # Normalize common separators.
    value = value.replace("_", " ")
    value = value.replace("-", " ")

    # Remove common punctuation while preserving alphanumeric characters.
    cleaned_chars: list[str] = []

    for char in value:
        if char.isalnum() or char.isspace():
            cleaned_chars.append(char)
        else:
            cleaned_chars.append(" ")

    value = "".join(cleaned_chars)

    # Collapse repeated whitespace.
    value = " ".join(value.split())

    return value


# ============================================================================
# BUILD LOOKUP
# ============================================================================

def build_domain_alias_lookup() -> dict[str, str]:
    """
    Build:

        normalized_alias -> canonical_target_field

    Raises
    ------
    ValueError
        If the same normalized alias maps to multiple target fields.
    """

    lookup: dict[str, str] = {}

    # TARGET_FIELDS contains TargetField objects.
    # Use their canonical names for validation.
    valid_targets = {
        field.name
        for field in TARGET_FIELDS
    }

    for target_field, aliases in DOMAIN_ALIASES.items():

        if target_field not in valid_targets:
            raise ValueError(
                f"Unknown target field in DOMAIN_ALIASES: "
                f"'{target_field}'"
            )

        all_aliases = [
            target_field,
            *aliases,
        ]

        for alias in all_aliases:

            normalized_alias = _normalize_alias(alias)

            if not normalized_alias:
                continue

            existing_target = lookup.get(
                normalized_alias
            )

            if (
                existing_target is not None
                and existing_target != target_field
            ):
                raise ValueError(
                    "Domain alias conflict: "
                    f"'{normalized_alias}' maps to both "
                    f"'{existing_target}' and "
                    f"'{target_field}'."
                )

            lookup[normalized_alias] = target_field

    return lookup
# ============================================================================
# GLOBAL LOOKUP
# ============================================================================

DOMAIN_ALIAS_LOOKUP = build_domain_alias_lookup()


# ============================================================================
# PUBLIC HELPER
# ============================================================================

def domain_alias_match(
    source_header: str,
) -> str | None:
    """
    Return the canonical target field for a normalized domain alias.

    Parameters
    ----------
    source_header:
        Source workbook header.

    Returns
    -------
    str | None
        Canonical target field if a domain alias matches,
        otherwise None.
    """

    normalized = _normalize_alias(source_header)

    return DOMAIN_ALIAS_LOOKUP.get(
        normalized
    )


__all__ = [
    "DOMAIN_ALIASES",
    "DOMAIN_ALIAS_LOOKUP",
    "build_domain_alias_lookup",
    "domain_alias_match",
]