"""
Tests for SQLite library database, bookmarks, and reading progress.
"""

from novel_reader.core.models import Bookmark, ReadingProgress
from novel_reader.library.database import Database


def test_database_book_upsert_and_retrieval(temp_db: Database) -> None:
    temp_db.upsert_book(
        book_id="book-001",
        title="Dune",
        author="Frank Herbert",
        language="en",
        description="Sci-fi classic",
        file_path="/path/to/dune.txt",
        source_format="txt",
        total_chapters=48,
        total_words=180000,
    )

    book = temp_db.get_book("book-001")
    assert book is not None
    assert book["title"] == "Dune"
    assert book["author"] == "Frank Herbert"
    assert book["total_chapters"] == 48


def test_reading_progress_persistence(temp_db: Database) -> None:
    temp_db.upsert_book(
        book_id="book-002",
        title="1984",
        author="George Orwell",
        language="en",
        description="",
        file_path="/path/to/1984.txt",
        source_format="txt",
        total_chapters=24,
        total_words=80000,
    )

    progress = ReadingProgress(
        book_id="book-002",
        current_chapter_index=3,
        current_paragraph_index=12,
        percentage=12.5,
    )
    temp_db.save_reading_progress(progress)

    loaded = temp_db.get_reading_progress("book-002")
    assert loaded is not None
    assert loaded.current_chapter_index == 3
    assert loaded.current_paragraph_index == 12
    assert loaded.percentage == 12.5


def test_bookmarks_lifecycle(temp_db: Database) -> None:
    temp_db.upsert_book(
        book_id="book-003",
        title="Foundation",
        author="Isaac Asimov",
        language="en",
        description="",
        file_path="/path/to/foundation.txt",
        source_format="txt",
        total_chapters=10,
        total_words=60000,
    )

    bm1 = Bookmark(book_id="book-003", chapter_index=2, paragraph_index=5, label="Key Clue", snippet="Hari Seldon spoke...")
    bm_id = temp_db.add_bookmark(bm1)
    assert bm_id > 0

    bookmarks = temp_db.get_bookmarks("book-003")
    assert len(bookmarks) == 1
    assert bookmarks[0].label == "Key Clue"
    assert bookmarks[0].snippet == "Hari Seldon spoke..."

    deleted = temp_db.delete_bookmark(bm_id)
    assert deleted is True
    assert len(temp_db.get_bookmarks("book-003")) == 0
