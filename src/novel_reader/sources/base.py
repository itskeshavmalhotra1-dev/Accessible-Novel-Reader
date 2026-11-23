"""
Base models and abstract interface for online novel sources and scrapers.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class CategoryItem:
    """Represents a category or genre from a novel source."""
    name: str
    url: str


@dataclass
class NovelItem:
    """Represents a novel from a web source."""
    id: str
    title: str
    url: str
    source_name: str
    author: str = "Unknown Author"
    description: str = ""
    latest_chapter: str = ""


@dataclass
class ChapterItem:
    """Represents a chapter in the table of contents."""
    index: int
    title: str
    url: str
    novel_url: str = ""


@dataclass
class ChapterContent:
    """Extracted text content of a chapter."""
    title: str
    content: str
    url: str
    prev_chapter_url: Optional[str] = None
    next_chapter_url: Optional[str] = None
    word_count: int = 0

    def __post_init__(self) -> None:
        if not self.word_count and self.content:
            self.word_count = len(self.content.split())


class BaseNovelSource(ABC):
    """Abstract base class for scraping and fetching novels from online websites."""

    @property
    @abstractmethod
    def name(self) -> str:
        """User-friendly name of the source."""

    @property
    @abstractmethod
    def base_url(self) -> str:
        """Root URL of the website."""

    @abstractmethod
    def get_categories(self) -> List[CategoryItem]:
        """Retrieve available categories and genres."""

    @abstractmethod
    def get_novels_by_category(self, category_url: str, page: int = 1) -> List[NovelItem]:
        """Retrieve novels for a given category/genre and page number."""

    @abstractmethod
    def search(self, query: str, page: int = 1) -> List[NovelItem]:
        """Search novels by keyword."""

    @abstractmethod
    def get_latest(self, page: int = 1) -> List[NovelItem]:
        """Get latest or popular novels."""

    @abstractmethod
    def get_chapters(self, novel_url: str) -> List[ChapterItem]:
        """Retrieve chapter list for a novel."""

    @abstractmethod
    def get_chapter_content(self, chapter_url: str) -> ChapterContent:
        """Fetch and extract cleaned text for a specific chapter."""
