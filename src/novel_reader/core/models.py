"""
Core domain data models for Novel Reader.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class BookMetadata:
    """Metadata describing a book."""
    title: str
    author: str = "Unknown Author"
    language: str = "en"
    description: str = ""
    identifier: str = ""
    source_format: str = "txt"
    created_at: datetime = field(default_factory=_utc_now)


@dataclass
class Chapter:
    """A single chapter or logical section within a book."""
    index: int
    title: str
    content: str
    word_count: int = 0
    id: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.word_count and self.content:
            self.word_count = len(self.content.split())


@dataclass
class Bookmark:
    """A saved reading mark in a book."""
    id: Optional[int] = None
    book_id: str = ""
    chapter_index: int = 0
    paragraph_index: int = 0
    character_offset: int = 0
    label: str = ""
    snippet: str = ""
    created_at: datetime = field(default_factory=_utc_now)


@dataclass
class ReadingProgress:
    """Current reading state for a book."""
    book_id: str
    current_chapter_index: int = 0
    current_paragraph_index: int = 0
    current_character_offset: int = 0
    percentage: float = 0.0
    last_read_at: datetime = field(default_factory=_utc_now)


@dataclass
class Book:
    """In-memory representation of a parsed book."""
    id: str
    file_path: str
    metadata: BookMetadata
    chapters: List[Chapter] = field(default_factory=list)

    @property
    def total_chapters(self) -> int:
        return len(self.chapters)

    @property
    def total_words(self) -> int:
        return sum(ch.word_count for ch in self.chapters)

    def get_chapter(self, index: int) -> Optional[Chapter]:
        if 0 <= index < len(self.chapters):
            return self.chapters[index]
        return None
