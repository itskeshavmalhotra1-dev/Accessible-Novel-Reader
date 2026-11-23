"""
Online novel scrapers and sources package.
"""

from novel_reader.sources.base import (
    BaseNovelSource,
    CategoryItem,
    ChapterContent,
    ChapterItem,
    NovelItem,
)
from novel_reader.sources.freewebnovel import FreeWebNovelSource
from novel_reader.sources.novelfull import (
    NovelFullCompatibleSource,
    NovelFullSource,
    NovGoSource,
)
from novel_reader.sources.novelping import NovelPingSource
from novel_reader.sources.registry import SourceRegistry, default_sources

__all__ = [
    "BaseNovelSource",
    "NovelItem",
    "ChapterItem",
    "ChapterContent",
    "FreeWebNovelSource",
    "NovelFullCompatibleSource",
    "NovelFullSource",
    "NovGoSource",
    "NovelPingSource",
    "SourceRegistry",
    "default_sources",
]
