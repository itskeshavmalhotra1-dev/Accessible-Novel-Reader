"""
Tests for document parsers (TextParser, EpubParser, and ParserFactory).
"""

from pathlib import Path
import pytest

from novel_reader.core.exceptions import UnsupportedFormatError
from novel_reader.parsers.epub import EpubParser
from novel_reader.parsers.factory import ParserFactory
from novel_reader.parsers.txt import TextParser


def test_txt_parser(sample_txt_file: Path) -> None:
    parser = TextParser()
    assert parser.can_parse(sample_txt_file)

    meta = parser.extract_metadata(sample_txt_file)
    assert meta.title == "The Chrono Paradox"
    assert meta.author == "Jane Doe"
    assert meta.source_format == "txt"

    book = parser.parse(sample_txt_file)
    assert book.total_chapters == 3  # Ch1, Ch2, Epilogue
    assert "Chapter 1" in book.chapters[0].title
    assert "Departure" in book.chapters[0].title
    assert "chrono-harness" in book.chapters[0].content
    assert "Chapter 2" in book.chapters[1].title
    assert "Neo-Tokyo" in book.chapters[1].content
    assert "Epilogue" in book.chapters[2].title


def test_epub_parser(sample_epub_file: Path) -> None:
    parser = EpubParser()
    assert parser.can_parse(sample_epub_file)

    meta = parser.extract_metadata(sample_epub_file)
    assert meta.title == "Test EPUB Novel"
    assert meta.author == "Arthur Conan"
    assert meta.source_format == "epub"

    book = parser.parse(sample_epub_file)
    assert book.total_chapters == 2
    assert "Chapter 1" in book.chapters[0].title
    assert "staff" in book.chapters[0].content
    assert "Chapter 2" in book.chapters[1].title


def test_parser_factory(sample_txt_file: Path, sample_epub_file: Path, temp_dir: Path) -> None:
    factory = ParserFactory()
    assert isinstance(factory.get_parser_for_file(sample_txt_file), TextParser)
    assert isinstance(factory.get_parser_for_file(sample_epub_file), EpubParser)

    unsupported = temp_dir / "test.xyz"
    unsupported.touch()
    with pytest.raises(UnsupportedFormatError):
        factory.get_parser_for_file(unsupported)
