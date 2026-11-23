"""
Factory for discovering, matching, and instantiating document parsers.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Type

from novel_reader.core.exceptions import UnsupportedFormatError
from novel_reader.parsers.base import BaseParser
from novel_reader.parsers.epub import EpubParser
from novel_reader.parsers.txt import TextParser


class ParserFactory:
    """Registry and factory for file parsers."""

    def __init__(self) -> None:
        self._parsers: List[BaseParser] = []
        self._register_default_parsers()

    def _register_default_parsers(self) -> None:
        self.register_parser(TextParser())
        self.register_parser(EpubParser())

    def register_parser(self, parser: BaseParser) -> None:
        """Register a new parser instance."""
        self._parsers.append(parser)

    def get_parser_for_file(self, file_path: str | Path) -> BaseParser:
        """Find the matching parser for a given file path."""
        path = Path(file_path)
        for parser in self._parsers:
            if parser.can_parse(path):
                return parser

        raise UnsupportedFormatError(
            f"No parser available for format '{path.suffix}'. Supported extensions: {self.supported_extensions}"
        )

    @property
    def supported_extensions(self) -> List[str]:
        """List of all supported file extensions across all registered parsers."""
        exts: List[str] = []
        for p in self._parsers:
            exts.extend(p.supported_extensions)
        return sorted(list(set(exts)))


# Default global factory instance
default_factory = ParserFactory()
