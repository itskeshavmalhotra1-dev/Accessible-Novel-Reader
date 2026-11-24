"""
Tests for online novel sources and scrapers.
"""

from unittest.mock import MagicMock, patch

from novel_reader.sources.base import ChapterContent, ChapterItem, NovelItem
from novel_reader.sources.freewebnovel import FreeWebNovelSource
from novel_reader.sources.novelfull import NovelFullSource
from novel_reader.sources.registry import SourceRegistry, default_sources


def test_source_registry_registration() -> None:
    registry = SourceRegistry()
    names = registry.list_source_names()
    assert "FreeWebNovel" in names
    assert "NovelFull" in names
    assert "NovGo" in names
    assert "NovelPing" in names
    assert registry.get_source("freewebnovel") is not None


def test_freewebnovel_novel_list_parsing() -> None:
    source = FreeWebNovelSource()
    sample_html = """
    <div class="col-content">
        <div class="li-row">
            <h3 class="tit"><a href="/novel/fantasy-tale" title="Fantasy Tale">Fantasy Tale</a></h3>
            <a href="/novel/fantasy-tale/chapter-100">Chapter 100</a>
        </div>
        <div class="li-row">
            <h3 class="tit"><a href="/novel/mystery-chronicle" title="Mystery Chronicle">Mystery Chronicle</a></h3>
            <a href="/novel/mystery-chronicle/chapter-500">Chapter 500</a>
        </div>
    </div>
    """
    items = source._parse_novel_list(sample_html)
    assert len(items) == 2
    assert items[0].title == "Fantasy Tale"
    assert items[0].id == "fantasy-tale"
    assert "Chapter 100" in items[0].latest_chapter
    assert items[1].title == "Mystery Chronicle"


def test_novelfull_novel_list_parsing() -> None:
    source = NovelFullSource()
    sample_html = """
    <div class="list-novel">
        <div class="row">
            <div class="col-xs-7">
                <h3 class="novel-title"><a href="/adventure-story.html" title="Adventure Story">Adventure Story</a></h3>
            </div>
        </div>
        <div class="row">
            <div class="col-xs-7">
                <h3 class="novel-title"><a href="/ancient-legend.html" title="Ancient Legend">Ancient Legend</a></h3>
            </div>
        </div>
    </div>
    """
    items = source._parse_novel_list(sample_html)
    assert len(items) == 2
    assert items[0].title == "Adventure Story"
    assert items[0].id == "adventure-story"
    assert items[1].title == "Ancient Legend"


def test_freewebnovel_chapter_content_extraction() -> None:
    source = FreeWebNovelSource()
    sample_html = """
    <html>
        <div class="titles"><h1>Chapter 1: The Journey</h1></div>
        <div class="txt">
            <script>ads();</script>
            <p>The dawn arrived quietly across the green valley.</p>
            <p>The traveler stepped forward onto the stone path.</p>
        </div>
        <a id="prev_url" href="/novel/fantasy-tale/chapter-0">Prev</a>
        <a id="next_url" href="/novel/fantasy-tale/chapter-2">Next</a>
    </html>
    """
    from bs4 import BeautifulSoup
    with patch("novel_reader.sources.freewebnovel.http_get_soup") as mock_soup:
        mock_soup.return_value = BeautifulSoup(sample_html, "html.parser")

        content = source.get_chapter_content("https://freewebnovel.com/novel/fantasy-tale/chapter-1")
        assert content.title == "Chapter 1: The Journey"
        assert "The traveler stepped forward onto the stone path." in content.content
        assert "ads();" not in content.content
        assert content.prev_chapter_url == "https://freewebnovel.com/novel/fantasy-tale/chapter-0"
        assert content.next_chapter_url == "https://freewebnovel.com/novel/fantasy-tale/chapter-2"


def test_freewebnovel_category_pagination() -> None:
    source = FreeWebNovelSource()
    with patch("novel_reader.sources.freewebnovel.http_get") as mock_http_get:
        mock_http_get.return_value = "<html></html>"

        # Page 1
        source.get_novels_by_category("https://freewebnovel.com/genre/Action", page=1)
        mock_http_get.assert_called_with("https://freewebnovel.com/genre/Action", timeout=15)

        # Page 2
        source.get_novels_by_category("https://freewebnovel.com/genre/Action", page=2)
        mock_http_get.assert_called_with("https://freewebnovel.com/genre/Action/2", timeout=15)


def test_novelfull_category_pagination() -> None:
    source = NovelFullSource()
    with patch("novel_reader.sources.novelfull.http_get") as mock_http_get:
        mock_http_get.return_value = "<html></html>"

        # Page 1
        source.get_novels_by_category("https://novelfull.net/genre/Action", page=1)
        mock_http_get.assert_called_with("https://novelfull.net/genre/Action", timeout=15)

        # Page 2
        source.get_novels_by_category("https://novelfull.net/genre/Action", page=2)
        mock_http_get.assert_called_with("https://novelfull.net/genre/Action?page=2", timeout=15)
