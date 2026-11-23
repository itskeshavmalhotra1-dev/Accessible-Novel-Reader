"""
Encoding utilities for reading text documents robustly across various encodings.
"""

from pathlib import Path


def detect_file_encoding(file_path: str | Path) -> str:
    """
    Detect the character encoding of a file.
    Tries charset-normalizer first if available, then falls back to heuristic checks.
    """
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"File not found: {file_path}")

    # Read the first chunk (up to 64KB) for detection
    with open(path, "rb") as f:
        raw = f.read(65536)

    if not raw:
        return "utf-8"

    # Check common BOMs
    if raw.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"
    if raw.startswith(b"\xff\xfe"):
        return "utf-16-le"
    if raw.startswith(b"\xfe\xff"):
        return "utf-16-be"

    try:
        from charset_normalizer import from_bytes
        matches = from_bytes(raw)
        best = matches.best()
        if best and best.encoding:
            return best.encoding
    except ImportError:
        pass

    # Fallback heuristic: Try utf-8
    try:
        raw.decode("utf-8")
        return "utf-8"
    except UnicodeDecodeError:
        pass

    # Fallback to system default or cp1252 / latin-1
    return "latin-1"


def read_text_file(file_path: str | Path, encoding: str | None = None) -> tuple[str, str]:
    """
    Read text file content safely, returning (content, detected_encoding).
    """
    path = Path(file_path)
    enc = encoding or detect_file_encoding(path)

    try:
        with open(path, "r", encoding=enc, errors="replace") as f:
            return f.read(), enc
    except (UnicodeDecodeError, LookupError):
        # Fallback with replacement
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read(), "utf-8-replace"
