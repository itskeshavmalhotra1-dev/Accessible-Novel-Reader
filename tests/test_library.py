"""
Tests for high-level LibraryManager operations.
"""

from pathlib import Path
import pytest

from novel_reader.core.exceptions import BookNotFoundError
from novel_reader.library.manager import LibraryManager


def test_import_and_load_txt_book(library_manager: LibraryManager, sample_txt_file: Path) -> None:
    book = library_manager.import_book(sample_txt_file)
    assert book.id is not None
    assert book.total_chapters == 3

    # Load from library
    loaded = library_manager.load_book(book.id)
    assert loaded.id == book.id
    assert loaded.total_chapters == 3

    # List library books
    books = library_manager.list_books()
    assert len(books) == 1
    assert books[0]["id"] == book.id


def test_remove_book(library_manager: LibraryManager, sample_txt_file: Path) -> None:
    book = library_manager.import_book(sample_txt_file)
    assert len(library_manager.list_books()) == 1

    deleted = library_manager.remove_book(book.id)
    assert deleted is True
    assert len(library_manager.list_books()) == 0

    with pytest.raises(BookNotFoundError):
        library_manager.load_book(book.id)
