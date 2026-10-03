from __future__ import annotations



import re

from typing import Any



import pandas as pd





\# ---------------------------------------------------------------------------

\# SOV vocabulary

\# ---------------------------------------------------------------------------



SOV_HEADER_TERMS = {

    "location",

    "loc",

    "location number",

    "location no",

    "loc number",

    "loc no",

    "building",

    "bldg",

    "building value",

    "bldg value",

    "facility",

    "address",

    "street",

    "city",

    "state",

    "zip",

    "zip code",

    "postal",

    "county",

    "country",

    "construction",

    "construction type",

    "year built",

    "year",

    "built",

    "value",

    "replacement",

    "replacement cost",

    "replacement value",

    "sprinkler",

    "sprinklers",

    "fire sprinkler",

    "occupancy",

    "occupancy type",

    "property",

    "property value",

    "contents",

    "business interruption",

    "bi",

    "total value",

    "tiv",

    "limit",

    "deductible",

    "coverage",

    "roof",

    "roof type",

    "stories",

    "storeys",

    "square feet",

    "sq ft",

    "area",

}





\# ---------------------------------------------------------------------------

\# Basic helpers

\# ---------------------------------------------------------------------------





def _normalize_text(value: object) -> str:

    """Normalize a cell value for text-based comparisons."""



    if value is None:

        return ""



    try:

        if pd.isna(value):

            return ""

    except (TypeError, ValueError):

        pass



    text = str(value).strip().lower()

    text = re.sub(r"\s+", " ", text)



    return text





def _is_empty(value: object) -> bool:

    """Return True when a value should be treated as empty."""



    if value is None:

        return True



    try:

        return bool(pd.isna(value))

    except (TypeError, ValueError):

        return False





def _is_numeric(value: object) -> bool:

    """Return True when a value is numeric or numeric-like."""



    if _is_empty(value):

        return False



    if isinstance(value, bool):

        return False



    if isinstance(value, (int, float)):

        return True



    text = _normalize_text(value)



    if not text:

        return False



    text = text.replace(",", "").replace("$", "").replace("%", "")



    try:

        float(text)

        return True

    except ValueError:

        return False





\# ---------------------------------------------------------------------------

\# Header semantic signals

\# ---------------------------------------------------------------------------





def calculate_header_semantic_score(row: pd.Series) -> float:

    """

    Estimate how strongly a row resembles a real business/SOV header.



    This is intentionally conservative. A header should contain recognizable

    field names rather than merely containing arbitrary SOV-related words.

    """



    values = [

        _normalize_text(value)

        for value in row.tolist()

        if not _is_empty(value)

    ]



    if not values:

        return 0.0



    matches = 0



    for value in values:

        matched = False



        # Exact match.

        if value in SOV_HEADER_TERMS:

            matched = True



        # Allow a normalized header term to occur as a meaningful phrase.

        if not matched:

            for term in SOV_HEADER_TERMS:

                if len(term) >= 4 and term in value:

                    matched = True

                    break



        if matched:

            matches += 1



    return float(matches / len(values))





\# ---------------------------------------------------------------------------

\# Data-row signals

\# ---------------------------------------------------------------------------





def calculate_data_row_likelihood(row: pd.Series) -> float:

    """

    Estimate whether a row looks more like a data record than a header.



    Signals include:

    - numeric-heavy values

    - long identifiers

    - mixed code-like strings

    - descriptive values

    - low header semantics

    """



    values = [

        value

        for value in row.tolist()

        if not _is_empty(value)

    ]



    if not values:

        return 0.0



    normalized = [_normalize_text(value) for value in values]



    numeric_count = sum(

        1

        for value in values

        if _is_numeric(value)

    )



    long_identifier_count = 0

    code_like_count = 0

    long_text_count = 0



    for text in normalized:

        if len(text) >= 8:

            long_identifier_count += 1



        # Code-like values such as:

        # ABC123

        # 047010

        # DWU/TRN

        # LOC-001

        if (

            len(text) >= 4

            and re.search(r"[a-z]", text)

            and re.search(r"\d", text)

        ):

            code_like_count += 1



        if len(text.split()) >= 3 or len(text) >= 25:

            long_text_count += 1



    numeric_ratio = numeric_count / len(values)

    long_identifier_ratio = long_identifier_count / len(values)

    code_like_ratio = code_like_count / len(values)

    long_text_ratio = long_text_count / len(values)



    header_semantic_score = calculate_header_semantic_score(row)



    score = (

        0.30 * numeric_ratio

        + 0.25 * long_identifier_ratio

        + 0.20 * code_like_ratio

        + 0.15 * long_text_ratio

        + 0.10 * (1.0 - header_semantic_score)

    )



    return float(min(score, 1.0))





\# ---------------------------------------------------------------------------

\# Basic row metrics

\# ---------------------------------------------------------------------------





def calculate_non_empty_ratio(row: pd.Series) -> float:

    """Ratio of non-empty cells in a row."""



    if len(row) == 0:

        return 0.0



    non_empty = sum(

        1

        for value in row.tolist()

        if not _is_empty(value)

    )



    return float(non_empty / len(row))





def calculate_text_ratio(row: pd.Series) -> float:

    """Ratio of non-empty cells that are primarily textual."""



    values = [

        value

        for value in row.tolist()

        if not _is_empty(value)

    ]



    if not values:

        return 0.0



    text_count = sum(

        1

        for value in values

        if not _is_numeric(value)

    )



    return float(text_count / len(values))





def calculate_unique_ratio(row: pd.Series) -> float:

    """Ratio of unique non-empty values in a row."""



    values = [

        _normalize_text(value)

        for value in row.tolist()

        if not _is_empty(value)

    ]



    if not values:

        return 0.0



    return float(len(set(values)) / len(values))





def calculate_sov_term_ratio(row: pd.Series) -> float:

    """Ratio of non-empty cells matching SOV vocabulary."""



    values = [

        _normalize_text(value)

        for value in row.tolist()

        if not _is_empty(value)

    ]



    if not values:

        return 0.0



    matches = 0



    for value in values:

        if value in SOV_HEADER_TERMS:

            matches += 1

            continue



        if any(

            len(term) >= 4 and term in value

            for term in SOV_HEADER_TERMS

        ):

            matches += 1



    return float(matches / len(values))





def calculate_numeric_ratio(row: pd.Series) -> float:

    """Ratio of non-empty cells that are numeric."""



    values = [

        value

        for value in row.tolist()

        if not _is_empty(value)

    ]



    if not values:

        return 0.0



    numeric_count = sum(

        1

        for value in values

        if _is_numeric(value)

    )



    return float(numeric_count / len(values))





def calculate_duplicate_ratio(row: pd.Series) -> float:

    """Estimate duplicate values within the row."""



    values = [

        _normalize_text(value)

        for value in row.tolist()

        if not _is_empty(value)

    ]



    if len(values) <= 1:

        return 0.0



    duplicate_count = len(values) - len(set(values))



    return float(duplicate_count / len(values))





def calculate_data_below_score(

    df: pd.DataFrame,

    row_index: int,

) -> float:

    """

    Estimate whether meaningful tabular data exists below a candidate row.

    """



    if df.empty or row_index >= len(df) - 1:

        return 0.0



    remaining = df.iloc[row_index + 1:]



    if remaining.empty:

        return 0.0



    non_empty_rows = (

        ~remaining.isna().all(axis=1)

    ).sum()



    if len(remaining) == 0:

        return 0.0



    return float(non_empty_rows / len(remaining))





\# ---------------------------------------------------------------------------

\# Additional data-pattern signals

\# ---------------------------------------------------------------------------





def calculate_date_like_ratio(row: pd.Series) -> float:

    """Estimate how many values look like dates."""



    values = [

        value

        for value in row.tolist()

        if not _is_empty(value)

    ]



    if not values:

        return 0.0



    date_like = 0



    for value in values:

        text = _normalize_text(value)



        if isinstance(value, pd.Timestamp):

            date_like += 1

            continue



        patterns = [

            r"^\d{1,2}/\d{1,2}/\d{2,4}$",

            r"^\d{4}-\d{1,2}-\d{1,2}$",

            r"^\d{1,2}-\d{1,2}-\d{2,4}$",

            r"^\d{1,2}\s+[a-z]{3,9}\s+\d{2,4}$",

        ]



        if any(

            re.match(pattern, text)

            for pattern in patterns

        ):

            date_like += 1



    return float(date_like / len(values))





def calculate_long_identifier_ratio(row: pd.Series) -> float:

    """

    Estimate how many values look like IDs/codes rather than field names.

    """



    values = [

        _normalize_text(value)

        for value in row.tolist()

        if not _is_empty(value)

    ]



    if not values:

        return 0.0



    count = 0



    for text in values:

        if len(text) >= 8:

            count += 1



    return float(count / len(values))





def calculate_value_pattern_score(row: pd.Series) -> float:

    """

    Estimate whether values follow data-record patterns.



    Higher values indicate:

    - IDs/codes

    - numeric values

    - mixed alphanumeric records

    - descriptive values

    """



    values = [

        _normalize_text(value)

        for value in row.tolist()

        if not _is_empty(value)

    ]



    if not values:

        return 0.0



    pattern_count = 0



    for text in values:

        if _is_numeric(text):

            pattern_count += 1

            continue



        if len(text) >= 8:

            pattern_count += 1

            continue



        if (

            re.search(r"[a-z]", text)

            and re.search(r"\d", text)

        ):

            pattern_count += 1

            continue



        if len(text.split()) >= 3:

            pattern_count += 1



    return float(pattern_count / len(values))





def calculate_row_similarity_to_following_rows(

    df: pd.DataFrame,

    row_index: int,

    lookahead: int = 3,

) -> float:

    """

    Measure structural similarity between a candidate row and rows below it.



    Data rows tend to have similar value-type patterns across consecutive

    records. Headers generally have a different pattern from the rows below.

    """



    if df.empty or row_index >= len(df) - 1:

        return 0.0



    candidate = df.iloc[row_index]



    candidate_values = [

        value

        for value in candidate.tolist()

        if not _is_empty(value)

    ]



    if not candidate_values:

        return 0.0



    candidate_pattern = [

        "num" if _is_numeric(value) else "text"

        for value in candidate.tolist()

    ]



    following = df.iloc[

        row_index + 1:

        min(row_index + 1 + lookahead, len(df))

    ]



    similarities: list[float] = []



    for _, row in following.iterrows():

        row_pattern = [

            "num" if _is_numeric(value) else "text"

            for value in row.tolist()

        ]



        if len(row_pattern) != len(candidate_pattern):

            continue



        matches = sum(

            a == b

            for a, b in zip(

                candidate_pattern,

                row_pattern,

            )

        )



        similarities.append(

            matches / len(candidate_pattern)

            if candidate_pattern

            else 0.0

        )



    if not similarities:

        return 0.0



    return float(sum(similarities) / len(similarities))





\# ---------------------------------------------------------------------------

\# Header score

\# ---------------------------------------------------------------------------





def calculate_header_score(

    non_empty_ratio: float,

    text_ratio: float,

    unique_ratio: float,

    sov_term_ratio: float,

    numeric_ratio: float,

    duplicate_ratio: float,

    data_below_score: float,

    date_like_ratio: float,

    long_identifier_ratio: float,

    value_pattern_score: float,

    row_similarity_score: float,

    header_semantic_score: float,

    data_row_likelihood: float,

) -> float:

    """

    Calculate the overall header candidate score.



    Semantic/header evidence receives high weight.



    Structural characteristics alone should not allow a data row

    to become a header.

    """



    score = (

        0.08 * non_empty_ratio

        + 0.05 * text_ratio

        + 0.05 * unique_ratio

        + 0.22 * sov_term_ratio

        + 0.05 * (1.0 - numeric_ratio)

        + 0.05 * (1.0 - duplicate_ratio)

        + 0.08 * data_below_score

        + 0.05 * (1.0 - date_like_ratio)

        + 0.04 * (1.0 - long_identifier_ratio)

        + 0.04 * (1.0 - value_pattern_score)

        + 0.04 * (1.0 - row_similarity_score)

        + 0.25 * header_semantic_score

        - 0.20 * data_row_likelihood

    )



    return float(max(0.0, min(score, 1.0)))





\# ---------------------------------------------------------------------------

\# Candidate generation

\# ---------------------------------------------------------------------------





def generate_header_candidates(

    df: pd.DataFrame,

    max_rows: int = 30,

) -> list[dict[str, Any]]:

    """

    Generate and score possible header rows.



    Only the first \`max_rows\` rows are considered because SOV files generally

    place their table headers near the beginning of a worksheet.

    """



    if df.empty:

        return []



    candidates: list[dict[str, Any]] = []



    rows_to_check = min(

        max_rows,

        len(df),

    )



    for row_index in range(rows_to_check):

        row = df.iloc[row_index]



        # Completely blank rows cannot be headers.

        if calculate_non_empty_ratio(row) == 0.0:

            continue



        non_empty_ratio = calculate_non_empty_ratio(row)

        text_ratio = calculate_text_ratio(row)

        unique_ratio = calculate_unique_ratio(row)

        sov_term_ratio = calculate_sov_term_ratio(row)

        numeric_ratio = calculate_numeric_ratio(row)

        duplicate_ratio = calculate_duplicate_ratio(row)



        data_below_score = calculate_data_below_score(

            df,

            row_index,

        )



        date_like_ratio = calculate_date_like_ratio(row)

        long_identifier_ratio = calculate_long_identifier_ratio(row)

        value_pattern_score = calculate_value_pattern_score(row)



        row_similarity_score = calculate_row_similarity_to_following_rows(

            df,

            row_index,

        )



        header_semantic_score = calculate_header_semantic_score(row)

        data_row_likelihood = calculate_data_row_likelihood(row)



        score = calculate_header_score(

            non_empty_ratio=non_empty_ratio,

            text_ratio=text_ratio,

            unique_ratio=unique_ratio,

            sov_term_ratio=sov_term_ratio,

            numeric_ratio=numeric_ratio,

            duplicate_ratio=duplicate_ratio,

            data_below_score=data_below_score,

            date_like_ratio=date_like_ratio,

            long_identifier_ratio=long_identifier_ratio,

            value_pattern_score=value_pattern_score,

            row_similarity_score=row_similarity_score,

            header_semantic_score=header_semantic_score,

            data_row_likelihood=data_row_likelihood,

        )



        candidates.append(

            {

                # Keep "row" because the existing test/debug script

                # expects this key.

                "row": row_index,



                # Keep "row_index" as the canonical internal name.

                "row_index": row_index,



                "score": score,

                "non_empty_ratio": non_empty_ratio,

                "text_ratio": text_ratio,

                "unique_ratio": unique_ratio,

                "sov_term_ratio": sov_term_ratio,

                "numeric_ratio": numeric_ratio,

                "duplicate_ratio": duplicate_ratio,

                "data_below_score": data_below_score,

                "date_like_ratio": date_like_ratio,

                "long_identifier_ratio": long_identifier_ratio,

                "value_pattern_score": value_pattern_score,

                "row_similarity_score": row_similarity_score,

                "header_semantic_score": header_semantic_score,

                "data_row_likelihood": data_row_likelihood,

            }

        )



    candidates.sort(

        key=lambda candidate: candidate["score"],

        reverse=True,

    )



    return candidates





\# ---------------------------------------------------------------------------

\# Header confidence

\# ---------------------------------------------------------------------------





def _determine_confidence(

    best_score: float,

    second_score: float | None,

) -> str:

    """

    Convert score and score separation into a confidence label.

    """



    if second_score is None:

        if best_score >= 0.65:

            return "high"



        if best_score >= 0.45:

            return "medium"



        return "low"



    gap = best_score - second_score



    if best_score >= 0.65 and gap >= 0.08:

        return "high"



    if best_score >= 0.45 and gap >= 0.04:

        return "medium"



    return "low"





\# ---------------------------------------------------------------------------

\# Multi-row header detection

\# ---------------------------------------------------------------------------





def _detect_possible_multirow_header(

    df: pd.DataFrame,

    header_row: int | None,

) -> bool:

    """

    Detect a possible two-row header structure.



    This is intentionally conservative and only looks immediately above the

    detected header.

    """



    if header_row is None or header_row <= 0:

        return False



    current_row = df.iloc[header_row]

    previous_row = df.iloc[header_row - 1]



    current_values = [

        _normalize_text(value)

        for value in current_row.tolist()

        if not _is_empty(value)

    ]



    previous_values = [

        _normalize_text(value)

        for value in previous_row.tolist()

        if not _is_empty(value)

    ]



    if not current_values or not previous_values:

        return False



    current_semantics = calculate_header_semantic_score(

        current_row

    )



    previous_semantics = calculate_header_semantic_score(

        previous_row

    )



    previous_non_empty = calculate_non_empty_ratio(

        previous_row

    )



    current_non_empty = calculate_non_empty_ratio(

        current_row

    )



    # A common two-row pattern:

    # row above = category/group labels

    # current row = actual column labels

    if (

        previous_non_empty >= 0.25

        and current_non_empty >= 0.50

        and current_semantics >= 0.15

        and previous_semantics >= 0.05

    ):

        return True



    return False





\# ---------------------------------------------------------------------------

\# Main detector

\# ---------------------------------------------------------------------------





def detect_header(

    df: pd.DataFrame,

    max_rows: int = 30,

) -> dict[str, Any]:

    """

    Detect the most plausible header row in a raw worksheet.



    Returns:

        {

            "header_row": int | None,

            "header_score": float,

            "header_confidence": str,

            "candidate_rows": list[dict],

            "possible_multirow_header": bool,

            "header_rejected_as_data": bool,

        }

    """



    # -----------------------------------------------------------------------

    # Empty dataframe

    # -----------------------------------------------------------------------



    if df.empty:

        return {

            "header_row": None,

            "header_score": 0.0,

            "header_confidence": "low",

            "candidate_rows": [],

            "possible_multirow_header": False,

            "header_rejected_as_data": False,

        }



    # -----------------------------------------------------------------------

    # Generate candidates

    # -----------------------------------------------------------------------



    candidates = generate_header_candidates(

        df=df,

        max_rows=max_rows,

    )



    if not candidates:

        return {

            "header_row": None,

            "header_score": 0.0,

            "header_confidence": "low",

            "candidate_rows": [],

            "possible_multirow_header": False,

            "header_rejected_as_data": False,

        }



    best_candidate = candidates[0]



    second_score = (

        candidates[1]["score"]

        if len(candidates) > 1

        else None

    )



    confidence = _determine_confidence(

        best_score=best_candidate["score"],

        second_score=second_score,

    )



    # -----------------------------------------------------------------------

    # HARD SEMANTIC GATE

    # -----------------------------------------------------------------------

    #

    # Structural properties alone are not enough to declare a row a header.

    # The candidate must contain meaningful header semantics.

    # -----------------------------------------------------------------------



    has_header_semantics = (
        best_candidate["header_semantic_score"] >= 0.12
        or best_candidate["sov_term_ratio"] >= 0.10
    )

    # A sheet can contain a legitimate header without being a
    # property-SOV sheet. In those cases, strong structural evidence
    # should be allowed to override weak SOV-specific semantics.
    has_strong_structural_header = (
        best_candidate["non_empty_ratio"] >= 0.95
        and best_candidate["text_ratio"] >= 0.90
        and best_candidate["unique_ratio"] >= 0.90
        and best_candidate["data_below_score"] >= 0.90
        and best_candidate["value_pattern_score"] >= 0.75
        and best_candidate["data_row_likelihood"] < 0.40
    )

    if not has_header_semantics and not has_strong_structural_header:
        return {
            "header_row": None,
            "header_score": best_candidate["score"],
            "header_confidence": "low",
            "candidate_rows": candidates,
            "possible_multirow_header": False,
            "header_rejected_as_data": True,
        }

    # DATA-ROW REJECTION

    # -----------------------------------------------------------------------

    #

    # Multiple independent signals are used.

    #

    # This is particularly important for sheets such as Trailer and

    # Equipment where actual records can look structurally similar to headers.

    # -----------------------------------------------------------------------



    data_like_without_semantics = (

        (

            best_candidate["data_row_likelihood"] >= 0.45

            and best_candidate["row_similarity_score"] >= 0.85

        )

        or (

            best_candidate["data_row_likelihood"] >= 0.50

            and best_candidate["long_identifier_ratio"] >= 0.20

        )

        or (

            best_candidate["data_row_likelihood"] >= 0.45

            and best_candidate["value_pattern_score"] >= 0.50

            and best_candidate["header_semantic_score"] < 0.30

        )

        or (

            best_candidate["data_row_likelihood"] >= 0.40

            and best_candidate["header_semantic_score"] < 0.20

            and best_candidate["sov_term_ratio"] < 0.15

        )

    )



    if data_like_without_semantics:

        return {

            "header_row": None,

            "header_score": best_candidate["score"],

            "header_confidence": "low",

            "candidate_rows": candidates,

            "possible_multirow_header": False,

            "header_rejected_as_data": True,

        }



    # -----------------------------------------------------------------------

    # Very weak candidates

    # -----------------------------------------------------------------------



    if best_candidate["score"] < 0.30:

        return {

            "header_row": None,

            "header_score": best_candidate["score"],

            "header_confidence": "low",

            "candidate_rows": candidates,

            "possible_multirow_header": False,

            "header_rejected_as_data": False,

        }



    # -----------------------------------------------------------------------

    # Multi-row header detection

    # -----------------------------------------------------------------------



    header_row = int(best_candidate["row_index"])



    possible_multirow_header = _detect_possible_multirow_header(

        df=df,

        header_row=header_row,

    )



    return {

        "header_row": header_row,

        "header_score": best_candidate["score"],

        "header_confidence": confidence,

        "candidate_rows": candidates,

        "possible_multirow_header": possible_multirow_header,

        "header_rejected_as_data": False,

    }