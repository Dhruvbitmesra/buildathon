from typing import Callable

from pydantic import BaseModel, Field

from app.state.sov_state import ColumnProfile


class FieldEvidence(BaseModel):
    target_field: str
    score: float = 0.0
    components: dict[str, float] = Field(default_factory=dict)
    reasons: list[str] = Field(default_factory=list)


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _numeric_score(profile: ColumnProfile) -> float:
    return _clamp(profile.numeric_ratio)


def _string_score(profile: ColumnProfile) -> float:
    return _clamp(profile.string_ratio)


def _uniqueness_score(profile: ColumnProfile) -> float:
    return _clamp(profile.unique_ratio)


def _categorical_score(profile: ColumnProfile) -> float:
    """
    Repeated categorical values are useful evidence for fields such as
    Occupancy and Construction.

    A unique ratio near 0 means many repeated values.
    A unique ratio near 1 means almost every value is unique.
    """
    return _clamp(1.0 - profile.unique_ratio)


def _currency_score(profile: ColumnProfile) -> float:
    return _clamp(
        profile.patterns.get("currency_like_ratio", 0.0)
    )


def _year_score(profile: ColumnProfile) -> float:
    return _clamp(
        profile.patterns.get("year_like_ratio", 0.0)
    )


def _boolean_score(profile: ColumnProfile) -> float:
    return _clamp(
        profile.patterns.get("boolean_like_ratio", 0.0)
    )


def _sprinkler_score(profile: ColumnProfile) -> float:
    return _clamp(
        profile.patterns.get("sprinkler_like_ratio", 0.0)
    )


def _zip_score(profile: ColumnProfile) -> float:
    return _clamp(
        profile.patterns.get("zip_like_ratio", 0.0)
    )


def _small_integer_score(profile: ColumnProfile) -> float:
    """
    Evidence for fields such as Storeys and Number of Buildings.

    A column is considered compatible when it is predominantly numeric
    and its observed values are small non-negative integers.
    """

    numeric_ratio = profile.numeric_ratio

    if numeric_ratio == 0.0:
        return 0.0

    if (
        profile.min_value is None
        or profile.max_value is None
    ):
        return numeric_ratio

    values_are_small = (
        profile.min_value >= 0
        and profile.max_value <= 100
    )

    if values_are_small:
        return _clamp(numeric_ratio)

    return _clamp(numeric_ratio * 0.25)


def _add_reason(
    reasons: list[str],
    condition: bool,
    message: str,
) -> None:
    if condition:
        reasons.append(message)


def _money_evidence(
    profile: ColumnProfile,
) -> FieldEvidence:
    numeric = _numeric_score(profile)
    currency = _currency_score(profile)

    score = (
        0.60 * numeric
        + 0.40 * currency
    )

    reasons: list[str] = []

    _add_reason(
        reasons,
        numeric >= 0.75,
        "Column is predominantly numeric.",
    )

    _add_reason(
        reasons,
        currency >= 0.50,
        "Values show monetary/currency-like formatting.",
    )

    return FieldEvidence(
        target_field="",
        score=_clamp(score),
        components={
            "numeric_ratio": numeric,
            "currency_like_ratio": currency,
        },
        reasons=reasons,
    )


def _building_value_evidence(
    profile: ColumnProfile,
) -> FieldEvidence:
    evidence = _money_evidence(profile)
    evidence.target_field = "Building Value"
    return evidence


def _contents_evidence(
    profile: ColumnProfile,
) -> FieldEvidence:
    evidence = _money_evidence(profile)
    evidence.target_field = "Contents"
    return evidence


def _bi_evidence(
    profile: ColumnProfile,
) -> FieldEvidence:
    evidence = _money_evidence(profile)
    evidence.target_field = "BI"
    return evidence


def _other_evidence(
    profile: ColumnProfile,
) -> FieldEvidence:
    evidence = _money_evidence(profile)
    evidence.target_field = "Other"
    return evidence


def _zip_evidence(
    profile: ColumnProfile,
) -> FieldEvidence:
    zip_score = _zip_score(profile)
    numeric = _numeric_score(profile)

    score = (
        0.75 * zip_score
        + 0.25 * numeric
    )

    reasons: list[str] = []

    _add_reason(
        reasons,
        zip_score >= 0.75,
        "Values follow a ZIP/postal-code-like pattern.",
    )

    _add_reason(
        reasons,
        numeric >= 0.75,
        "Column is predominantly numeric.",
    )

    return FieldEvidence(
        target_field="Zip",
        score=_clamp(score),
        components={
            "zip_like_ratio": zip_score,
            "numeric_ratio": numeric,
        },
        reasons=reasons,
    )


def _year_built_evidence(
    profile: ColumnProfile,
) -> FieldEvidence:
    year = _year_score(profile)

    score = year

    reasons: list[str] = []

    _add_reason(
        reasons,
        year >= 0.75,
        "Values predominantly resemble construction years.",
    )

    return FieldEvidence(
        target_field="Year Built",
        score=_clamp(score),
        components={
            "year_like_ratio": year,
        },
        reasons=reasons,
    )


def _storeys_evidence(
    profile: ColumnProfile,
) -> FieldEvidence:
    numeric = _numeric_score(profile)
    small_integer = _small_integer_score(profile)

    score = (
        0.35 * numeric
        + 0.65 * small_integer
    )

    reasons: list[str] = []

    _add_reason(
        reasons,
        numeric >= 0.75,
        "Column is predominantly numeric.",
    )

    _add_reason(
        reasons,
        small_integer >= 0.75,
        "Values are consistent with small building/floor counts.",
    )

    return FieldEvidence(
        target_field="Storeys",
        score=_clamp(score),
        components={
            "numeric_ratio": numeric,
            "small_integer_score": small_integer,
        },
        reasons=reasons,
    )


def _number_of_buildings_evidence(
    profile: ColumnProfile,
) -> FieldEvidence:
    numeric = _numeric_score(profile)
    small_integer = _small_integer_score(profile)

    score = (
        0.35 * numeric
        + 0.65 * small_integer
    )

    reasons: list[str] = []

    _add_reason(
        reasons,
        numeric >= 0.75,
        "Column is predominantly numeric.",
    )

    _add_reason(
        reasons,
        small_integer >= 0.75,
        "Values are consistent with small building counts.",
    )

    return FieldEvidence(
        target_field="Number of Buildings",
        score=_clamp(score),
        components={
            "numeric_ratio": numeric,
            "small_integer_score": small_integer,
        },
        reasons=reasons,
    )


def _sprinkler_evidence(
    profile: ColumnProfile,
) -> FieldEvidence:
    sprinkler = _sprinkler_score(profile)
    boolean = _boolean_score(profile)

    score = sprinkler

    reasons: list[str] = []

    _add_reason(
        reasons,
        sprinkler >= 0.75,
        "Values match supported fire sprinkler codes.",
    )

    _add_reason(
        reasons,
        boolean >= 0.75,
        "Values are predominantly boolean-like.",
    )

    return FieldEvidence(
        target_field="Fire Sprinklers (Y/N)",
        score=_clamp(score),
        components={
            "sprinkler_like_ratio": sprinkler,
            "boolean_like_ratio": boolean,
        },
        reasons=reasons,
    )

def _reference_evidence(
    profile: ColumnProfile,
) -> FieldEvidence:
    uniqueness = _uniqueness_score(profile)
    string = _string_score(profile)

    score = (
        0.65 * uniqueness
        + 0.35 * string
    )

    reasons: list[str] = []

    _add_reason(
        reasons,
        uniqueness >= 0.75,
        "Values have high uniqueness, consistent with identifiers.",
    )

    _add_reason(
        reasons,
        string >= 0.50,
        "Values contain predominantly string-like data.",
    )

    return FieldEvidence(
        target_field="Reference",
        score=_clamp(score),
        components={
            "unique_ratio": uniqueness,
            "string_ratio": string,
        },
        reasons=reasons,
    )


def _address_evidence(
    profile: ColumnProfile,
) -> FieldEvidence:
    string = _string_score(profile)
    uniqueness = _uniqueness_score(profile)

    score = (
        0.55 * string
        + 0.45 * uniqueness
    )

    reasons: list[str] = []

    _add_reason(
        reasons,
        string >= 0.75,
        "Column is predominantly string-like.",
    )

    _add_reason(
        reasons,
        uniqueness >= 0.50,
        "Values have meaningful uniqueness, consistent with addresses.",
    )

    return FieldEvidence(
        target_field="Address",
        score=_clamp(score),
        components={
            "string_ratio": string,
            "unique_ratio": uniqueness,
        },
        reasons=reasons,
    )


def _location_string_evidence(
    profile: ColumnProfile,
    target_field: str,
) -> FieldEvidence:
    string = _string_score(profile)
    uniqueness = _uniqueness_score(profile)

    score = (
        0.65 * string
        + 0.35 * (1.0 - uniqueness)
    )

    reasons: list[str] = []

    _add_reason(
        reasons,
        string >= 0.75,
        "Column is predominantly string-like.",
    )

    _add_reason(
        reasons,
        uniqueness <= 0.50,
        "Values contain repetition consistent with geographic categories.",
    )

    return FieldEvidence(
        target_field=target_field,
        score=_clamp(score),
        components={
            "string_ratio": string,
            "categorical_repetition": 1.0 - uniqueness,
        },
        reasons=reasons,
    )


def _occupancy_evidence(
    profile: ColumnProfile,
) -> FieldEvidence:
    categorical = _categorical_score(profile)
    string = _string_score(profile)

    score = (
        0.60 * string
        + 0.40 * categorical
    )

    reasons: list[str] = []

    _add_reason(
        reasons,
        string >= 0.75,
        "Column is predominantly string-like.",
    )

    _add_reason(
        reasons,
        categorical >= 0.50,
        "Values contain repeated categories.",
    )

    return FieldEvidence(
        target_field="Occupancy",
        score=_clamp(score),
        components={
            "string_ratio": string,
            "categorical_score": categorical,
        },
        reasons=reasons,
    )


def _construction_evidence(
    profile: ColumnProfile,
) -> FieldEvidence:
    categorical = _categorical_score(profile)
    string = _string_score(profile)

    score = (
        0.60 * string
        + 0.40 * categorical
    )

    reasons: list[str] = []

    _add_reason(
        reasons,
        string >= 0.75,
        "Column is predominantly string-like.",
    )

    _add_reason(
        reasons,
        categorical >= 0.50,
        "Values contain repeated construction categories.",
    )

    return FieldEvidence(
        target_field="Construction",
        score=_clamp(score),
        components={
            "string_ratio": string,
            "categorical_score": categorical,
        },
        reasons=reasons,
    )


def _country_evidence(
    profile: ColumnProfile,
) -> FieldEvidence:
    return _location_string_evidence(
        profile,
        "Country",
    )


def _state_evidence(
    profile: ColumnProfile,
) -> FieldEvidence:
    return _location_string_evidence(
        profile,
        "State",
    )


def _city_evidence(
    profile: ColumnProfile,
) -> FieldEvidence:
    return _location_string_evidence(
        profile,
        "City",
    )


def _county_evidence(
    profile: ColumnProfile,
) -> FieldEvidence:
    return _location_string_evidence(
        profile,
        "County",
    )


FIELD_EVIDENCE_FUNCTIONS: dict[
    str,
    Callable[[ColumnProfile], FieldEvidence],
] = {
    "Reference": _reference_evidence,
    "Address": _address_evidence,
    "City": _city_evidence,
    "State": _state_evidence,
    "Zip": _zip_evidence,
    "County": _county_evidence,
    "Country": _country_evidence,
    "Building Value": _building_value_evidence,
    "Contents": _contents_evidence,
    "BI": _bi_evidence,
    "Occupancy": _occupancy_evidence,
    "Construction": _construction_evidence,
    "Storeys": _storeys_evidence,
    "Number of Buildings": _number_of_buildings_evidence,
    "Year Built": _year_built_evidence,
    "Fire Sprinklers (Y/N)": _sprinkler_evidence,
    "Other": _other_evidence,
}


def score_field_evidence(
    profile: ColumnProfile,
) -> list[FieldEvidence]:
    """
    Generate evidence scores for every canonical target field.

    This function does not choose a final target field.
    """

    results: list[FieldEvidence] = []

    for target_field, scorer in FIELD_EVIDENCE_FUNCTIONS.items():
        results.append(scorer(profile))

    return results


def rank_field_evidence(
    profile: ColumnProfile,
) -> list[FieldEvidence]:
    """
    Return field evidence ranked from highest to lowest score.
    """

    results = score_field_evidence(profile)

    return sorted(
        results,
        key=lambda result: result.score,
        reverse=True,
    )