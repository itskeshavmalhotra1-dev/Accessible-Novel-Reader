"""
Core domain models and exceptions.
"""

from novel_reader.core.exceptions import (
    BookNotFoundError,
    NovelReaderError,
    ParserError,
    StorageError,
    UnsupportedFormatError,
)
from novel_reader.core.models import (
    Book,
    BookMetadata,
    Bookmark,
    Chapter,
    ReadingProgress,
)

__all__ = [
    "Book",
    "BookMetadata",
    "Bookmark",
    "Chapter",
    "ReadingProgress",
    "NovelReaderError",
    "UnsupportedFormatError",
    "ParserError",
    "StorageError",
    "BookNotFoundError",
]
