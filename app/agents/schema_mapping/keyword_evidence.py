"""
Concept-keyword evidence for schema mapping.

Exact/alias matching needs the whole header to be known and fuzzy
matching needs similar spelling. Real SOV headers combine a small set of
insurance concepts in endless ways ("Bldg TIV", "Yr Blt", "Building Sum
Insured", "Premises Address"). This module:

1. expands standard SOV abbreviations token by token;
2. recognises the concept words that identify each target field.

It is domain knowledge, not a list of headers: each rule names a
concept, and a header matches when it contains that concept's words.
Matches are moderate-confidence evidence (they still pass the value
plausibility veto, the one-to-one assignment and human review).
"""

from typing import Optional

from app.agents.schema_mapping.header_normalizer import normalize_header


ABBREVIATIONS = {
    "bldg": "building",
    "bldgs": "buildings",
    "blt": "built",
    "yr": "year",
    "yrs": "years",
    "const": "construction",
    "constr": "construction",
    "cnstr": "construction",
    "occ": "occupancy",
    "occup": "occupancy",
    "desc": "description",
    "descr": "description",
    "cnty": "county",
    "ctry": "country",
    "cntry": "country",
    "addr": "address",
    "st": "state",
    "prov": "province",
    "loc": "location",
    "locn": "location",
    "ref": "reference",
    "num": "number",
    "no": "number",
    "nr": "number",
    "qty": "number",
    "amt": "amount",
    "val": "value",
    "repl": "replacement",
    "sprk": "sprinkler",
    "sprink": "sprinkler",
    "spr": "sprinkler",
    "flrs": "floors",
    "stys": "stories",
    "misc": "other",
}

VALUE_WORDS = {
    "value", "values", "limit", "limits", "tiv", "amount", "insured",
    "sum", "rcv", "acv", "replacement", "cost", "exposure",
}
COUNT_WORDS = {"number", "count", "total", "how", "many"}
ID_WORDS = {"id", "number", "reference", "code", "key", "identifier"}
YEAR_WORDS = {"year"}
BUILT_WORDS = {"built", "constructed", "construction", "build", "erected"}

BUILDING_OBJECTS = {"building", "structure", "structures", "real", "dwelling"}
CONTENTS_OBJECTS = {
    "contents", "content", "bpp", "stock", "inventory", "equipment",
    "machinery", "furniture", "fixtures", "personal",
}
BI_WORDS = {"bi", "income", "interruption", "rental", "rents", "earnings"}
ENTITY_WORDS = {"location", "site", "property", "risk", "premises", "item", "building"}

SINGLE_CONCEPTS = [
    ("Fire Sprinklers (Y/N)", {"sprinkler", "sprinklers", "sprinklered"}),
    ("Zip", {"zip", "zipcode", "postal", "postcode", "zip5"}),
    ("County", {"county", "parish"}),
    ("Country", {"country", "nation"}),
    ("City", {"city", "town", "municipality"}),
    ("State", {"state", "province"}),
    ("Address", {"address", "street"}),
    ("Occupancy", {"occupancy", "occupation"}),
    ("Storeys", {"stories", "storeys", "floors", "floor", "levels"}),
]


def expanded_tokens(header: object) -> list[str]:
    tokens = normalize_header(header).split()
    return [ABBREVIATIONS.get(token, token) for token in tokens]


def keyword_match(header: object) -> Optional[tuple[str, str]]:
    """
    Return (target_field, explanation) when the header contains the
    concept words of exactly one target field, else None.
    """

    tokens = expanded_tokens(header)
    words = set(tokens)

    if not words:
        return None

    matches: list[tuple[str, str]] = []

    # Year Built takes precedence over Construction ("Construction Year").
    if words & YEAR_WORDS and words & BUILT_WORDS:
        return "Year Built", "year + built/constructed"

    if words & {"construction"} and not words & {"roof", "date", "re"}:
        matches.append(("Construction", "construction"))

    # "Number of Buildings" / "Bldg Count" are counts; "Building Number"
    # (singular + number) is an identifier.
    if not words & VALUE_WORDS and (
        ("buildings" in words and words & COUNT_WORDS)
        or ("building" in words and words & {"count", "total"})
    ):
        return "Number of Buildings", "count of buildings"

    if words & BI_WORDS and (
        words & {"bi", "interruption"}
        or words & {"income", "rental", "rents", "earnings"}
    ):
        matches.append(("BI", "business income / interruption"))

    if words & CONTENTS_OBJECTS and (
        words & VALUE_WORDS
        or words & {"contents", "bpp", "stock"}
        or {"personal", "property"} <= words
    ):
        matches.append(("Contents", "contents / personal property"))

    elif words & BUILDING_OBJECTS and (
        words & VALUE_WORDS or {"real", "property"} <= words
    ) and not words & COUNT_WORDS - {"total"}:
        matches.append(("Building Value", "building + value word"))

    if words & {"other"} and (words & VALUE_WORDS or words & {"property", "values"}):
        matches.append(("Other", "other insured values"))

    if words & ENTITY_WORDS and words & ID_WORDS and not words & {
        "zip", "postal", "city", "phone", "policy",
    }:
        matches.append(("Reference", "location/site + id/number"))

    for target, concept in SINGLE_CONCEPTS:
        if words & concept:
            matches.append((target, "/".join(sorted(words & concept))))

    targets = {target for target, _ in matches}

    if len(targets) != 1:
        return None

    target, reason = matches[0]
    return target, reason
