from typing import Optional

from pydantic import BaseModel

from app.agents.schema_mapping.header_normalizer import normalize_header
from app.agents.schema_mapping.target_schema import TARGET_FIELDS


class ExactMatchResult(BaseModel):
    source_header: str
    normalized_header: str
    matched_field: Optional[str] = None
    match_method: Optional[str] = None
    confidence: float = 0.0
    deterministic: bool = False


def build_exact_lookup() -> dict[str, str]:
    """
    Build a normalized lookup table containing canonical target
    field names and approved aliases.

    The lookup maps:

        normalized source/header form -> canonical target field name
    """

    lookup: dict[str, str] = {}

    for field in TARGET_FIELDS:
        canonical_key = normalize_header(field.name)

        if canonical_key:
            lookup.setdefault(canonical_key, field.name)

        for alias in field.aliases:
            alias_key = normalize_header(alias)

            if alias_key:
                lookup.setdefault(alias_key, field.name)

    return lookup


EXACT_LOOKUP = build_exact_lookup()


def exact_match_header(
    source_header: object,
    assigned_fields: Optional[set[str]] = None,
) -> ExactMatchResult:
    """
    Attempt deterministic exact matching for a source SOV header.

    Matching is performed only against normalized canonical names
    and approved aliases.

    No fuzzy matching, embeddings, or LLM reasoning is performed.
    """

    assigned_fields = assigned_fields or set()

    normalized_header = normalize_header(source_header)

    result = ExactMatchResult(
        source_header="" if source_header is None else str(source_header),
        normalized_header=normalized_header,
    )

    if not normalized_header:
        return result

    matched_field = EXACT_LOOKUP.get(normalized_header)

    if matched_field is None:
        return result

    if matched_field in assigned_fields:
        return result.model_copy(
            update={
                "match_method": "exact_conflict",
            }
        )

    return result.model_copy(
        update={
            "matched_field": matched_field,
            "match_method": "exact",
            "confidence": 1.0,
            "deterministic": True,
        }
    )


def exact_match_headers(
    source_headers: list[str],
) -> list[ExactMatchResult]:
    """
    Match multiple source headers while enforcing one-to-one
    deterministic assignment.
    """

    results: list[ExactMatchResult] = []
    assigned_fields: set[str] = set()

    for source_header in source_headers:
        result = exact_match_header(
            source_header,
            assigned_fields=assigned_fields,
        )

        results.append(result)

        if result.matched_field is not None:
            assigned_fields.add(result.matched_field)

    return results