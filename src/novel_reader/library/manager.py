"""
High-level library management services.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

from novel_reader.core.exceptions import BookNotFoundError
from novel_reader.core.models import Book, Bookmark, ReadingProgress
from novel_reader.library.database import Database
from novel_reader.parsers.factory import ParserFactory, default_factory


class LibraryManager:
    """Manages the user's book collection, reading progress, and bookmarks."""

    def __init__(self, db: Database | None = None, parser_factory: ParserFactory | None = None) -> None:
        self.db = db or Database()
        self.parser_factory = parser_factory or default_factory
        self._book_cache: Dict[str, Book] = {}

    def import_book(self, file_path: str | Path) -> Book:
        """Parse and import a book file into the library."""
        path = Path(file_path).resolve()
        parser = self.parser_factory.get_parser_for_file(path)
        book = parser.parse(path)

        self.db.upsert_book(
            book_id=book.id,
            title=book.metadata.title,
            author=book.metadata.author,
            language=book.metadata.language,
            description=book.metadata.description,
            file_path=str(path),
            source_format=book.metadata.source_format,
            total_chapters=book.total_chapters,
            total_words=book.total_words,
        )

        self._book_cache[book.id] = book
        return book

    def load_book(self, book_id: str) -> Book:
        """Load a book by ID, utilizing memory cache if available."""
        if book_id in self._book_cache:
            return self._book_cache[book_id]

        record = self.db.get_book(book_id)
        if not record:
            raise BookNotFoundError(f"Book with ID '{book_id}' not found in library.")

        file_path = Path(record["file_path"])
        if not file_path.exists():
            raise FileNotFoundError(f"Original book file missing: {file_path}")

        parser = self.parser_factory.get_parser_for_file(file_path)
        book = parser.parse(file_path)
        self._book_cache[book.id] = book
        return book

    def list_books(self) -> List[dict]:
        """List all books in the library."""
        return self.db.list_books()

    def remove_book(self, book_id: str) -> bool:
        """Remove a book from the library database."""
        self._book_cache.pop(book_id, None)
        return self.db.delete_book(book_id)

    def get_progress(self, book_id: str) -> ReadingProgress:
        """Get reading progress for a book or initialize default."""
        progress = self.db.get_reading_progress(book_id)
        if not progress:
            progress = ReadingProgress(book_id=book_id)
        return progress

    def save_progress(self, progress: ReadingProgress) -> None:
        """Persist updated reading progress."""
        self.db.save_reading_progress(progress)

    def add_bookmark(self, bookmark: Bookmark) -> int:
        """Add a bookmark."""
        return self.db.add_bookmark(bookmark)

    def get_bookmarks(self, book_id: str) -> List[Bookmark]:
        """Retrieve bookmarks for a book."""
        return self.db.get_bookmarks(book_id)

    def delete_bookmark(self, bookmark_id: int) -> bool:
        """Delete a bookmark by ID."""
        return self.db.delete_bookmark(bookmark_id)
