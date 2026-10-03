from pathlib import Path


SUPPORTED_EXTENSIONS = {
    ".xlsx",
    ".xls",
    ".csv",
}


class FileValidationError(Exception):
    """Raised when an SOV file cannot be processed."""


def validate_file(file_path: str) -> Path:
    """
    Validate that the input path exists, is a file,
    and has a supported SOV file extension.
    """

    path = Path(file_path)

    # Check whether file exists
    if not path.exists():
        raise FileValidationError(
            f"File does not exist: {file_path}"
        )

    # Check whether path is actually a file
    if not path.is_file():
        raise FileValidationError(
            f"Path is not a file: {file_path}"
        )

    # Check supported file type
    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise FileValidationError(
            f"Unsupported file type: {path.suffix}. "
            f"Supported types: {SUPPORTED_EXTENSIONS}"
        )

    return path