"""
Static US reference data used by the State/ZIP validators and the
deterministic normalizers.

Only lookup tables live here; no validation logic.
"""

STATE_NAME_TO_CODE: dict[str, str] = {
    "alabama": "AL",
    "alaska": "AK",
    "arizona": "AZ",
    "arkansas": "AR",
    "california": "CA",
    "colorado": "CO",
    "connecticut": "CT",
    "delaware": "DE",
    "florida": "FL",
    "georgia": "GA",
    "hawaii": "HI",
    "idaho": "ID",
    "illinois": "IL",
    "indiana": "IN",
    "iowa": "IA",
    "kansas": "KS",
    "kentucky": "KY",
    "louisiana": "LA",
    "maine": "ME",
    "maryland": "MD",
    "massachusetts": "MA",
    "michigan": "MI",
    "minnesota": "MN",
    "mississippi": "MS",
    "missouri": "MO",
    "montana": "MT",
    "nebraska": "NE",
    "nevada": "NV",
    "new hampshire": "NH",
    "new jersey": "NJ",
    "new mexico": "NM",
    "new york": "NY",
    "north carolina": "NC",
    "north dakota": "ND",
    "ohio": "OH",
    "oklahoma": "OK",
    "oregon": "OR",
    "pennsylvania": "PA",
    "rhode island": "RI",
    "south carolina": "SC",
    "south dakota": "SD",
    "tennessee": "TN",
    "texas": "TX",
    "utah": "UT",
    "vermont": "VT",
    "virginia": "VA",
    "washington": "WA",
    "west virginia": "WV",
    "wisconsin": "WI",
    "wyoming": "WY",
    # Federal district and territories.
    "district of columbia": "DC",
    "puerto rico": "PR",
    "virgin islands": "VI",
    "us virgin islands": "VI",
    "u.s. virgin islands": "VI",
    "guam": "GU",
    "american samoa": "AS",
    "northern mariana islands": "MP",
}


STATE_CODES: set[str] = set(STATE_NAME_TO_CODE.values())


# AP-style abbreviations commonly found in client spreadsheets.
# Keys are lower-case with dots and spaces removed.
AP_STATE_ABBREVIATIONS: dict[str, str] = {
    "ala": "AL",
    "ariz": "AZ",
    "ark": "AR",
    "calif": "CA",
    "colo": "CO",
    "conn": "CT",
    "del": "DE",
    "fla": "FL",
    "ga": "GA",
    "ill": "IL",
    "ind": "IN",
    "kan": "KS",
    "kans": "KS",
    "ky": "KY",
    "la": "LA",
    "md": "MD",
    "mass": "MA",
    "mich": "MI",
    "minn": "MN",
    "miss": "MS",
    "mo": "MO",
    "mont": "MT",
    "neb": "NE",
    "nebr": "NE",
    "nev": "NV",
    "okla": "OK",
    "ore": "OR",
    "pa": "PA",
    "penn": "PA",
    "tenn": "TN",
    "tex": "TX",
    "vt": "VT",
    "va": "VA",
    "wash": "WA",
    "wva": "WV",
    "wis": "WI",
    "wisc": "WI",
    "wyo": "WY",
}


US_COUNTRY_ALIASES: set[str] = {
    "us",
    "usa",
    "u.s.",
    "u.s.a.",
    "u.s",
    "u.s.a",
    "united states",
    "united states of america",
    "america",
}


# First three ZIP digits -> plausible state codes.
# Ranges are inclusive. A few prefixes legitimately serve more than
# one state, so each range maps to a set.
_ZIP3_RANGES: list[tuple[int, int, set[str]]] = [
    (5, 5, {"NY"}),
    (6, 7, {"PR"}),
    (8, 8, {"VI"}),
    (9, 9, {"PR"}),
    (10, 27, {"MA"}),
    (28, 29, {"RI"}),
    (30, 38, {"NH"}),
    (39, 49, {"ME"}),
    (50, 54, {"VT"}),
    (55, 55, {"MA"}),
    (56, 59, {"VT"}),
    (60, 69, {"CT"}),
    (70, 89, {"NJ"}),
    (100, 149, {"NY"}),
    (150, 196, {"PA"}),
    (197, 199, {"DE"}),
    (200, 200, {"DC"}),
    (201, 201, {"VA"}),
    (202, 205, {"DC"}),
    (206, 219, {"MD"}),
    (220, 246, {"VA"}),
    (247, 268, {"WV"}),
    (270, 289, {"NC"}),
    (290, 299, {"SC"}),
    (300, 319, {"GA"}),
    (320, 349, {"FL"}),
    (350, 369, {"AL"}),
    (370, 385, {"TN"}),
    (386, 397, {"MS"}),
    (398, 399, {"GA"}),
    (400, 427, {"KY"}),
    (430, 459, {"OH"}),
    (460, 479, {"IN"}),
    (480, 499, {"MI"}),
    (500, 528, {"IA"}),
    (530, 549, {"WI"}),
    (550, 567, {"MN"}),
    (569, 569, {"DC"}),
    (570, 577, {"SD"}),
    (580, 588, {"ND"}),
    (590, 599, {"MT"}),
    (600, 629, {"IL"}),
    (630, 658, {"MO"}),
    (660, 679, {"KS"}),
    (680, 693, {"NE"}),
    (700, 714, {"LA"}),
    (716, 729, {"AR"}),
    (730, 732, {"OK"}),
    (733, 733, {"TX"}),
    (734, 749, {"OK"}),
    (750, 799, {"TX"}),
    (800, 816, {"CO"}),
    (820, 831, {"WY"}),
    (832, 838, {"ID"}),
    (840, 847, {"UT"}),
    (850, 865, {"AZ"}),
    (870, 884, {"NM"}),
    (885, 885, {"TX"}),
    (889, 898, {"NV"}),
    (900, 961, {"CA"}),
    (967, 968, {"HI"}),
    (969, 969, {"GU", "AS", "MP"}),
    (970, 979, {"OR"}),
    (980, 994, {"WA"}),
    (995, 999, {"AK"}),
]


def states_for_zip_prefix(zip_code: str) -> set[str] | None:
    """
    Return the plausible state codes for a 5-digit ZIP, or None when
    the prefix is not in the table (unknown or military ranges).
    """

    digits = zip_code[:3]

    if len(digits) != 3 or not digits.isdigit():
        return None

    prefix = int(digits)

    for low, high, states in _ZIP3_RANGES:
        if low <= prefix <= high:
            return states

    return None
