"""
Source registry and aggregator for managing multiple novel websites.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from novel_reader.sources.base import (
    BaseNovelSource,
    ChapterContent,
    ChapterItem,
    NovelItem,
)
from novel_reader.sources.freewebnovel import FreeWebNovelSource
from novel_reader.sources.novelfull import (
    NovelFullSource,
    NovGoSource,
)
from novel_reader.sources.novelping import NovelPingSource


class SourceRegistry:
    """Manages available online novel sources."""

    def __init__(self) -> None:
        self._sources: Dict[str, BaseNovelSource] = {}
        self._register_default_sources()

    def _register_default_sources(self) -> None:
        self.register(FreeWebNovelSource())
        self.register(NovelFullSource())
        self.register(NovGoSource())
        self.register(NovelPingSource())

    def register(self, source: BaseNovelSource) -> None:
        self._sources[source.name.lower()] = source

    def get_source(self, name: str) -> Optional[BaseNovelSource]:
        return self._sources.get(name.lower())

    def list_sources(self) -> List[BaseNovelSource]:
        return list(self._sources.values())

    def list_source_names(self) -> List[str]:
        return [s.name for s in self._sources.values()]

    def search_all(self, query: str) -> List[NovelItem]:
        results: List[NovelItem] = []
        for src in self._sources.values():
            try:
                results.extend(src.search(query))
            except Exception:
                pass
        return results


default_sources = SourceRegistry()
