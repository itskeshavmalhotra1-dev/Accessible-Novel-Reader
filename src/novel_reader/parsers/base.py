"""
Abstract base class for document and book format parsers.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from novel_reader.core.models import Book, BookMetadata


class BaseParser(ABC):
    """Abstract interface that all file format parsers must implement."""

    @property
    @abstractmethod
    def supported_extensions(self) -> tuple[str, ...]:
        """Tuple of lowercase file extensions supported by this parser (e.g. ('.txt',))."""

    def can_parse(self, file_path: str | Path) -> bool:
        """Check whether this parser can handle the specified file."""
        path = Path(file_path)
        return path.suffix.lower() in self.supported_extensions

    @abstractmethod
    def extract_metadata(self, file_path: str | Path) -> BookMetadata:
        """Quickly extract metadata without loading full content if possible."""

    @abstractmethod
    def parse(self, file_path: str | Path) -> Book:
        """Parse the full book structure into a Book instance."""
