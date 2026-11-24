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


def test_novel_bookmarks_save_update_and_deduplication(temp_db: Database) -> None:
    # 1. Save initial bookmark for Novel 1
    bm_id = temp_db.save_novel_bookmark(
        source_name="MockSource",
        novel_title="Sword God",
        novel_url="http://mock.test/novel/sword-god",
        chapter_index=1,
        chapter_title="Chapter 1: Awaken",
        chapter_url="http://mock.test/novel/sword-god/ch1",
    )
    assert bm_id > 0

    all_bms = temp_db.list_novel_bookmarks()
    assert len(all_bms) == 1
    assert all_bms[0]["novel_title"] == "Sword God"
    assert all_bms[0]["chapter_index"] == 1

    # 2. Update bookmark for the same novel to Chapter 15 - must NOT create duplicate rows
    temp_db.save_novel_bookmark(
        source_name="MockSource",
        novel_title="Sword God",
        novel_url="http://mock.test/novel/sword-god",
        chapter_index=15,
        chapter_title="Chapter 15: The Breakthrough",
        chapter_url="http://mock.test/novel/sword-god/ch15",
    )

    all_bms2 = temp_db.list_novel_bookmarks()
    assert len(all_bms2) == 1  # Guaranteed zero duplicates
    assert all_bms2[0]["chapter_index"] == 15
    assert all_bms2[0]["chapter_title"] == "Chapter 15: The Breakthrough"

    # 3. Save bookmark for a second novel
    temp_db.save_novel_bookmark(
        source_name="MockSource",
        novel_title="Magic King",
        novel_url="http://mock.test/novel/magic-king",
        chapter_index=3,
        chapter_title="Chapter 3: Spell Casting",
        chapter_url="http://mock.test/novel/magic-king/ch3",
    )

    all_bms3 = temp_db.list_novel_bookmarks()
    assert len(all_bms3) == 2

    # 4. Get specific novel bookmark
    bm = temp_db.get_novel_bookmark("http://mock.test/novel/sword-god")
    assert bm is not None
    assert bm["chapter_index"] == 15

    # 5. Delete bookmark
    del_ok = temp_db.delete_novel_bookmark(all_bms3[0]["id"])
    assert del_ok is True
    assert len(temp_db.list_novel_bookmarks()) == 1
