import re
import unicodedata


def normalize_header(value: object) -> str:
    """
    Normalize a source SOV header for deterministic comparison.

    This function performs only syntactic normalization.
    It does not perform semantic field mapping.
    """

    if value is None:
        return ""

    text = str(value)

    if not text.strip():
        return ""

    text = unicodedata.normalize("NFKC", text)

    text = text.strip().lower()

    text = text.replace("_", " ")
    text = text.replace("-", " ")

    text = re.sub(r"[^\w\s]", " ", text)

    text = re.sub(r"\s+", " ", text)

    return text.strip()