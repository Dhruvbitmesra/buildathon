from app.agents.schema_mapping.exact_matcher import (
    EXACT_LOOKUP,
    build_exact_lookup,
    exact_match_header,
    exact_match_headers,
)


def test_lookup_contains_canonical_fields():
    lookup = build_exact_lookup()

    assert lookup["building value"] == "Building Value"
    assert lookup["address"] == "Address"
    assert lookup["year built"] == "Year Built"


def test_lookup_contains_aliases():
    lookup = build_exact_lookup()

    assert lookup["bldg repl cost new"] == "Building Value"
    assert lookup["business interruption"] == "BI"
    assert lookup["stories"] == "Storeys"


def test_exact_canonical_match():
    result = exact_match_header("Building Value")

    assert result.matched_field == "Building Value"
    assert result.match_method == "exact"
    assert result.confidence == 1.0
    assert result.deterministic is True


def test_exact_alias_match():
    result = exact_match_header("Bldg Repl Cost New")

    assert result.matched_field == "Building Value"
    assert result.match_method == "exact"
    assert result.confidence == 1.0
    assert result.deterministic is True


def test_matching_is_case_insensitive():
    result = exact_match_header("BUILDING VALUE")

    assert result.matched_field == "Building Value"
    assert result.confidence == 1.0


def test_matching_handles_formatting():
    result = exact_match_header("  Building_Value  ")

    assert result.matched_field == "Building Value"
    assert result.match_method == "exact"


def test_fire_sprinkler_match():
    result = exact_match_header("Fire Sprinklers (Y/N)")

    assert result.matched_field == "Fire Sprinklers (Y/N)"
    assert result.match_method == "exact"
    assert result.confidence == 1.0


def test_unresolved_header():
    result = exact_match_header("Completely Unknown Column")

    assert result.matched_field is None
    assert result.match_method is None
    assert result.confidence == 0.0
    assert result.deterministic is False


def test_empty_header():
    result = exact_match_header("")

    assert result.matched_field is None
    assert result.confidence == 0.0


def test_none_header():
    result = exact_match_header(None)

    assert result.matched_field is None
    assert result.confidence == 0.0


def test_duplicate_target_is_not_assigned_twice():
    results = exact_match_headers(
        [
            "Building Value",
            "Bldg Repl Cost New",
        ]
    )

    assert results[0].matched_field == "Building Value"

    assert results[1].matched_field is None
    assert results[1].match_method == "exact_conflict"


def test_multiple_different_fields():
    results = exact_match_headers(
        [
            "Address",
            "City",
            "State",
            "Year Built",
        ]
    )

    assert [result.matched_field for result in results] == [
        "Address",
        "City",
        "State",
        "Year Built",
    ]


def test_exact_lookup_is_available():
    assert "building value" in EXACT_LOOKUP
    assert EXACT_LOOKUP["building value"] == "Building Value"