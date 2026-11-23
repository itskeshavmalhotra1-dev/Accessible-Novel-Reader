"""
Utility modules for Novel Reader.
"""

from novel_reader.utils.encoding import detect_file_encoding, read_text_file
from novel_reader.utils.text import (
    estimate_reading_time_minutes,
    normalize_whitespace,
    sanitize_speech_text,
    split_into_paragraphs,
    strip_html_tags,
)

__all__ = [
    "detect_file_encoding",
    "read_text_file",
    "strip_html_tags",
    "normalize_whitespace",
    "sanitize_speech_text",
    "split_into_paragraphs",
    "estimate_reading_time_minutes",
]
