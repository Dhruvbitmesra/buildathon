from app.agents.data_quality.field_rules import FIELD_RULES


EXPECTED_FIELDS = {
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
}


def test_field_rules_cover_all_sov_fields():
    assert set(FIELD_RULES) == EXPECTED_FIELDS


def test_storeys_is_positive_integer():
    rule = FIELD_RULES["Storeys"]

    assert rule["kind"] == "positive_integer"
    assert rule["minimum"] == 1


def test_number_of_buildings_is_positive_integer():
    rule = FIELD_RULES["Number of Buildings"]

    assert rule["kind"] == "positive_integer"
    assert rule["minimum"] == 1


def test_monetary_fields_are_non_negative():
    for field in [
        "Building Value",
        "Contents",
        "BI",
        "Other",
    ]:
        rule = FIELD_RULES[field]

        assert rule["kind"] == "monetary"
        assert rule["non_negative"] is True


def test_year_built_has_future_year_protection():
    rule = FIELD_RULES["Year Built"]

    assert rule["kind"] == "year"
    assert rule["not_future"] is True


def test_zip_is_integer_and_non_negative():
    rule = FIELD_RULES["Zip"]

    assert rule["kind"] == "zip"
    assert rule["integer"] is True
    assert rule["non_negative"] is True


def test_sprinkler_values_are_exact():
    assert FIELD_RULES["Fire Sprinklers (Y/N)"]["allowed_values"] == {
        "Y",
        "N",
        "Y13",
        "Y(13R)",
    }


def test_text_fields_reject_numeric_only_values_where_configured():
    for field in [
        "City",
        "State",
        "County",
        "Occupancy",
        "Construction",
    ]:
        assert FIELD_RULES[field]["reject_numeric_only"] is True