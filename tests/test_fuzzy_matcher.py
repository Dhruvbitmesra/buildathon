from app.agents.schema_mapping.fuzzy_matcher import (
    FUZZY_CANDIDATES,
    FUZZY_THRESHOLD,
    fuzzy_match_header,
    fuzzy_match_headers,
)


def test_fuzzy_threshold():
    assert FUZZY_THRESHOLD == 0.75


def test_fuzzy_candidates_are_available():
    assert "building value" in FUZZY_CANDIDATES
    assert "bldg value" in FUZZY_CANDIDATES


def test_close_header_is_matched():
    result = fuzzy_match_header("Building Values")

    assert result.matched_field == "Building Value"
    assert result.match_method == "fuzzy"
    assert result.confidence >= 0.75
    assert result.deterministic is True


def test_typo_can_be_matched():
    result = fuzzy_match_header("Bulding Value")

    assert result.matched_field == "Building Value"
    assert result.confidence >= 0.75


def test_fuzzy_matching_handles_case():
    result = fuzzy_match_header("BUILDING VALUES")

    assert result.matched_field == "Building Value"


def test_low_similarity_remains_unresolved():
    result = fuzzy_match_header(
        "completely unrelated xyz column"
    )

    assert result.matched_field is None
    assert result.match_method is None


def test_empty_header_is_unresolved():
    result = fuzzy_match_header("")

    assert result.matched_field is None
    assert result.confidence == 0.0


def test_none_header_is_unresolved():
    result = fuzzy_match_header(None)

    assert result.matched_field is None
    assert result.confidence == 0.0


def test_assigned_field_is_excluded():
    result = fuzzy_match_header(
        "Building Values",
        assigned_fields={"Building Value"},
    )

    assert result.matched_field != "Building Value"


def test_confidence_is_between_zero_and_one():
    result = fuzzy_match_header("Building Values")

    assert 0.0 <= result.confidence <= 1.0


def test_similarity_score_is_between_zero_and_hundred():
    result = fuzzy_match_header("Building Values")

    assert 0.0 <= result.similarity_score <= 100.0


def test_multiple_headers_respect_one_to_one_assignment():
    results = fuzzy_match_headers(
        [
            "Building Values",
            "Building Valuess",
        ]
    )

    matched_fields = [
        result.matched_field
        for result in results
        if result.matched_field is not None
    ]

    assert len(matched_fields) == len(set(matched_fields))


def test_fire_sprinkler_fuzzy_match():
    result = fuzzy_match_header(
        "Fire Sprinkler Protection"
    )

    assert result.matched_field == "Fire Sprinklers (Y/N)"
    assert result.confidence >= 0.75


def test_generic_building_is_not_mapped_to_number_of_buildings():
    result = fuzzy_match_header("Building")

    assert not (
        result.matched_field == "Number of Buildings"
        and result.deterministic
        and result.confidence >= 0.75
    )


def test_number_of_buildings_still_matches():
    result = fuzzy_match_header("Number of Buildings")

    assert result.matched_field == "Number of Buildings"
    assert result.deterministic
    assert result.confidence >= 0.75


def test_building_count_still_matches_number_of_buildings():
    result = fuzzy_match_header("Building Count")

    assert result.matched_field == "Number of Buildings"
    assert result.deterministic
    assert result.confidence >= 0.75


def test_building_value_still_matches_building_value():
    result = fuzzy_match_header("Building Value")

    assert result.matched_field == "Building Value"
    assert result.deterministic
    assert result.confidence >= 0.75