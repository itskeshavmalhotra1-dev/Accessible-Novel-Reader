"""
SQLite database engine for local book storage, reading history, and bookmarks.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
import sqlite3
from typing import Generator, List, Optional

from novel_reader.core.exceptions import StorageError
from novel_reader.core.models import BookMetadata, Bookmark, ReadingProgress


class Database:
    """Thread-safe SQLite database manager for library persistence."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        if db_path is None:
            # Default to user home directory or project directory
            home_dir = Path.home() / ".novel_reader"
            home_dir.mkdir(parents=True, exist_ok=True)
            self.db_path = home_dir / "library.db"
        else:
            self.db_path = Path(db_path)
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._init_schema()

    @contextmanager
    def _get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        try:
            conn = sqlite3.connect(self.db_path, timeout=10.0)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON;")
            conn.execute("PRAGMA journal_mode = WAL;")
            yield conn
            conn.commit()
        except sqlite3.Error as e:
            if 'conn' in locals():
                conn.rollback()
            raise StorageError(f"Database error: {e}") from e
        finally:
            if 'conn' in locals():
                conn.close()

    def _init_schema(self) -> None:
        with self._get_connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS books (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    author TEXT NOT NULL DEFAULT 'Unknown Author',
                    language TEXT NOT NULL DEFAULT 'en',
                    description TEXT DEFAULT '',
                    file_path TEXT NOT NULL,
                    source_format TEXT NOT NULL,
                    total_chapters INTEGER DEFAULT 0,
                    total_words INTEGER DEFAULT 0,
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS reading_progress (
                    book_id TEXT PRIMARY KEY,
                    current_chapter_index INTEGER DEFAULT 0,
                    current_paragraph_index INTEGER DEFAULT 0,
                    current_character_offset INTEGER DEFAULT 0,
                    percentage REAL DEFAULT 0.0,
                    last_read_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS bookmarks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    book_id TEXT NOT NULL,
                    chapter_index INTEGER DEFAULT 0,
                    paragraph_index INTEGER DEFAULT 0,
                    character_offset INTEGER DEFAULT 0,
                    label TEXT DEFAULT '',
                    snippet TEXT DEFAULT '',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_bookmarks_book ON bookmarks(book_id);
                """
            )

    def upsert_book(
        self,
        book_id: str,
        title: str,
        author: str,
        language: str,
        description: str,
        file_path: str,
        source_format: str,
        total_chapters: int,
        total_words: int,
    ) -> None:
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO books (id, title, author, language, description, file_path, source_format, total_chapters, total_words)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    title=excluded.title,
                    author=excluded.author,
                    language=excluded.language,
                    description=excluded.description,
                    file_path=excluded.file_path,
                    source_format=excluded.source_format,
                    total_chapters=excluded.total_chapters,
                    total_words=excluded.total_words;
                """,
                (
                    book_id,
                    title,
                    author,
                    language,
                    description,
                    file_path,
                    source_format,
                    total_chapters,
                    total_words,
                ),
            )

    def get_book(self, book_id: str) -> Optional[dict]:
        with self._get_connection() as conn:
            cur = conn.execute("SELECT * FROM books WHERE id = ?", (book_id,))
            row = cur.fetchone()
            return dict(row) if row else None

    def list_books(self) -> List[dict]:
        with self._get_connection() as conn:
            cur = conn.execute(
                """
                SELECT b.*, p.current_chapter_index, p.percentage, p.last_read_at
                FROM books b
                LEFT JOIN reading_progress p ON b.id = p.book_id
                ORDER BY coalesce(p.last_read_at, b.added_at) DESC
                """
            )
            return [dict(row) for row in cur.fetchall()]

    def delete_book(self, book_id: str) -> bool:
        with self._get_connection() as conn:
            cur = conn.execute("DELETE FROM books WHERE id = ?", (book_id,))
            return cur.rowcount > 0

    def save_reading_progress(self, progress: ReadingProgress) -> None:
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO reading_progress (
                    book_id, current_chapter_index, current_paragraph_index,
                    current_character_offset, percentage, last_read_at
                ) VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(book_id) DO UPDATE SET
                    current_chapter_index=excluded.current_chapter_index,
                    current_paragraph_index=excluded.current_paragraph_index,
                    current_character_offset=excluded.current_character_offset,
                    percentage=excluded.percentage,
                    last_read_at=CURRENT_TIMESTAMP;
                """,
                (
                    progress.book_id,
                    progress.current_chapter_index,
                    progress.current_paragraph_index,
                    progress.current_character_offset,
                    progress.percentage,
                ),
            )

    def get_reading_progress(self, book_id: str) -> Optional[ReadingProgress]:
        with self._get_connection() as conn:
            cur = conn.execute("SELECT * FROM reading_progress WHERE book_id = ?", (book_id,))
            row = cur.fetchone()
            if not row:
                return None
            return ReadingProgress(
                book_id=row["book_id"],
                current_chapter_index=row["current_chapter_index"],
                current_paragraph_index=row["current_paragraph_index"],
                current_character_offset=row["current_character_offset"],
                percentage=row["percentage"],
            )

    def add_bookmark(self, bookmark: Bookmark) -> int:
        with self._get_connection() as conn:
            cur = conn.execute(
                """
                INSERT INTO bookmarks (
                    book_id, chapter_index, paragraph_index, character_offset, label, snippet
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    bookmark.book_id,
                    bookmark.chapter_index,
                    bookmark.paragraph_index,
                    bookmark.character_offset,
                    bookmark.label,
                    bookmark.snippet,
                ),
            )
            return cur.lastrowid or 0

    def get_bookmarks(self, book_id: str) -> List[Bookmark]:
        with self._get_connection() as conn:
            cur = conn.execute(
                "SELECT * FROM bookmarks WHERE book_id = ? ORDER BY chapter_index, paragraph_index",
                (book_id,),
            )
            return [
                Bookmark(
                    id=row["id"],
                    book_id=row["book_id"],
                    chapter_index=row["chapter_index"],
                    paragraph_index=row["paragraph_index"],
                    character_offset=row["character_offset"],
                    label=row["label"],
                    snippet=row["snippet"],
                )
                for row in cur.fetchall()
            ]

    def delete_bookmark(self, bookmark_id: int) -> bool:
        with self._get_connection() as conn:
            cur = conn.execute("DELETE FROM bookmarks WHERE id = ?", (bookmark_id,))
            return cur.rowcount > 0
