"""
Tests for wxPython accessible GUI frame and controls.
"""

from unittest.mock import patch, MagicMock
import wx

from novel_reader.sources.base import ChapterContent, ChapterItem, NovelItem
from novel_reader.ui.gui import (
    NovelReaderFrame,
    ID_HOTKEY_RELOAD,
    ID_HOTKEY_PREV_PAGE,
    ID_HOTKEY_NEXT_PAGE,
    ID_HOTKEY_PREV_CHAPTER,
    ID_HOTKEY_NEXT_CHAPTER,
    ID_HOTKEY_JUMP_CHAPTER,
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
    assert frame.choice_chapter_range is not None
    assert frame.btn_jump_chapter is not None
    assert frame.btn_sort_chapters is not None
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

    # Test updating chapters with independent token guard (small novel <= 100)
    chapters = [
        ChapterItem(index=1, title="Chapter 1", url="http://test/1/ch1"),
        ChapterItem(index=2, title="Chapter 2", url="http://test/1/ch2"),
    ]
    frame.current_novel = novels[0]
    frame._update_chapter_list(chapters, frame._chap_token)
    assert frame.list_chapters.GetCount() == 2
    assert frame.choice_chapter_range.IsShown() is False

    # Test smart chapter bucketing for large novels (> 100 chapters)
    large_chapters = [
        ChapterItem(index=i, title=f"Chapter {i}", url=f"http://test/1/ch{i}")
        for i in range(1, 251)
    ]
    frame._update_chapter_list(large_chapters, frame._chap_token)
    assert len(frame.all_chapters) == 250
    assert frame.choice_chapter_range.IsShown() is True
    assert frame.choice_chapter_range.GetCount() == 3  # 1-100, 101-200, 201-250
    assert frame.list_chapters.GetCount() == 100  # First bucket has 100 items

    # Switch bucket to bucket 1 (Chapters 101-200)
    frame.choice_chapter_range.SetSelection(1)
    frame.on_chapter_range_changed()
    assert frame.list_chapters.GetCount() == 100
    assert frame.list_chapters.GetString(0) == "Chapter 101"

    # Toggle Sort Order (Ascending to Descending)
    frame.on_toggle_chapter_sort()
    assert frame.chapter_sort_asc is False
    assert frame.btn_sort_chapters.GetLabel() == "Sort: 9-1"
    assert frame.list_chapters.GetString(0) == "Chapter 250"

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

    # Test programmatic jump to chapter (re-sort back to ascending first)
    frame.chapter_sort_asc = False
    frame.on_toggle_chapter_sort()  # back to True
    frame.on_jump_to_chapter(target_input="150")
    assert frame.choice_chapter_range.GetSelection() == 1  # 101-200
    assert frame.current_chapter is not None
    assert frame.current_chapter.index == 150

    with patch("wx.TextEntryDialog") as mock_dlg_cls:
        mock_dlg = MagicMock()
        mock_dlg.ShowModal.return_value = wx.ID_OK
        mock_dlg.GetValue.return_value = "50"
        mock_dlg_cls.return_value = mock_dlg

        event_jump = wx.CommandEvent(wx.wxEVT_MENU, ID_HOTKEY_JUMP_CHAPTER)
        assert frame.GetEventHandler().ProcessEvent(event_jump)
        assert frame.choice_chapter_range.GetSelection() == 0  # 1-100
        assert frame.current_chapter.index == 50

    frame.Destroy()
    app.Destroy()
