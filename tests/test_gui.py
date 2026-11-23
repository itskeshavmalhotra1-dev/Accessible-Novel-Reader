"""
Tests for wxPython accessible GUI frame and controls.
"""

import wx

from novel_reader.sources.base import ChapterContent, ChapterItem, NovelItem
from novel_reader.ui.gui import (
    NovelReaderFrame,
    ID_HOTKEY_RELOAD,
    ID_HOTKEY_PREV_PAGE,
    ID_HOTKEY_NEXT_PAGE,
    ID_HOTKEY_PREV_CHAPTER,
    ID_HOTKEY_NEXT_CHAPTER,
)


def test_gui_frame_initialization() -> None:
    app = wx.App(False)
    frame = NovelReaderFrame(None)

    assert frame.GetTitle() == "Accessible Novel Reader"
    assert frame.choice_source is not None
    assert frame.list_categories is not None
    assert frame.txt_search is not None
    assert frame.btn_search is not None
    assert frame.btn_reload is not None
    assert frame.btn_update is not None
    assert frame.list_novels is not None
    assert frame.list_chapters is not None
    assert frame.txt_reading is not None
    assert frame.btn_prev_chapter is not None
    assert frame.btn_next_chapter is not None
    assert frame.btn_prev_page is not None
    assert frame.btn_next_page is not None
    assert frame.lbl_page_info is not None
    assert frame.current_page == 1

    # Test updating novel list with independent token guard
    novels = [
        NovelItem(id="n1", title="Test Novel 1", url="http://test/1", source_name="TestSrc"),
        NovelItem(id="n2", title="Test Novel 2", url="http://test/2", source_name="TestSrc"),
    ]
    frame._update_novel_list(novels, "Found 2 novels.", frame._novel_token)
    assert frame.list_novels.GetCount() == 2
    assert frame.list_novels.GetString(0) == "Test Novel 1"
    assert frame.btn_prev_page.IsEnabled() is False  # page 1
    assert frame.btn_next_page.IsEnabled() is True   # has novels
    assert frame.lbl_page_info.GetLabel() == "Page 1"

    # Test updating chapters with independent token guard
    chapters = [
        ChapterItem(index=1, title="Chapter 1", url="http://test/1/ch1"),
        ChapterItem(index=2, title="Chapter 2", url="http://test/1/ch2"),
    ]
    frame.current_novel = novels[0]
    frame._update_chapter_list(chapters, frame._chap_token)
    assert frame.list_chapters.GetCount() == 2

    # Test displaying chapter content into the reading section
    content = ChapterContent(
        title="Chapter 1: The Beginning",
        content="Line 1 of the story.\nLine 2 of the story.",
        url="http://test/1/ch1",
        next_chapter_url="http://test/1/ch2",
    )
    frame._display_chapter_content(content, frame._content_token)
    assert "Line 1 of the story" in frame.txt_reading.GetValue()
    assert frame.lbl_chapter_title.GetLabel() == "Chapter 1: The Beginning"

    # Test essential accelerator event dispatch
    event_reload = wx.CommandEvent(wx.wxEVT_MENU, ID_HOTKEY_RELOAD)
    assert frame.GetEventHandler().ProcessEvent(event_reload)

    event_next_page = wx.CommandEvent(wx.wxEVT_MENU, ID_HOTKEY_NEXT_PAGE)
    assert frame.GetEventHandler().ProcessEvent(event_next_page)

    event_prev_page = wx.CommandEvent(wx.wxEVT_MENU, ID_HOTKEY_PREV_PAGE)
    assert frame.GetEventHandler().ProcessEvent(event_prev_page)

    event_next_chap = wx.CommandEvent(wx.wxEVT_MENU, ID_HOTKEY_NEXT_CHAPTER)
    assert frame.GetEventHandler().ProcessEvent(event_next_chap)

    event_prev_chap = wx.CommandEvent(wx.wxEVT_MENU, ID_HOTKEY_PREV_CHAPTER)
    assert frame.GetEventHandler().ProcessEvent(event_prev_chap)

    frame.Destroy()
    app.Destroy()
