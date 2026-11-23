"""
Plain text and Markdown novel parser with smart chapter detection.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
import re
from typing import List

from novel_reader.core.exceptions import ParserError
from novel_reader.core.models import Book, BookMetadata, Chapter
from novel_reader.parsers.base import BaseParser
from novel_reader.utils.encoding import read_text_file
from novel_reader.utils.text import normalize_whitespace

# Regex patterns for detecting chapters in English, Chinese/CJK, and Markdown
CHAPTER_PATTERNS = [
    # English chapter headers: Chapter 1, Chapter One, Chapter I, Ch. 1, Episode 1, Volume 1
    re.compile(
        r"^(?:chapter|ch\.|volume|vol\.|book|act|episode|scene)\s+(?:[0-9]+|[ivxlcdm]+|[a-z]+)(?:\s*[:.\-—]\s*.*)?$",
        re.IGNORECASE,
    ),
    # Standalone prologue, epilogue, interlude, introduction, afterword
    re.compile(
        r"^(?:prologue|epilogue|interlude|prelude|afterword|introduction|foreword)(?:\s*[:.\-—]\s*.*)?$",
        re.IGNORECASE,
    ),
    # CJK Chapter patterns: 第1章, 第一回, 第1卷, etc.
    re.compile(r"^第[0-9一二三四五六七八九十百千万零]+[章节回卷折篇](?:\s+.*)?$"),
    # Markdown headings (# Chapter 1, ## Heading)
    re.compile(r"^#{1,3}\s+.+$"),
    # Numbered titles: 1. Introduction, 01 - The Beginning
    re.compile(r"^[0-9]{1,4}\s*[:.\-—]\s+\S+.*$"),
]


class TextParser(BaseParser):
    """Parser for plain text (.txt) and markdown (.md) novels."""

    @property
    def supported_extensions(self) -> tuple[str, ...]:
        return (".txt", ".md", ".text")

    def extract_metadata(self, file_path: str | Path) -> BookMetadata:
        path = Path(file_path)
        title = path.stem.replace("_", " ").strip()
        author = "Unknown Author"
        format_name = path.suffix.lower().lstrip(".")
        try:
            raw_text, _ = read_text_file(path)
            for line in raw_text.splitlines()[:25]:
                trimmed = line.strip()
                lower = trimmed.lower()
                if lower.startswith("title:"):
                    extracted = trimmed.split(":", 1)[1].strip()
                    if extracted:
                        title = extracted
                elif lower.startswith("author:"):
                    extracted = trimmed.split(":", 1)[1].strip()
                    if extracted:
                        author = extracted
        except Exception:
            pass

        return BookMetadata(
            title=title,
            author=author,
            source_format=format_name,
            identifier=self._generate_id(path),
        )

    def parse(self, file_path: str | Path) -> Book:
        path = Path(file_path)
        if not path.is_file():
            raise ParserError(f"Target file does not exist: {file_path}")

        try:
            raw_text, _ = read_text_file(path)
        except Exception as e:
            raise ParserError(f"Failed to read file {file_path}: {e}") from e

        metadata = self.extract_metadata(path)
        chapters = self._detect_chapters(raw_text)

        book_id = metadata.identifier or self._generate_id(path)
        return Book(
            id=book_id,
            file_path=str(path.resolve()),
            metadata=metadata,
            chapters=chapters,
        )

    def _detect_chapters(self, text: str) -> List[Chapter]:
        lines = text.splitlines()
        chapters: List[Chapter] = []
        current_title = "Beginning"
        current_lines: List[str] = []
        chapter_index = 0

        for line in lines:
            trimmed = line.strip()
            if self._is_chapter_heading(trimmed):
                # If we have accumulated text before this heading
                if current_lines:
                    # If this is the initial chunk and contains only metadata, discard it
                    if current_title == "Beginning" and self._is_only_metadata_lines(current_lines):
                        current_lines = []
                    else:
                        content = normalize_whitespace("\n".join(current_lines))
                        if content:
                            chapters.append(
                                Chapter(
                                    index=chapter_index,
                                    title=current_title,
                                    content=content,
                                )
                            )
                            chapter_index += 1
                        current_lines = []
                current_title = trimmed
            else:
                current_lines.append(line)

        # Append final chapter
        if current_lines:
            if not (current_title == "Beginning" and self._is_only_metadata_lines(current_lines)):
                content = normalize_whitespace("\n".join(current_lines))
                if content:
                    chapters.append(
                        Chapter(
                            index=chapter_index,
                            title=current_title,
                            content=content,
                        )
                    )

        # Fallback if no chapters or empty
        if not chapters:
            content = normalize_whitespace(text)
            if content:
                chapters.append(
                    Chapter(
                        index=0,
                        title="Complete Text",
                        content=content,
                    )
                )

        return chapters

    def _is_only_metadata_lines(self, lines: List[str]) -> bool:
        for line in lines:
            trimmed = line.strip()
            if not trimmed:
                continue
            lower = trimmed.lower()
            if not (lower.startswith("title:") or lower.startswith("author:") or lower.startswith("translator:")):
                return False
        return True

    def _is_chapter_heading(self, line: str) -> bool:
        if not line or len(line) > 120:
            return False
        for pattern in CHAPTER_PATTERNS:
            if pattern.match(line):
                return True
        return False

    @staticmethod
    def _generate_id(path: Path) -> str:
        data = f"{path.name}:{path.stat().st_size if path.exists() else 0}"
        return hashlib.sha256(data.encode("utf-8")).hexdigest()[:16]
