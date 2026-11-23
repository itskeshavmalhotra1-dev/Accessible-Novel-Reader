"""
Tests for core data models.
"""

from novel_reader.core.models import Book, BookMetadata, Bookmark, Chapter, ReadingProgress


def test_book_metadata_defaults() -> None:
    meta = BookMetadata(title="Test Novel")
    assert meta.title == "Test Novel"
    assert meta.author == "Unknown Author"
    assert meta.language == "en"
    assert meta.source_format == "txt"


def test_chapter_word_count() -> None:
    content = "The quick brown fox jumps over the lazy dog."
    ch = Chapter(index=0, title="Intro", content=content)
    assert ch.word_count == 9
    assert ch.index == 0


def test_book_aggregate_properties() -> None:
    ch1 = Chapter(index=0, title="Ch 1", content="One two three")
    ch2 = Chapter(index=1, title="Ch 2", content="Four five six seven")
    book = Book(
        id="book-1",
        file_path="/path/test.txt",
        metadata=BookMetadata(title="Test"),
        chapters=[ch1, ch2],
    )
    assert book.total_chapters == 2
    assert book.total_words == 7
    assert book.get_chapter(0) == ch1
    assert book.get_chapter(1) == ch2
    assert book.get_chapter(2) is None


def test_bookmark_creation() -> None:
    bm = Bookmark(book_id="b1", chapter_index=1, paragraph_index=3, snippet="Some text...")
    assert bm.book_id == "b1"
    assert bm.chapter_index == 1
    assert bm.paragraph_index == 3
    assert bm.snippet == "Some text..."
