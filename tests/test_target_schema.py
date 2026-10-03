from app.agents.schema_mapping.target_schema import (
    TARGET_FIELDS,
    TARGET_FIELD_BY_NAME,
    TARGET_FIELD_NAMES,
)


EXPECTED_FIELDS = (
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
)


def test_target_field_count():
    assert len(TARGET_FIELDS) == 17


def test_target_field_names():
    assert TARGET_FIELD_NAMES == EXPECTED_FIELDS


def test_target_field_names_are_unique():
    assert len(TARGET_FIELD_NAMES) == len(set(TARGET_FIELD_NAMES))


def test_all_expected_fields_exist():
    for field_name in EXPECTED_FIELDS:
        assert field_name in TARGET_FIELD_BY_NAME


def test_fire_sprinkler_allowed_values():
    field = TARGET_FIELD_BY_NAME["Fire Sprinklers (Y/N)"]

    assert field.data_type == "string"
    assert field.allowed_values == [
        "Y",
        "N",
        "Y13",
        "Y(13R)",
    ]


def test_numeric_field_types():
    expected_integer_fields = {
        "Zip",
        "Storeys",
        "Number of Buildings",
        "Year Built",
    }

    expected_float_fields = {
        "Building Value",
        "Contents",
        "BI",
        "Other",
    }

    for field_name in expected_integer_fields:
        assert TARGET_FIELD_BY_NAME[field_name].data_type == "integer"

    for field_name in expected_float_fields:
        assert TARGET_FIELD_BY_NAME[field_name].data_type == "float"


def test_string_fields():
    expected_string_fields = {
        "Reference",
        "Address",
        "City",
        "State",
        "County",
        "Country",
        "Occupancy",
        "Construction",
        "Fire Sprinklers (Y/N)",
    }

    for field_name in expected_string_fields:
        assert TARGET_FIELD_BY_NAME[field_name].data_type == "string"


def test_every_field_has_description():
    for field in TARGET_FIELDS:
        assert field.description.strip()


def test_every_field_has_aliases():
    for field in TARGET_FIELDS:
        assert len(field.aliases) > 0