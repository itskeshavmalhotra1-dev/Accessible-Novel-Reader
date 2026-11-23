"""
Domain exceptions for Novel Reader.
"""


class NovelReaderError(Exception):
    """Base exception for all novel-reader errors."""


class UnsupportedFormatError(NovelReaderError):
    """Raised when an unsupported file format or extension is encountered."""


class ParserError(NovelReaderError):
    """Raised when parsing a book or document fails."""


class StorageError(NovelReaderError):
    """Raised when reading from or writing to the library database fails."""


class BookNotFoundError(StorageError):
    """Raised when a requested book is not found in the library."""
