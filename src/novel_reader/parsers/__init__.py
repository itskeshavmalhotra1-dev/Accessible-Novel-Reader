"""
Document format parsers for text, markdown, epub, and more.
"""

from novel_reader.parsers.base import BaseParser
from novel_reader.parsers.epub import EpubParser
from novel_reader.parsers.factory import ParserFactory, default_factory
from novel_reader.parsers.txt import TextParser

__all__ = [
    "BaseParser",
    "TextParser",
    "EpubParser",
    "ParserFactory",
    "default_factory",
]
