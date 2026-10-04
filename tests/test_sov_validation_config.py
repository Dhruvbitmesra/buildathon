from app.agents.data_quality.config import (
    SOV_ALLOWED_CATEGORIES,
    SOV_FIELD_RANGES,
    SOV_FIELD_TYPES,
    SOV_REQUIRED_FIELDS,
    SOV_UNIQUE_FIELDS,
    get_sov_validation_config,
)


def test_sov_has_17_required_fields():
    assert len(SOV_REQUIRED_FIELDS) == 17


def test_sov_field_types_cover_all_required_fields():
    assert set(SOV_FIELD_TYPES) == set(SOV_REQUIRED_FIELDS)


def test_sprinkler_allowed_values_are_exact():
    assert SOV_ALLOWED_CATEGORIES["Fire Sprinklers (Y/N)"] == {
        "Y",
        "N",
        "Y13",
        "Y(13R)",
    }


def test_storeys_has_minimum_one():
    assert SOV_FIELD_RANGES["Storeys"] == (1, None)


def test_number_of_buildings_has_minimum_one():
    assert SOV_FIELD_RANGES["Number of Buildings"] == (1, None)


def test_reference_is_unique():
    assert "Reference" in SOV_UNIQUE_FIELDS


def test_config_contains_all_validation_sections():
    config = get_sov_validation_config()

    expected_keys = {
        "required_fields",
        "field_types",
        "non_negative_fields",
        "allowed_categories",
        "field_ranges",
        "future_year_fields",
        "unique_fields",
    }

    assert set(config) == expected_keys