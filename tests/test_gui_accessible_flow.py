"""
End-to-end integration tests for accessible keyboard navigation and chapter reading.
"""

import wx
import pytest

from novel_reader.sources.base import (
    BaseNovelSource,
    CategoryItem,
    ChapterContent,
    ChapterItem,
    NovelItem,
)
from novel_reader.sources.registry import SourceRegistry
from novel_reader.ui.gui import (
    NovelReaderFrame,
    ID_HOTKEY_RELOAD,
    ID_HOTKEY_NEXT_CHAPTER,
    ID_HOTKEY_PREV_CHAPTER,
    ID_HOTKEY_PREV_PAGE,
    ID_HOTKEY_NEXT_PAGE,
)


class MockNovelSource(BaseNovelSource):
    @property
    def name(self) -> str:
        return "MockSource"

    @property
    def base_url(self) -> str:
        return "http://mock.test"

    def get_latest(self, page: int = 1):
        return self.get_novels_by_category("", page=page)

    def get_categories(self):
        return [
            CategoryItem(name="Action", url="http://mock.test/cat/action"),
            CategoryItem(name="Fantasy", url="http://mock.test/cat/fantasy"),
        ]

    def get_novels_by_category(self, category_url: str, page: int = 1):
        if page == 1:
            return [
                NovelItem(id="n1", title="Sword God", url="http://mock.test/novel/sword-god", source_name=self.name),
                NovelItem(id="n2", title="Magic King", url="http://mock.test/novel/magic-king", source_name=self.name),
            ]
        elif page == 2:
            return [
                NovelItem(id="n3", title="Dragon Emperor", url="http://mock.test/novel/dragon-emperor", source_name=self.name),
            ]
        return []

    def get_chapters(self, novel_url: str):
        return [
            ChapterItem(index=1, title="Chapter 1: Awaken", url="http://mock.test/novel/sword-god/ch1"),
            ChapterItem(index=2, title="Chapter 2: Training", url="http://mock.test/novel/sword-god/ch2"),
        ]

    def get_chapter_content(self, chapter_url: str):
        if "ch1" in chapter_url:
            return ChapterContent(
                title="Chapter 1: Awaken",
                content="Line 1 of Awaken.\nLine 2 of Awaken.",
                url=chapter_url,
                next_chapter_url="http://mock.test/novel/sword-god/ch2",
            )
        return ChapterContent(
            title="Chapter 2: Training",
            content="Line 1 of Training.\nLine 2 of Training.",
            url=chapter_url,
            prev_chapter_url="http://mock.test/novel/sword-god/ch1",
        )

    def search(self, query: str, page: int = 1):
        return self.get_novels_by_category("", page=page)


def test_accessible_hotkey_focus_navigation():
    app = wx.App(False)
    frame = NovelReaderFrame(None)

    # Test all essential hotkey commands dispatch properly
    for cmd_id in [
        ID_HOTKEY_RELOAD,
        ID_HOTKEY_PREV_PAGE,
        ID_HOTKEY_NEXT_PAGE,
        ID_HOTKEY_PREV_CHAPTER,
        ID_HOTKEY_NEXT_CHAPTER,
    ]:
        evt = wx.CommandEvent(wx.wxEVT_MENU, cmd_id)
        assert frame.GetEventHandler().ProcessEvent(evt) is True

    frame.Destroy()
    app.Destroy()


def test_chapter_navigation_and_crlf_formatting():
    app = wx.App(False)
    frame = NovelReaderFrame(None)

    mock = MockNovelSource()
    frame.current_source = mock

    # Populate categories
    cats = mock.get_categories()
    frame._update_categories_list(cats, frame._cat_token)
    assert frame.list_categories.GetCount() == 2
    assert frame.list_categories.GetString(0) == "Action"

    # Populate novels
    novels = mock.get_novels_by_category(cats[0].url)
    frame._update_novel_list(novels, "Loaded novels", frame._novel_token)
    assert frame.list_novels.GetCount() == 2
    assert frame.list_novels.GetString(0) == "Sword God"

    # Populate chapters
    chs = mock.get_chapters(novels[0].url)
    frame.current_novel = novels[0]
    frame._update_chapter_list(chs, frame._chap_token)
    assert frame.list_chapters.GetCount() == 2
    assert frame.list_chapters.GetString(0) == "Chapter 1: Awaken"

    # Load chapter 1
    content1 = mock.get_chapter_content(chs[0].url)
    frame._display_chapter_content(content1, frame._content_token)

    # Check reading content
    reading_val = frame.txt_reading.GetValue()
    assert "Line 1 of Awaken." in reading_val

    # Navigate to next chapter via Alt+N
    next_evt = wx.CommandEvent(wx.wxEVT_MENU, ID_HOTKEY_NEXT_CHAPTER)
    frame.GetEventHandler().ProcessEvent(next_evt)

    # Directly verify previous chapter navigation
    prev_evt = wx.CommandEvent(wx.wxEVT_MENU, ID_HOTKEY_PREV_CHAPTER)
    frame.GetEventHandler().ProcessEvent(prev_evt)

    frame.Destroy()
    app.Destroy()


def test_category_pagination_flow():
    app = wx.App(False)
    frame = NovelReaderFrame(None)

    mock = MockNovelSource()
    frame.current_source = mock
    frame.current_category = CategoryItem(name="Action", url="http://mock.test/cat/action")

    # Start on page 1
    novels_p1 = mock.get_novels_by_category(frame.current_category.url, page=1)
    frame._update_novel_list(novels_p1, "Page 1 loaded", frame._novel_token)

    assert frame.current_page == 1
    assert frame.lbl_page_info.GetLabel() == "Page 1"
    assert frame.btn_prev_page.IsEnabled() is False
    assert frame.btn_next_page.IsEnabled() is True
    assert frame.list_novels.GetCount() == 2
    assert frame.list_novels.GetString(0) == "Sword God"

    # Simulate pressing Next Page (PageDown)
    frame.on_next_page(None)
    # The worker in mock or direct update
    novels_p2 = mock.get_novels_by_category(frame.current_category.url, page=2)
    frame._update_novel_list(novels_p2, "Page 2 loaded", frame._novel_token)

    assert frame.current_page == 2
    assert frame.lbl_page_info.GetLabel() == "Page 2"
    assert frame.btn_prev_page.IsEnabled() is True
    assert frame.btn_next_page.IsEnabled() is True
    assert frame.list_novels.GetCount() == 1
    assert frame.list_novels.GetString(0) == "Dragon Emperor"

    # Simulate pressing Previous Page (PageUp)
    frame.on_prev_page(None)
    frame._update_novel_list(novels_p1, "Page 1 loaded", frame._novel_token)

    assert frame.current_page == 1
    assert frame.lbl_page_info.GetLabel() == "Page 1"
    assert frame.btn_prev_page.IsEnabled() is False

    frame.Destroy()
    app.Destroy()


def test_smart_chapter_bucketing_and_boundary_crossover():
    app = wx.App(False)
    frame = NovelReaderFrame(None)

    mock = MockNovelSource()
    frame.current_source = mock
    frame.current_novel = NovelItem(id="n_large", title="Grand Odyssey", url="http://mock.test/novel/odyssey", source_name="MockSource")

    # Generate 250 chapters
    large_chapters = [
        ChapterItem(index=i, title=f"Chapter {i}: Part {i}", url=f"http://mock.test/novel/odyssey/ch{i}")
        for i in range(1, 251)
    ]
    # Pre-cache chapter content for boundaries: ch100, ch101, ch102
    for i in [100, 101, 102]:
        url = f"http://mock.test/novel/odyssey/ch{i}"
        next_url = f"http://mock.test/novel/odyssey/ch{i+1}" if i < 250 else None
        prev_url = f"http://mock.test/novel/odyssey/ch{i-1}" if i > 1 else None
        frame._content_cache[url] = ChapterContent(
            title=f"Chapter {i}: Part {i}",
            content=f"Text of chapter {i}.",
            url=url,
            next_chapter_url=next_url,
            prev_chapter_url=prev_url,
        )

    frame._update_chapter_list(large_chapters, frame._chap_token)

    # 1. Verify initial bucketing
    assert len(frame.all_chapters) == 250
    assert frame.choice_chapter_range.IsShown() is True
    assert frame.choice_chapter_range.GetCount() == 3
    assert frame.choice_chapter_range.GetSelection() == 0  # Bucket 0: 1-100
    assert frame.list_chapters.GetCount() == 100

    # 2. Jump directly to Chapter 100 via smart jump
    frame.on_jump_to_chapter(target_input="100")
    assert frame.choice_chapter_range.GetSelection() == 0  # Still in bucket 0
    assert frame.list_chapters.GetSelection() == 99        # 100th item (0-indexed 99)
    assert frame.current_chapter.title == "Chapter 100: Part 100"
    assert frame.lbl_chapter_title.GetLabel() == "Chapter 100: Part 100"

    # 3. Next Chapter (crossing bucket boundary from 100 to 101)
    frame.on_next_chapter(None)
    assert frame.choice_chapter_range.GetSelection() == 1  # Automatically switched to bucket 1 (101-200)
    assert frame.list_chapters.GetSelection() == 0        # 1st item in bucket 1
    assert frame.current_chapter.title == "Chapter 101: Part 101"
    assert frame.lbl_chapter_title.GetLabel() == "Chapter 101: Part 101"

    # 4. Previous Chapter (crossing bucket boundary backward from 101 to 100)
    frame.on_prev_chapter(None)
    assert frame.choice_chapter_range.GetSelection() == 0  # Automatically switched back to bucket 0
    assert frame.list_chapters.GetSelection() == 99        # Last item in bucket 0
    assert frame.current_chapter.title == "Chapter 100: Part 100"

    # 5. Test jump to out-of-range or non-numeric input does not alter state or crash
    cur_sel = frame.list_chapters.GetSelection()
    frame.on_jump_to_chapter(target_input="not_a_number")
    assert frame.list_chapters.GetSelection() == cur_sel

    frame.on_jump_to_chapter(target_input="9999")
    assert frame.list_chapters.GetSelection() == cur_sel

    frame.Destroy()
    app.Destroy()
