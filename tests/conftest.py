"""
Shared test fixtures and setup for novel-reader tests.
"""

from pathlib import Path
import tempfile
from typing import Generator
import zipfile

import pytest

from novel_reader.core.models import Book, BookMetadata, Chapter
from novel_reader.library.database import Database
from novel_reader.library.manager import LibraryManager


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    with tempfile.TemporaryDirectory() as td:
        yield Path(td)


@pytest.fixture
def temp_db(temp_dir: Path) -> Database:
    db_file = temp_dir / "test_library.db"
    return Database(db_path=db_file)


@pytest.fixture
def library_manager(temp_db: Database) -> LibraryManager:
    return LibraryManager(db=temp_db)


@pytest.fixture
def sample_txt_file(temp_dir: Path) -> Path:
    file_path = temp_dir / "sample_novel.txt"
    content = """Title: The Chrono Paradox
Author: Jane Doe

Chapter 1: The Departure
In the year 2342, temporal transit was commonplace.
Mark adjusted his chrono-harness and stepped into the vortex.

Chapter 2: The Anomaly
The destination coordinates had shifted.
Instead of Neo-Tokyo, ancient stone pillars greeted him.
An eerie silence hung over the desolate ruins.

Epilogue
Years passed before the signal was recovered.
The timeline remained fractured forever.
"""
    file_path.write_text(content, encoding="utf-8")
    return file_path


@pytest.fixture
def sample_epub_file(temp_dir: Path) -> Path:
    epub_path = temp_dir / "sample_novel.epub"
    with zipfile.ZipFile(epub_path, "w") as zf:
        # mimetype
        zf.writestr("mimetype", "application/epub+zip")
        # container.xml
        zf.writestr(
            "META-INF/container.xml",
            """<?xml version="1.0"?>
            <container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
                <rootfiles>
                    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
                </rootfiles>
            </container>
            """,
        )
        # content.opf
        zf.writestr(
            "OEBPS/content.opf",
            """<?xml version="1.0" encoding="utf-8"?>
            <package xmlns="http://www.idpf.org/2007/opf" version="2.0">
                <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
                    <dc:title>Test EPUB Novel</dc:title>
                    <dc:creator>Arthur Conan</dc:creator>
                    <dc:language>en</dc:language>
                </metadata>
                <manifest>
                    <item id="ch1" href="ch1.xhtml" media-type="application/xhtml+xml"/>
                    <item id="ch2" href="ch2.xhtml" media-type="application/xhtml+xml"/>
                </manifest>
                <spine>
                    <itemref idref="ch1"/>
                    <itemref idref="ch2"/>
                </spine>
            </package>
            """,
        )
        # ch1.xhtml
        zf.writestr(
            "OEBPS/ch1.xhtml",
            """<?xml version="1.0" encoding="utf-8"?>
            <html xmlns="http://www.w3.org/1999/xhtml">
            <head><title>Chapter 1</title></head>
            <body>
                <h1>Chapter 1: The Awakening</h1>
                <p>The sound of thunder echoed through the dark valley.</p>
                <p>Kael opened his eyes and reached for his staff.</p>
            </body>
            </html>
            """,
        )
        # ch2.xhtml
        zf.writestr(
            "OEBPS/ch2.xhtml",
            """<?xml version="1.0" encoding="utf-8"?>
            <html xmlns="http://www.w3.org/1999/xhtml">
            <head><title>Chapter 2</title></head>
            <body>
                <h1>Chapter 2: The Journey Begins</h1>
                <p>With provisions packed, the small company departed at dawn.</p>
            </body>
            </html>
            """,
        )
    return epub_path
