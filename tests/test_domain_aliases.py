import pytest

from app.agents.schema_mapping.domain_aliases import (
    DOMAIN_ALIASES,
    DOMAIN_ALIAS_LOOKUP,
    build_domain_alias_lookup,
)
from app.agents.schema_mapping.target_schema import TARGET_FIELD_NAMES


def test_all_target_fields_have_domain_alias_entries():
    for field_name in TARGET_FIELD_NAMES:
        assert field_name in DOMAIN_ALIASES


def test_domain_aliases_are_not_empty():
    for field_name, aliases in DOMAIN_ALIASES.items():
        assert aliases, f"No aliases defined for {field_name}"


def test_aliases_are_normalized_in_lookup():
    assert DOMAIN_ALIAS_LOOKUP["bldg value"] == "Building Value"
    assert DOMAIN_ALIAS_LOOKUP["business interruption"] == "BI"
    assert DOMAIN_ALIAS_LOOKUP["stories"] == "Storeys"


def test_common_sov_aliases():
    assert DOMAIN_ALIAS_LOOKUP["replacement cost"] == "Building Value"
    assert DOMAIN_ALIAS_LOOKUP["contents value"] == "Contents"
    assert DOMAIN_ALIAS_LOOKUP["business income"] == "BI"
    assert DOMAIN_ALIAS_LOOKUP["construction type"] == "Construction"
    assert DOMAIN_ALIAS_LOOKUP["building count"] == "Number of Buildings"


def test_fire_sprinkler_aliases():
    assert DOMAIN_ALIAS_LOOKUP["fire sprinkler"] == "Fire Sprinklers (Y/N)"
    assert DOMAIN_ALIAS_LOOKUP["sprinkler protection"] == (
        "Fire Sprinklers (Y/N)"
    )


def test_alias_lookup_contains_no_empty_keys():
    assert "" not in DOMAIN_ALIAS_LOOKUP


def test_alias_lookup_has_unique_targets_per_alias():
    rebuilt = build_domain_alias_lookup()

    assert rebuilt == DOMAIN_ALIAS_LOOKUP


def test_conflicting_aliases_are_rejected(monkeypatch):
    import app.agents.schema_mapping.domain_aliases as module

    original = module.DOMAIN_ALIASES

    monkeypatch.setattr(
        module,
        "DOMAIN_ALIASES",
        {
            "Address": ["shared alias"],
            "City": ["shared alias"],
        },
    )

    with pytest.raises(ValueError, match="Domain alias conflict"):
        module.build_domain_alias_lookup()

    monkeypatch.setattr(module, "DOMAIN_ALIASES", original)


def test_no_dataset_specific_raw_values():
    suspicious_values = {
        "SOV_B4ID",
        "SOV_H6D2",
        "SOV_K4T9",
        "SOV_Q8B3",
    }

    all_aliases = {
        alias
        for aliases in DOMAIN_ALIASES.values()
        for alias in aliases
    }

    assert suspicious_values.isdisjoint(all_aliases)