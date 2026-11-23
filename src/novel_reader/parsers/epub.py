"""
Pure-Python EPUB format parser using standard library zipfile and XML parsing.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Dict, List, Optional
import xml.etree.ElementTree as ET
import zipfile

from novel_reader.core.exceptions import ParserError
from novel_reader.core.models import Book, BookMetadata, Chapter
from novel_reader.parsers.base import BaseParser
from novel_reader.utils.text import strip_html_tags


class EpubParser(BaseParser):
    """Parser for EPUB 2 and EPUB 3 electronic book formats."""

    @property
    def supported_extensions(self) -> tuple[str, ...]:
        return (".epub",)

    def extract_metadata(self, file_path: str | Path) -> BookMetadata:
        path = Path(file_path)
        if not path.is_file():
            raise ParserError(f"Target file does not exist: {file_path}")

        try:
            with zipfile.ZipFile(path, "r") as zf:
                opf_path = self._get_opf_path(zf)
                opf_data = zf.read(opf_path)
                return self._parse_opf_metadata(opf_data, path)
        except Exception as e:
            raise ParserError(f"Failed to read EPUB metadata from {file_path}: {e}") from e

    def parse(self, file_path: str | Path) -> Book:
        path = Path(file_path)
        if not path.is_file():
            raise ParserError(f"Target file does not exist: {file_path}")

        try:
            with zipfile.ZipFile(path, "r") as zf:
                opf_path = self._get_opf_path(zf)
                opf_dir = str(Path(opf_path).parent)
                if opf_dir == ".":
                    opf_dir = ""

                opf_data = zf.read(opf_path)
                metadata = self._parse_opf_metadata(opf_data, path)
                chapters = self._parse_spine_chapters(zf, opf_data, opf_dir)

                book_id = metadata.identifier or self._generate_id(path)
                return Book(
                    id=book_id,
                    file_path=str(path.resolve()),
                    metadata=metadata,
                    chapters=chapters,
                )
        except Exception as e:
            raise ParserError(f"Failed to parse EPUB file {file_path}: {e}") from e

    def _get_opf_path(self, zf: zipfile.ZipFile) -> str:
        container_path = "META-INF/container.xml"
        if container_path not in zf.namelist():
            raise ParserError("Invalid EPUB: META-INF/container.xml missing")

        data = zf.read(container_path)
        root = ET.fromstring(data)
        # Find rootfile element
        for elem in root.iter():
            if elem.tag.endswith("rootfile"):
                full_path = elem.attrib.get("full-path")
                if full_path:
                    return full_path

        raise ParserError("Invalid EPUB: rootfile not found in container.xml")

    def _parse_opf_metadata(self, opf_data: bytes, path: Path) -> BookMetadata:
        root = ET.fromstring(opf_data)
        title = ""
        author = "Unknown Author"
        language = "en"
        desc = ""
        identifier = ""

        for elem in root.iter():
            tag = elem.tag.lower()
            if tag.endswith("title") and elem.text and not title:
                title = elem.text.strip()
            elif tag.endswith("creator") and elem.text:
                author = elem.text.strip()
            elif tag.endswith("language") and elem.text:
                language = elem.text.strip()
            elif tag.endswith("description") and elem.text:
                desc = elem.text.strip()
            elif tag.endswith("identifier") and elem.text and not identifier:
                identifier = elem.text.strip()

        return BookMetadata(
            title=title or path.stem.replace("_", " ").strip(),
            author=author,
            language=language,
            description=desc,
            identifier=identifier or self._generate_id(path),
            source_format="epub",
        )

    def _parse_spine_chapters(
        self, zf: zipfile.ZipFile, opf_data: bytes, opf_dir: str
    ) -> List[Chapter]:
        root = ET.fromstring(opf_data)
        manifest: Dict[str, str] = {}

        # Collect manifest items: id -> href
        for elem in root.iter():
            if elem.tag.endswith("item"):
                item_id = elem.attrib.get("id")
                href = elem.attrib.get("href")
                media_type = elem.attrib.get("media-type", "")
                if item_id and href and ("html" in media_type or "xml" in media_type or not media_type):
                    manifest[item_id] = href

        # Read spine order
        spine_items: List[str] = []
        for elem in root.iter():
            if elem.tag.endswith("itemref"):
                idref = elem.attrib.get("idref")
                if idref and idref in manifest:
                    spine_items.append(manifest[idref])

        chapters: List[Chapter] = []
        for idx, href in enumerate(spine_items):
            # Resolve relative href with opf_dir
            if opf_dir:
                entry_path = f"{opf_dir}/{href}".replace("\\", "/")
            else:
                entry_path = href.replace("\\", "/")

            if entry_path in zf.namelist():
                content_bytes = zf.read(entry_path)
                try:
                    content_str = content_bytes.decode("utf-8")
                except UnicodeDecodeError:
                    content_str = content_bytes.decode("latin-1", errors="replace")

                clean_text = strip_html_tags(content_str)
                if clean_text:
                    # Try to extract chapter title from first line
                    first_line = clean_text.splitlines()[0] if clean_text.splitlines() else ""
                    title = first_line[:60] if first_line else f"Section {idx + 1}"

                    chapters.append(
                        Chapter(
                            index=len(chapters),
                            title=title,
                            content=clean_text,
                            id=href,
                        )
                    )

        return chapters

    @staticmethod
    def _generate_id(path: Path) -> str:
        data = f"{path.name}:{path.stat().st_size if path.exists() else 0}"
        return hashlib.sha256(data.encode("utf-8")).hexdigest()[:16]
