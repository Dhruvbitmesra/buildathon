from app.agents.schema_mapping.header_normalizer import normalize_header


def test_lowercase_conversion():
    assert normalize_header("BUILDING VALUE") == "building value"


def test_strip_whitespace():
    assert normalize_header("  Building Value  ") == "building value"


def test_underscore_conversion():
    assert normalize_header("Building_Value") == "building value"


def test_hyphen_conversion():
    assert normalize_header("Building-Value") == "building value"


def test_punctuation_removal():
    assert normalize_header("No. of Buildings") == "no of buildings"


def test_parentheses_removal():
    assert normalize_header("Fire Sprinklers (Y/N)") == "fire sprinklers y n"


def test_repeated_whitespace():
    assert normalize_header("Building   Replacement    Cost") == (
        "building replacement cost"
    )


def test_none_value():
    assert normalize_header(None) == ""


def test_empty_value():
    assert normalize_header("") == ""


def test_whitespace_only_value():
    assert normalize_header("     ") == ""


def test_meaningful_words_are_preserved():
    assert normalize_header("Bldg Repl Cost New") == "bldg repl cost new"


def test_no_semantic_mapping():
    result = normalize_header("Bldg Repl Cost New")

    assert result != "building value"
    assert result == "bldg repl cost new"


def test_unicode_normalization():
    assert normalize_header("Ｂｕｉｌｄｉｎｇ Ｖａｌｕｅ") == "building value"