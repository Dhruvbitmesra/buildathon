from typing import Optional

from pydantic import BaseModel
from rapidfuzz import fuzz, process

from app.agents.schema_mapping.domain_aliases import DOMAIN_ALIAS_LOOKUP
from app.agents.schema_mapping.header_normalizer import normalize_header
from app.agents.schema_mapping.target_schema import TARGET_FIELDS


FUZZY_THRESHOLD = 0.75


class FuzzyMatchResult(BaseModel):
    source_header: str
    normalized_header: str
    matched_field: Optional[str] = None
    matched_text: Optional[str] = None
    similarity_score: float = 0.0
    confidence: float = 0.0
    match_method: Optional[str] = None
    deterministic: bool = False


def build_fuzzy_candidates() -> dict[str, str]:
    """
    Build the searchable vocabulary for fuzzy matching.

    Each normalized canonical field name and approved domain alias
    points back to its canonical target field.
    """

    candidates: dict[str, str] = {}

    for field in TARGET_FIELDS:
        canonical = normalize_header(field.name)

        if canonical:
            candidates.setdefault(canonical, field.name)

        for alias in field.aliases:
            normalized_alias = normalize_header(alias)

            if normalized_alias:
                candidates.setdefault(
                    normalized_alias,
                    field.name,
                )

    for alias, target_field in DOMAIN_ALIAS_LOOKUP.items():
        candidates.setdefault(alias, target_field)

    return candidates


FUZZY_CANDIDATES = build_fuzzy_candidates()


def fuzzy_match_header(
    source_header: object,
    assigned_fields: Optional[set[str]] = None,
    threshold: float = FUZZY_THRESHOLD,
) -> FuzzyMatchResult:
    """
    Perform lexical fuzzy matching against canonical field names
    and approved aliases.

    A match is accepted only when its normalized confidence is
    greater than or equal to the configured threshold.
    """

    assigned_fields = assigned_fields or set()

    source_text = "" if source_header is None else str(source_header)
    normalized_header = normalize_header(source_header)

    result = FuzzyMatchResult(
        source_header=source_text,
        normalized_header=normalized_header,
    )

    if not normalized_header:
        return result

    choices = {
        text: target_field
        for text, target_field in FUZZY_CANDIDATES.items()
        if target_field not in assigned_fields
    }

    if not choices:
        return result

    best_match = process.extractOne(
        normalized_header,
        choices.keys(),
        scorer=fuzz.ratio,
    )

    if best_match is None:
        return result

    matched_text, score, _ = best_match

    confidence = float(score) / 100.0

    if confidence < threshold:
        return result.model_copy(
            update={
                "matched_text": matched_text,
                "similarity_score": float(score),
                "confidence": confidence,
            }
        )

    matched_field = choices[matched_text]

    return result.model_copy(
        update={
            "matched_field": matched_field,
            "matched_text": matched_text,
            "similarity_score": float(score),
            "confidence": confidence,
            "match_method": "fuzzy",
            "deterministic": True,
        }
    )


def fuzzy_match_headers(
    source_headers: list[str],
    assigned_fields: Optional[set[str]] = None,
    threshold: float = FUZZY_THRESHOLD,
) -> list[FuzzyMatchResult]:
    """
    Perform fuzzy matching across multiple source headers while
    enforcing one-to-one target assignment.
    """

    used_fields = set(assigned_fields or set())
    results: list[FuzzyMatchResult] = []

    for source_header in source_headers:
        result = fuzzy_match_header(
            source_header,
            assigned_fields=used_fields,
            threshold=threshold,
        )

        results.append(result)

        if result.matched_field is not None:
            used_fields.add(result.matched_field)

    return results